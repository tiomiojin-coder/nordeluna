import contextlib
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch,MagicMock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import publication_center_core as center


class PublicationCenterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.game=self.root/'game';self.game.mkdir()
        for name,body in {'Game.ini':b'[Game]','Data/Scripts.rxdata':b'scripts','Data/species.dat':b'species','Data/moves.dat':b'moves','Graphics/UI/icon.png':b'image','mkxp.json':b'{}','soundfont.sf2':b'font'}.items():
            file=self.game/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(body)
        self.base=self.root/'base.json';self.base.write_text(json.dumps({'base':'1'*32,'files':center.content.scan(self.game),'compatibility':center.content.compatibility(self.game)}))
        self.patch('content.BASE',self.base);self.patch('reviewed_code',MagicMock(return_value={}))
        self.patch('versions',MagicMock(return_value={'pc':'1.3.1','pc_code':131,'android':'1.16.1','android_code':24}))
        self.patch('SESSION',self.root/'session.json');self.patch('STATE',self.root)
    def patch(self,name,value):
        target=center
        parts=name.split('.')
        for part in parts[:-1]:target=getattr(target,part)
        p=patch.object(target,parts[-1],value);p.start();self.addCleanup(p.stop)

    def test_moves_and_sprites_use_one_shared_content_pack(self):
        (self.game/'Data/moves.dat').write_bytes(b'updated-moves')
        (self.game/'Graphics/UI/icon.png').write_bytes(b'updated-sprite')
        plan=center.analyze(self.game)
        self.assertEqual(plan['mode'],'content')
        self.assertEqual({r['path'] for r in plan['changes']},{'Data/moves.dat','Graphics/UI/icon.png'})
    def test_plugins_and_removals_select_full_release(self):
        (self.game/'Data/Scripts.rxdata').write_bytes(b'new-engine')
        self.assertEqual(center.analyze(self.game)['mode'],'full')
        (self.game/'Data/Scripts.rxdata').write_bytes(b'scripts')
        (self.game/'Graphics/UI/icon.png').unlink()
        self.assertEqual(center.analyze(self.game)['mode'],'full')
    def test_local_program_changes_are_reviewed_in_full_release(self):
        center.reviewed_code.return_value={'android/ClientLauncher.java':'a'*64}
        plan=center.analyze(self.game)
        self.assertEqual(plan['mode'],'full');self.assertIn('android/ClientLauncher.java',plan['code'])
    def test_changed_game_or_code_after_preview_is_rejected(self):
        plan=center.analyze(self.game)
        (self.game/'Data/moves.dat').write_bytes(b'different-size')
        with self.assertRaisesRegex(ValueError,'mudaram'):center.unchanged(plan)
        plan=center.analyze(self.game);center.reviewed_code.return_value={'scripts/new.py':'a'*64}
        with self.assertRaisesRegex(ValueError,'mudaram'):center.unchanged(plan)
    def test_generated_versions_match_both_workflows_and_installed_codes(self):
        root=Path(__file__).resolve().parents[2]
        patch_text=(root/'android/nordeluna.patch').read_text(encoding='utf-8')
        android=(root/'.github/workflows/nordeluna-android.yml').read_text(encoding='utf-8')
        pc=(root/'.github/workflows/nordeluna-pc.yml').read_text(encoding='utf-8')
        p,a,w=center.release_sources(patch_text,android,pc,center.versions(),'a'*64,'docs/release-1.16.1.md')
        self.assertIn('versionCode 24',p);self.assertIn('versionName "1.16.1"',p)
        self.assertIn('android-1.16.1',a);self.assertIn('v1.16.1.apk',a);self.assertIn('GAME_ARCHIVE_SHA256: '+'a'*64,a)
        self.assertIn('--version 1.3.1 --code 131',w);self.assertIn('pc-1.3.1',w)
        self.assertNotIn('release-1.16.md',a+w)
    def test_content_upload_failure_can_resume_exact_package_without_token_on_disk(self):
        plan={'mode':'content'};package=self.root/'package.zip'
        with patch.object(center.core,'exclusive_lock',contextlib.nullcontext),patch.object(center,'prepare_content',return_value=package),patch.object(center.content,'load_package',return_value=('manifest',None,None,None)),patch.object(center.content,'publish_package',side_effect=ValueError('connection lost')):
            with self.assertRaises(ValueError):center.publish(plan,'Title','Notes',2,'testers','private-token',threading.Event(),lambda *a:None)
        state=center.read_session();self.assertEqual(state['phase'],'content_prepared');self.assertNotIn('private-token',center.SESSION.read_text())
        with patch.object(center.core,'exclusive_lock',contextlib.nullcontext),patch.object(center.content,'publish_package') as send:
            center.resume('new-token',threading.Event(),lambda *a:None)
        self.assertEqual(send.call_args.kwargs['expected_manifest'],hashlib.sha256(b'manifest').hexdigest())
        self.assertEqual(send.call_args.kwargs['channel'],'testers');self.assertEqual(center.read_session()['phase'],'complete')
    def test_full_release_waits_for_both_builds_before_signing(self):
        state={'phase':'building','commit':'source','versions':center.versions(),'notes':'docs/notes.md','audience':'testers','pc_dispatched':False}
        client=MagicMock();completed={'workflow_runs':[{'head_sha':'source','status':'completed','conclusion':'success','html_url':'https://github.com/example'}]};client.get.side_effect=[{'workflow_runs':[]},completed,completed]
        with patch.object(center.core,'git',return_value='source'),patch.object(center.core,'GitHub',return_value=client),patch.object(center,'post') as dispatch,patch.object(center.subprocess,'run') as run,patch.object(center,'publish_testers') as publish:
            run.return_value.returncode=0;center.finish_full(state,'token',threading.Event(),lambda *a:None)
        self.assertEqual(client.get.call_count,3);dispatch.assert_called_once();publish.assert_called_once()
        args=run.call_args.args[0];self.assertIn('--testers-only',args);self.assertNotIn('--publish',args)
        self.assertEqual(state['phase'],'catalog_signed')
    def test_failed_build_never_signs_or_publishes(self):
        state={'phase':'building','commit':'source','versions':center.versions(),'notes':'docs/notes.md','audience':'stable','pc_dispatched':True}
        client=MagicMock();client.get.return_value={'workflow_runs':[{'head_sha':'source','status':'completed','conclusion':'failure','html_url':'https://github.com/example'}]}
        with patch.object(center.core,'git',return_value='source'),patch.object(center.core,'GitHub',return_value=client),patch.object(center.subprocess,'run') as run,patch.object(center,'publish_testers') as publish:
            with self.assertRaisesRegex(ValueError,'falhou'):center.finish_full(state,'token',threading.Event(),lambda *a:None)
        run.assert_not_called();publish.assert_not_called()

    def prepare_fixture(self):
        project=self.root/'project';project.mkdir()
        actual=Path(__file__).resolve().parents[2]
        for name in ['android/nordeluna.patch','.github/workflows/nordeluna-android.yml','.github/workflows/nordeluna-pc.yml']:
            target=project/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((actual/name).read_bytes())
        (project/'docs').mkdir();(project/'game-assets').mkdir()
        (project/'game-assets/sha256.txt').write_text('old-sha')
        (project/'game-assets/game-assets.zip.part001').write_bytes(b'old-part-1')
        (project/'game-assets/game-assets.zip.part002').write_bytes(b'old-part-2')
        index=self.root/'index';index.write_bytes(b'previous-staging-index')
        center.content.BASE.with_name('touched.json').write_text('["Graphics/UI/icon.png"]')
        return project,index

    def test_failed_full_preparation_restores_base_history_files_and_git_index(self):
        project,index=self.prepare_fixture();base=center.content.BASE.read_bytes();touched=center.content.BASE.with_name('touched.json')
        def package(*args):
            center.content.BASE.write_bytes(b'future-base');touched.write_bytes(b'[]');index.write_bytes(b'partial-index')
            raise ValueError('simulated preparation failure')
        plan={'source':str(self.game),'code':{},'versions':center.versions()};client=MagicMock();client.get.return_value={'workflow_runs':[]}
        with patch.object(center,'ROOT',project),patch.object(center,'ensure_repository'),patch.object(center,'unchanged'),patch.object(center.core,'GitHub',return_value=client),patch.object(center.core,'git',return_value=str(index)),patch.object(center.core,'package_game',side_effect=package):
            with self.assertRaisesRegex(ValueError,'simulated'):center.prepare_full(plan,'Title','Notes','testers',threading.Event(),lambda *a:None)
        self.assertEqual(center.content.BASE.read_bytes(),base);self.assertEqual(json.loads(touched.read_text()),['Graphics/UI/icon.png'])
        self.assertEqual(index.read_bytes(),b'previous-staging-index');self.assertEqual((project/'game-assets/game-assets.zip.part001').read_bytes(),b'old-part-1')

    def test_full_preparation_uses_one_archive_and_records_both_versions_before_push(self):
        project,index=self.prepare_fixture();client=MagicMock();client.get.return_value={'workflow_runs':[]}
        def package(source,output,stop,notify):output.write_bytes(b'new-packed-game');return hashlib.sha256(output.read_bytes()).hexdigest()
        def git(*args):return str(index) if args==('rev-parse','--git-path','index') else 'source-commit'
        plan={'source':str(self.game),'code':{},'versions':center.versions()}
        with patch.object(center,'ROOT',project),patch.object(center,'ensure_repository'),patch.object(center,'unchanged'),patch.object(center.core,'GitHub',return_value=client),patch.object(center.core,'git',side_effect=git) as commands,patch.object(center.core,'package_game',side_effect=package):
            state=center.prepare_full(plan,'Title','Notes','testers',threading.Event(),lambda *a:None)
        self.assertEqual(state['commit'],'source-commit');self.assertEqual(state['phase'],'prepared')
        self.assertEqual((project/'game-assets/game-assets.zip.part001').read_bytes(),b'new-packed-game')
        self.assertFalse((project/'game-assets/game-assets.zip.part002').exists())
        self.assertTrue((project/'docs/release-1.16.1.md').is_file())
        self.assertFalse(any(call.args[0]=='push' for call in commands.call_args_list))


if __name__=='__main__':unittest.main()
