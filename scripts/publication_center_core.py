"""One reviewed operation for both platforms. Importing never publishes anything."""
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib
from pathlib import Path

import updater_core as core

ROOT=core.ROOT
STATE=ROOT/'.cache/publication-center'
SESSION=STATE/'session.json'


def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


content=module('center_content','content-update-tools.py')


def digest(file):
    with file.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save_session(data):
    STATE.mkdir(parents=True,exist_ok=True)
    tmp=SESSION.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(SESSION)


def read_session():
    return json.loads(SESSION.read_text(encoding='utf-8')) if SESSION.is_file() else {}


def reviewed_code():
    files=set(filter(None,core.git('diff','--name-only','-z','HEAD').split('\0')))
    files.update(filter(None,core.git('ls-files','--others','--exclude-standard','-z').split('\0')))
    result={}
    for name in sorted(files):
        path=Path(name);parts=path.parts
        if any(p.startswith('.') and p!='.github' for p in parts):raise ValueError('Arquivo fora da publicacao: '+name)
        allowed=(parts[0] in {'scripts','game-plugins','android','windows','assets','docs','server','public','game-assets','.github'} or len(parts)==1 and path.suffix.lower() in {'.cmd','.md'})
        if not allowed or path.suffix.lower() in {'.env','.pem','.key','.sqlite','.db','.keystore','.p12','.pfx'} or any(word in path.name.lower() for word in ('private-key','secret','password','credentials')):
            raise ValueError('Arquivo local nao permitido na publicacao automatica: '+name)
        file=ROOT/path
        if file.is_symlink():raise ValueError('Link nao permitido: '+name)
        result[name]=digest(file) if file.is_file() else None
    return result


def versions():
    android=(ROOT/'android/nordeluna.patch').read_text(encoding='utf-8')
    pc=(ROOT/'.github/workflows/nordeluna-pc.yml').read_text(encoding='utf-8')
    name=re.search(r'(?m)^\+\s*versionName\s+"([\d.]+)"',android)[1]
    code=int(re.search(r'(?m)^\+\s*versionCode\s+(\d+)',android)[1])
    pcname=re.search(r'--version ([\d.]+)',pc)[1]
    catalog=json.loads((ROOT/'public/launcher/releases.json').read_text(encoding='utf-8'))
    if 'manifest' in catalog:catalog=json.loads(catalog['manifest'])
    pccode=max(catalog['channels']['stable']['windows']['code'],int(re.search(r'--code (\d+)',pc)[1]) if re.search(r'--code (\d+)',pc) else 130)
    def bump(value):
        bits=value.split('.');bits[-1]=str(int(bits[-1])+1);return '.'.join(bits)
    return dict(android=bump(name),android_code=code+1,pc=bump(pcname),pc_code=pccode+1)


def analyze(game):
    game=Path(game).resolve();inventory=core.inventory(game)
    if not content.BASE.is_file():raise ValueError('Prepare primeiro a base inicial do atualizador.')
    baseline=json.loads(content.BASE.read_text(encoding='utf-8'))
    old=dict(baseline['files'])
    for name in content.DATABASE_FILES:
        if name in baseline.get('compatibility',{}):old.setdefault(name,baseline['compatibility'][name])
    current=content.scan(game)
    touched_file=content.BASE.with_name('touched.json')
    touched=set(json.loads(touched_file.read_text(encoding='utf-8'))) if touched_file.is_file() else set()
    changes=[dict(path=name,change='Alterado' if name in old else 'Novo',size=(game/name).stat().st_size) for name in sorted(current) if current[name]!=old.get(name) or name in touched]
    removed=sorted((set(old)|touched)-set(current));code=reviewed_code()
    expected={k:v for k,v in baseline.get('compatibility',{}).items() if not content.allowed_path(k) and k!='Data/System.rxdata'}
    reasons=[]
    if code:reasons.append('Existem alteracoes no programa, plugins, servidor ou ferramentas.')
    if expected!=content.compatibility(game):reasons.append('Motor, plugins ou outras tabelas compiladas mudaram.')
    if removed:reasons.append('Arquivos da base foram removidos.')
    if sum(row['size'] for row in changes)>64*1024*1024 or len(changes)>500 or any(row['size']>16*1024*1024 for row in changes):
        reasons.append('O conjunto excede o limite dos pacotes rapidos; sera usada uma versao completa.')
    if not reasons and sum(len(zlib.compress((game/row['path']).read_bytes(),6)) for row in changes)>32*1024*1024:
        reasons.append('O pacote comprimido excede 32 MB; sera usada uma versao completa.')
    return dict(source=str(game),mode='full' if reasons else 'content',reasons=reasons,changes=changes,
                removed=removed,code=code,inventory=inventory,base_sha=digest(content.BASE),versions=versions())


def unchanged(plan):
    current=core.inventory(Path(plan['source']))
    # JSON persistence turns tuple values into lists.
    if {k:list(v) for k,v in current.items()}!={k:list(v) for k,v in plan['inventory'].items()} or reviewed_code()!=plan['code'] or digest(content.BASE)!=plan['base_sha']:
        raise ValueError('Os arquivos mudaram depois da previa. Clique em Conferir alteracoes novamente.')


def prepare_content(plan,title,notes,version):
    unchanged(plan)
    return content.build(version,title,notes,Path(plan['source']))


def release_sources(patch,android,pc,versions,digest_value,notes_name):
    old_android=re.search(r'Nordeluna-Android-arm64-v([\d.]+)\.apk',android)[1]
    old_pc=re.search(r'--version ([\d.]+)',pc)[1]
    android=android.replace(old_android,versions['android'])
    pc=pc.replace(old_pc,versions['pc'])
    patch,android,_=core.new_release_text(patch,android,digest_value)
    patch=re.sub(r'(?m)^(\+\s*versionName\s+")[\d.]+(")',lambda m:m[1]+versions['android']+m[2],patch)
    # Version code is monotonic; do not derive it from a display name.
    patch=re.sub(r'(?m)^(\+\s*versionCode\s+)\d+',lambda m:m[1]+str(versions['android_code']),patch)
    pc=re.sub(r'--version [\d.]+(?: --code \d+)?','--version '+versions['pc']+' --code '+str(versions['pc_code']),pc)
    for old in set(re.findall(r'docs/release-[\d.]+\.md',android+pc)):
        android=android.replace(old,notes_name);pc=pc.replace(old,notes_name)
    return patch,android,pc


def post(client,route,data):
    url='https://api.github.com/repos/'+core.REPOSITORY+'/'+route
    request=urllib.request.Request(url,json.dumps(data).encode(),method='POST',headers={'Authorization':'Bearer '+client.token,'User-Agent':'Nordeluna-Publisher','Content-Type':'application/json','Accept':'application/vnd.github+json'})
    with client.opener.open(request,timeout=60) as reply:return reply.status


def ensure_repository():
    if core.git('branch','--show-current')!='main':raise ValueError('A publicacao usa a branch main.')
    if core.git('remote','get-url','origin') not in ('https://github.com/'+core.REPOSITORY,'https://github.com/'+core.REPOSITORY+'.git','git@github.com:'+core.REPOSITORY+'.git'):
        raise ValueError('O origin nao corresponde ao Nordeluna.')
    core.git('fetch','origin','main')
    if int(core.git('rev-list','--count','HEAD..origin/main')):raise ValueError('O GitHub tem alteracoes novas. Sincronize o projeto antes de publicar.')


def prepare_full(plan,title,notes,audience,stop,notify):
    ensure_repository();unchanged(plan)
    client=core.GitHub()
    for workflow in ('nordeluna-pc.yml',core.WORKFLOW):
        if any(r['status']!='completed' for r in client.get('actions/workflows/'+workflow+'/runs?per_page=10')['workflow_runs']):
            raise ValueError('Ja existe uma build em andamento. Aguarde ou acompanhe a publicacao anterior.')
    STATE.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=STATE,prefix='full-') as tmp:
        tmp=Path(tmp);archive=tmp/'game.zip'
        original_base=content.BASE.read_bytes()
        touched=content.BASE.with_name('touched.json');original_touched=touched.read_bytes() if touched.is_file() else None
        index=Path(core.git('rev-parse','--git-path','index'))
        if not index.is_absolute():index=ROOT/index
        original_index=index.read_bytes() if index.is_file() else None
        backup=STATE/('backup-'+str(time.time_ns()));backup.mkdir()
        targets=['android/nordeluna.patch','.github/workflows/'+core.WORKFLOW,'.github/workflows/nordeluna-pc.yml','game-assets/sha256.txt']
        targets += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'game-assets').glob('game-assets.zip.part[0-9][0-9][0-9]'))]
        for name in targets:
            target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        committed=False;generated=[]
        try:
            digest_value=core.package_game(Path(plan['source']),archive,stop,notify)
            if reviewed_code()!=plan['code']:raise ValueError('O codigo mudou durante a preparacao. Confira novamente.')
            notes_name='docs/release-'+plan['versions']['android']+'.md'
            if (ROOT/notes_name).exists():raise ValueError('As notas desta versao ja existem; confira a numeracao antes de publicar.')
            patch,android,pc=release_sources((ROOT/targets[0]).read_text(encoding='utf-8'),(ROOT/targets[1]).read_text(encoding='utf-8'),(ROOT/targets[2]).read_text(encoding='utf-8'),plan['versions'],digest_value,notes_name)
            for name,text in zip(targets[:3],(patch,android,pc)):(ROOT/name).write_text(text,encoding='utf-8',newline='\n')
            parts=tmp/'parts';parts.mkdir();files=core.install_package(archive,digest_value,parts)
            old_parts=[p.relative_to(ROOT).as_posix() for p in (ROOT/'game-assets').glob('game-assets.zip.part[0-9][0-9][0-9]')]
            generated=old_parts+['game-assets/'+p.name for p in files]
            for name in generated:(ROOT/name).resolve().relative_to((ROOT/'game-assets').resolve())
            for name in old_parts:(ROOT/name).unlink()
            for file in [*files,parts/'sha256.txt']:shutil.copy2(file,ROOT/'game-assets'/file.name)
            generated=[p.relative_to(ROOT).as_posix() for p in (ROOT/'game-assets').glob('game-assets.zip.part[0-9][0-9][0-9]')]
            generated.append(notes_name);(ROOT/notes_name).write_text(title+'\n\n'+notes+'\n',encoding='utf-8')
            core.checkpoint(stop)
            paths=sorted(set(targets+generated+list(plan['code'])))
            checked=reviewed_code()
            if set(checked)-set(paths):raise ValueError('Surgiram arquivos fora da previa. Confira as alteracoes novamente.')
            for name,sha in plan['code'].items():
                if name not in targets+generated and checked.get(name)!=sha:raise ValueError('O codigo mudou depois da previa: '+name)
            core.git('add','--',*paths);core.git('commit','-m','Publish Nordeluna PC '+plan['versions']['pc']+' and Android '+plan['versions']['android'])
            committed=True
            state=dict(phase='prepared',commit=core.git('rev-parse','HEAD'),versions=plan['versions'],notes=notes_name,audience=audience,pc_dispatched=False)
            save_session(state);return state
        finally:
            if not committed:
                content.BASE.write_bytes(original_base)
                if original_touched is None:touched.unlink(missing_ok=True)
                else:touched.write_bytes(original_touched)
                for name in generated:
                    if (ROOT/name).is_file() and name not in targets:(ROOT/name).unlink()
                for name in targets:shutil.copy2(backup/name,ROOT/name)
                if original_index is None:index.unlink(missing_ok=True)
                else:index.write_bytes(original_index)


def finish_full(state,token,stop,notify):
    if state['phase']=='catalog_signed':
        if core.git('rev-parse','HEAD')!=state['catalog_commit']:raise ValueError('O catalogo local mudou desde a assinatura.')
        return publish_testers(state,token,notify)
    head=core.git('rev-parse','HEAD')
    if head!=state['commit']:
        # The finalizer can commit the signed catalogue and lose connectivity
        # during push. Recover only that exact child commit, never other edits.
        if state['audience']=='stable' and core.git('rev-parse','HEAD^')==state['commit'] and core.git('diff','--name-only','HEAD^','HEAD')=='public/launcher/releases.json' and (ROOT/'.cache/testers/publicacao-testers.json').is_file():
            core.git('push','origin','main');state.update(phase='catalog_signed',catalog_commit=head);save_session(state)
            return publish_testers(state,token,notify)
        raise ValueError('O projeto mudou desde a preparacao. Restaure o commit da publicacao antes de retomar.')
    client=core.GitHub()
    if state['phase']=='prepared':
        core.checkpoint(stop);notify('status','Enviando a versao completa de PC e Android...')
        core.git('push','origin','main');state['phase']='building';save_session(state)
    if not state.get('pc_dispatched'):
        existing=client.get('actions/workflows/nordeluna-pc.yml/runs?head_sha='+state['commit']+'&per_page=10')['workflow_runs']
        if not any(r['head_sha']==state['commit'] for r in existing):post(client,'actions/workflows/nordeluna-pc.yml/dispatches',{'ref':'main'})
        state['pc_dispatched']=True;save_session(state)
    start=time.monotonic()
    while True:
        core.checkpoint(stop);states=[];done=True
        for workflow in ('nordeluna-pc.yml',core.WORKFLOW):
            runs=client.get('actions/workflows/'+workflow+'/runs?head_sha='+state['commit']+'&per_page=10')['workflow_runs']
            run=next((r for r in runs if r['head_sha']==state['commit']),None)
            name='PC' if workflow=='nordeluna-pc.yml' else 'Android'
            states.append(name+': '+(run['status'] if run else 'aguardando'))
            if run:notify('url',run['html_url'])
            if run and run['status']=='completed' and run['conclusion']!='success':raise ValueError(name+' falhou. Consulte os logs e use Retomar depois de executar novamente a build do mesmo commit.')
            done=done and bool(run and run['status']=='completed' and run['conclusion']=='success')
        notify('status',' / '.join(states))
        if done:break
        if time.monotonic()-start>5400:raise ValueError('Acompanhamento pausado apos 90 minutos. Use Retomar para continuar.')
        stop.wait(15)
    core.checkpoint(stop)
    v=state['versions'];notify('status','Conferindo e assinando os downloads de PC e Android...')
    args=[sys.executable,str(ROOT/'scripts/finalize-client-release.py'),'--pc-tag','pc-'+v['pc'],'--android-tag','android-'+v['android'],'--pc-code',str(v['pc_code']),'--android-code',str(v['android_code']),'--pc-commit',state['commit'],'--android-commit',state['commit'],'--notes',str(ROOT/state['notes'])]
    args+=['--testers-only'] if state['audience']=='testers' else ['--publish']
    result=subprocess.run(args,cwd=ROOT,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError(result.stderr.decode('utf-8',errors='replace')[-2500:])
    state['phase']='catalog_signed';state['catalog_commit']=core.git('rev-parse','HEAD');save_session(state)
    publish_testers(state,token,notify)


def publish_testers(state,token,notify):
    payload=json.loads((ROOT/'.cache/testers/publicacao-testers.json').read_text(encoding='utf-8'))
    gifts=module('center_admin','gift-manager.py')
    with gifts.AdminSession(token) as session:session.publish({'action':'publish','payload':payload},'tester')
    state['phase']='complete';save_session(state)
    notify('status','PC e Android publicados. Os launchers ja podem consultar a nova versao.')


def resume(token,stop,notify):
    with core.exclusive_lock():
        state=read_session()
        if not state or state.get('phase')=='complete':raise ValueError('Nao existe uma publicacao pendente.')
        if state['phase']=='content_prepared':finish_content(state,token,stop,notify)
        else:finish_full(state,token,stop,notify)


def finish_content(state,token,stop,notify):
    core.checkpoint(stop)
    def progress(message):
        core.checkpoint(stop);notify('status',message)
    content.publish_package(token,Path(state['package']),progress,channel=state['audience'],expected_manifest=state['manifest_hash'])
    state['phase']='complete';save_session(state)
    notify('status','Pacote publicado para PC e Android. Os jogadores devem baixar e reiniciar o jogo.')


def deploy_server(token,notify):
    with core.exclusive_lock():
        packer=module('center_server_package','package-discloud.py')
        package=packer.package('nordeluna-online',ROOT/'build/publication-center/Nordeluna-Servidor.zip')
        deploy=module('center_server_deploy','discloud-local-deploy.py')
        deploy.deploy(token,package,lambda message,phase:notify('status',message))


def publish(plan,title,notes,version,audience,token,stop,notify):
    with core.exclusive_lock():
        pending=read_session()
        if pending and pending.get('phase')!='complete':raise ValueError('Existe uma publicacao pendente. Use Retomar.')
        if plan['mode']=='content':
            core.checkpoint(stop);notify('status','Gerando um pacote para PC e Android...')
            if version==0:
                gifts=module('center_version_admin','gift-manager.py')
                with gifts.AdminSession(token) as session:remote=session.publish({'action':'packages'},'update')
                version=max([r['version'] for r in remote.get('packages',[])]+[pending.get('version',0)])+1
            package=prepare_content(plan,title,notes,version)
            raw=content.load_package(package)[0]
            state=dict(phase='content_prepared',package=str(package),manifest_hash=hashlib.sha256(raw.encode()).hexdigest(),audience=audience,version=version)
            save_session(state);finish_content(state,token,stop,notify)
        else:
            state=prepare_full(plan,title,notes,audience,stop,notify)
            finish_full(state,token,stop,notify)
