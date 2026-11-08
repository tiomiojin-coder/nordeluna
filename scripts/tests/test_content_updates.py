import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib
import zipfile

ROOT=Path(__file__).resolve().parents[2]
from server.relay import Store
from server.updates import UpdateService,allowed_path,validate_manifest,verify_signature,CHUNK,DIGEST_INFO
spec=importlib.util.spec_from_file_location('content_builder',ROOT/'scripts/content-update-tools.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def sign(data):
    key=json.loads(builder.PRIVATE.read_text(encoding='utf-8'))
    raw=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    digest=DIGEST_INFO+hashlib.sha256(raw.encode()).digest();block=b'\0\1'+b'\xff'*(256-len(digest)-3)+b'\0'+digest
    return raw,f'{pow(int.from_bytes(block,"big"),int(key["d"],16),int(key["n"],16)):0512x}'


class ContentUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Tests must never need the author's private signing key, including CI.
        cls.keydir=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.keydir.cleanup)
        cls.private=Path(cls.keydir.name)/'private.json';cls.public=Path(cls.keydir.name)/'public.json'
        with patch.object(builder,'PRIVATE',cls.private),patch.object(builder,'PUBLIC',cls.public):key=builder.signing_key()
        cls.public_data=dict(n=key['n'],base='1'*32);cls.public.write_text(json.dumps(cls.public_data))
    def setUp(self):
        for name,value in [('PRIVATE',self.private),('PUBLIC',self.public)]:
            changed=patch.object(builder,name,value);changed.start();self.addCleanup(changed.stop)
        changed=patch.object(UpdateService,'update_signing_key',return_value=self.public_data);changed.start();self.addCleanup(changed.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.game=self.root/'game';(self.game/'Data').mkdir(parents=True)
        (self.game/'Data/Map039.rxdata').write_bytes(b'original-map')
        self.base=self.root/'base.json';self.base.write_text(json.dumps(dict(base=json.loads(builder.PUBLIC.read_text())['base'],files=builder.scan(self.game))))
        self.store=Store(str(self.root/'relay.sqlite3'));self.addCleanup(lambda:self.store.db.close())
    def pack(self,version=1):
        (self.game/'Data/Map039.rxdata').write_bytes(b'new-map'*20000)
        (self.game/'Data/Map042.rxdata').write_bytes(b'new-area')
        with patch.object(builder,'BASE',self.base):path=builder.build(version,'Nova area','Novos eventos',self.game,self.root/f'pack-{version}.zip')
        return builder.load_package(path)
    def upload(self,package,finish=True,channel='stable'):
        raw,signature,data,blobs=package
        self.store.update_admin(dict(action='begin',manifest=raw,signature=signature,channel=channel))
        for digest,blob in blobs.items():
            for part,start in enumerate(range(0,len(blob),CHUNK)):
                payload=dict(action='put',version=data['version'],blob=digest,part=part,data=blob[start:start+CHUNK].hex())
                self.store.update_admin(payload);self.store.update_admin(payload)
        if finish:self.store.update_admin(dict(action='finish',version=data['version']))
    def test_pack_is_cumulative_signed_and_decompresses_to_game_bytes(self):
        raw,signature,data,blobs=self.pack();verify_signature(raw,signature,json.loads(builder.PUBLIC.read_text()))
        self.assertEqual({r['path'] for r in data['files']},{'Data/Map039.rxdata','Data/Map042.rxdata'})
        for row in data['files']:
            original=zlib.decompress(blobs[row['blob']]);self.assertEqual(original,(self.game/row['path']).read_bytes());self.assertEqual(hashlib.sha256(original).hexdigest(),row['sha256'])
        (self.game/'Data/Map043.rxdata').write_bytes(b'area2')
        self.assertEqual(len(self.pack(2)[2]['files']),3)
    def test_partial_upload_is_not_visible_and_retry_does_not_duplicate(self):
        package=self.pack();self.upload(package,False)
        self.assertIsNone(self.store.handle(dict(protocol=1,action='update_manifest',base=package[2]['base']))['manifest'])
        self.assertEqual(self.store.update_admin(dict(action='finish',version=1)),dict(published=1))
        manifest=self.store.handle(dict(protocol=1,action='update_manifest',base=package[2]['base']))
        self.assertEqual(manifest,dict(manifest=package[0],signature=package[1],channel='stable'))
        for digest,packed in package[3].items():
            data=self.store.handle(dict(protocol=1,action='update_chunk',version=1,blob=digest,part=0))
            self.assertEqual(bytes.fromhex(data['data']),packed[:CHUNK])
    def test_missing_chunk_and_tampered_signature_cannot_publish(self):
        raw,signature,data,_=self.pack()
        with self.assertRaises(ValueError):self.store.update_admin(dict(action='begin',manifest=raw+' ',signature=signature))
        self.store.update_admin(dict(action='begin',manifest=raw,signature=signature))
        with self.assertRaises(ValueError):self.store.update_admin(dict(action='finish',version=1))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM update_packages').fetchone()[0],0)
    def test_wrong_base_or_older_version_is_rejected(self):
        package=self.pack();self.upload(package)
        self.assertEqual(self.store.update_admin(dict(action='begin',manifest=package[0],signature=package[1])),dict(published=1,channel='stable'))
        changed=copy.deepcopy(package[2]);changed['title']='Outra edicao';raw,signature=sign(changed)
        with self.assertRaises(ValueError):self.store.update_admin(dict(action='begin',manifest=raw,signature=signature))
        data=copy.deepcopy(package[2]);data['version']=2;data['base']='f'*32;raw,signature=sign(data)
        with self.assertRaises(ValueError):self.store.update_admin(dict(action='begin',manifest=raw,signature=signature))
        self.assertIsNone(self.store.handle(dict(protocol=1,action='update_manifest',base='0'*32))['manifest'])
    def test_only_published_blobs_can_be_downloaded(self):
        package=self.pack();self.upload(package,False)
        with self.assertRaises(ValueError):self.store.handle(dict(protocol=1,action='update_chunk',version=1,blob=next(iter(package[3])),part=0))
    def test_paths_cannot_overwrite_saves_plugins_or_executables(self):
        for path in ['../Save.rxdata','Data/../Save.rxdata','/Data/Map039.rxdata','Data\\Map039.rxdata','Data/Scripts.rxdata','Data/PluginScripts.rxdata','Plugins/Nordeluna Online/x.rb','Graphics/UI/../../save.dat','Graphics/.secret/a.png','C:/a.png','Game.exe','Data/mapmetadata.dat','Data/Map039.rxdata/']:
            self.assertFalse(allowed_path(path),path)
        data=self.pack()[2]
        for path in ['Data/Scripts.rxdata','Data/../Map039.rxdata']:
            bad=copy.deepcopy(data);bad['files'][0]['path']=path
            with self.assertRaises(ValueError):validate_manifest(json.dumps(bad))
    def test_resource_limits_are_enforced_before_allocation(self):
        data=self.pack()[2];data['files'][0]['size']=2**32
        with self.assertRaises(ValueError):validate_manifest(json.dumps(data))
    def test_removed_base_file_requires_new_apk(self):
        (self.game/'Data/Map039.rxdata').unlink()
        with patch.object(builder,'BASE',self.base),self.assertRaisesRegex(ValueError,'removidos'):builder.build(1,'Test','',self.game,self.root/'bad.zip')
    def test_reverted_map_is_still_in_cumulative_pack(self):
        self.pack()
        (self.game/'Data/Map039.rxdata').write_bytes(b'original-map')
        with patch.object(builder,'BASE',self.base):path=builder.build(2,'Reverter mapa','',self.game,self.root/'revert.zip')
        rows=builder.load_package(path)[2]['files']
        self.assertIn('Data/Map039.rxdata',[r['path'] for r in rows])
    def test_storage_retains_three_cumulative_versions_and_reuses_shared_chunks(self):
        for version in range(1,5):self.upload(self.pack(version))
        self.assertEqual([r[0] for r in self.store.db.execute('SELECT version FROM update_packages ORDER BY version')],[2,3,4])
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM update_chunks').fetchone()[0],2)
    def test_apk_base_uses_checked_archive_instead_of_live_editor_files(self):
        base=json.loads(self.base.read_text());archive=self.root/'game.zip'
        with zipfile.ZipFile(archive,'w') as output:
            output.writestr('./Plugins/Nordeluna Online/028_ContentUpdates.rb',"BASE = '"+base['base']+"'")
            output.writestr('./Data/Map039.rxdata',b'actual-apk-map')
            output.writestr('./Data/System.rxdata',b'editor-magic-number')
            output.writestr('./Data/species.dat',b'species-data')
        with patch.object(builder,'BASE',self.base):self.assertTrue(builder.capture_apk_base(archive))
        captured=json.loads(self.base.read_text())
        self.assertEqual(captured['files']['Data/Map039.rxdata'],hashlib.sha256(b'actual-apk-map').hexdigest())
        self.assertNotIn('Data/System.rxdata',captured['compatibility'])
        self.assertIn('Data/species.dat',captured['compatibility'])
    def accounts(self):
        import secrets
        result=[]
        for nick in ('Lunar','Solar'):
            account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32))
            self.store.handle(dict(protocol=1,action='account_register',account=account,nickname=nick));result.append(account)
        return result
    def test_testers_require_server_membership_and_authentication_for_manifest_and_bytes(self):
        a,b=self.accounts();stable=self.pack(1);self.upload(stable)
        private=self.pack(2);self.upload(private,channel='testers')
        self.store.update_admin(dict(action='testers_set',testers=['Lunar']))
        query=dict(protocol=1,action='update_manifest',base=private[2]['base'])
        self.assertEqual(json.loads(self.store.handle(query)['manifest'])['version'],1)
        self.assertEqual(json.loads(self.store.handle(dict(query,account=b,tester=True))['manifest'])['version'],1)
        self.assertEqual(json.loads(self.store.handle(dict(query,account=a))['manifest'])['version'],2)
        blob=next(iter(private[3]));chunk=dict(protocol=1,action='update_chunk',version=2,blob=blob,part=0)
        for denied in (chunk,dict(chunk,account=b)):
            with self.assertRaises(ValueError):self.store.handle(denied)
        self.assertIn('data',self.store.handle(dict(chunk,account=a)))
        with self.assertRaises(Exception):self.store.handle(dict(query,account=dict(a,secret='0'*64)))
        editor=Store(str(self.root/'relay.sqlite3'))
        try:editor.update_admin(dict(action='testers_set',testers=[]))
        finally:editor.db.close()
        with self.assertRaises(ValueError):self.store.handle(dict(chunk,account=a))
    def test_promotion_reuses_signed_bytes_and_preserves_stable_during_many_tests(self):
        stable=self.pack(1);self.upload(stable)
        for version in range(2,6):self.upload(self.pack(version),channel='testers')
        query=dict(protocol=1,action='update_manifest',base=stable[2]['base'])
        self.assertEqual(json.loads(self.store.handle(query)['manifest'])['version'],1)
        before=self.store.db.execute('SELECT COUNT(*) FROM update_chunks').fetchone()[0]
        private=self.pack(5)
        editor=Store(str(self.root/'relay.sqlite3'))
        try:editor.update_admin(dict(action='promote',version=5,signature=private[1]))
        finally:editor.db.close()
        result=self.store.handle(query)
        self.assertEqual(result['manifest'],private[0]);self.assertEqual(result['channel'],'stable')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM update_chunks').fetchone()[0],before)
        with self.assertRaises(ValueError):self.store.update_admin(dict(action='promote',version=3,signature=self.pack(3)[1]))
    def test_rename_keeps_tester_and_invalid_replacement_keeps_old_group(self):
        a,_=self.accounts();self.store.update_admin(dict(action='testers_set',testers=['Lunar']))
        self.store.handle(dict(protocol=1,action='account_register',account=a,nickname='LunarNovo'))
        self.assertEqual(self.store.update_admin(dict(action='testers_get'))['testers'][0]['nickname'],'LunarNovo')
        with self.assertRaises(ValueError):self.store.update_admin(dict(action='testers_set',testers=['Unknown']))
        self.assertEqual(len(self.store.update_admin(dict(action='testers_get'))['testers']),1)
    def test_changed_package_cannot_be_uploaded_after_review(self):
        self.pack()
        with self.assertRaisesRegex(ValueError,'mudou depois da previa'):
            builder.publish_package('not-a-real-token',self.root/'pack-1.zip',expected_manifest='0'*64)
