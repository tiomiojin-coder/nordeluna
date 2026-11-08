"""Build signed cumulative content packs using the project's local base snapshot."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import queue
import secrets
import sys
import threading
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from updater_core import DEFAULT_GAME
from server.updates import allowed_path,validate_manifest,verify_signature,CHUNK,DIGEST_INFO

PRIVATE=ROOT/'.cache/content-updates/private-key.json'
BASE=ROOT/'.cache/content-updates/base.json'
PUBLIC=ROOT/'server/content-key.json'


def prime():
    small=(3,5,7,11,13,17,19,23,29,31,37,41,43,47)
    while True:
        n=secrets.randbits(1024)|(1<<1023)|1
        if any(n%p==0 for p in small):continue
        d=n-1;s=0
        while d%2==0:d//=2;s+=1
        for _ in range(40):
            a=secrets.randbelow(n-3)+2;x=pow(a,d,n)
            if x in (1,n-1):continue
            for _ in range(s-1):
                x=pow(x,2,n)
                if x==n-1:break
            else:break
        else:return n


def signing_key():
    if PRIVATE.is_file():return json.loads(PRIVATE.read_text(encoding='utf-8'))
    if PUBLIC.is_file():raise ValueError('A chave privada original nao foi encontrada. Restaure o backup de .cache/content-updates antes de assinar novos pacotes.')
    while True:
        p,q=prime(),prime();n=p*q;phi=(p-1)*(q-1)
        if p!=q and n.bit_length()==2048 and math.gcd(65537,phi)==1:break
    data=dict(n=f'{n:x}',d=f'{pow(65537,-1,phi):x}')
    PRIVATE.parent.mkdir(parents=True,exist_ok=True);PRIVATE.write_text(json.dumps(data),encoding='utf-8')
    return data


def scan(game):
    result={}
    for folder in ('Data','Graphics','Audio','Movies'):
        directory=game/folder
        if not directory.is_dir():continue
        for path in directory.rglob('*'):
            relative=path.relative_to(game).as_posix()
            if path.is_file() and not path.is_symlink() and allowed_path(relative):
                with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                result[relative]=digest
    return result


def compatibility(game):
    return {p.relative_to(game).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (game/'Data').iterdir() if p.is_file() and p.name!='System.rxdata' and not allowed_path(p.relative_to(game).as_posix()) and p.suffix in ('.dat','.rxdata')}


def capture_apk_base(archive_path):
    """Freeze precisely the checked APK source ZIP, not a moving editor folder."""
    with zipfile.ZipFile(archive_path) as archive:
        lookup={entry.filename.removeprefix('./'):entry for entry in archive.infolist()}
        if 'Plugins/Nordeluna Online/028_ContentUpdates.rb' not in lookup:return False
        if not BASE.is_file():raise ValueError('Prepare a base do atualizador antes de empacotar o APK.')
        data=json.loads(BASE.read_text(encoding='utf-8'));files={};database={}
        source=archive.read(lookup['Plugins/Nordeluna Online/028_ContentUpdates.rb']).decode('utf-8')
        if data['base'] not in source:raise ValueError('O plugin do APK tem outra base. Sincronize o plugin antes de empacotar.')
        for entry in archive.infolist():
            name=entry.filename.removeprefix('./')
            runtime=allowed_path(name)
            compatible=name.startswith('Data/') and '/' not in name[5:] and name!='Data/System.rxdata' and name.endswith(('.dat','.rxdata')) and not runtime
            if not runtime and not compatible:continue
            with archive.open(entry) as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            (files if runtime else database)[name]=digest
        data.update(files=files,compatibility=database)
    temporary=BASE.with_suffix('.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(BASE)
    BASE.with_name('touched.json').write_text('[]',encoding='utf-8')
    return True


def initialize(game=DEFAULT_GAME):
    key=signing_key()
    if not BASE.is_file():
        files=scan(game)
        data=dict(base=secrets.token_hex(16),files=files)
        BASE.parent.mkdir(parents=True,exist_ok=True);BASE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    base=json.loads(BASE.read_text(encoding='utf-8'))
    if 'compatibility' not in base:
        base['compatibility']=compatibility(game)
        BASE.write_text(json.dumps(base,ensure_ascii=False,indent=2),encoding='utf-8')
    public=dict(n=key['n'],base=base['base'])
    if PUBLIC.is_file() and json.loads(PUBLIC.read_text(encoding='utf-8'))!=public:
        raise ValueError('A chave ou base atual difere da incorporada no aplicativo.')
    PUBLIC.write_text(json.dumps(public,indent=2)+'\n',encoding='utf-8')
    ruby=ROOT/'game-plugins/Nordeluna Online/028_ContentUpdates.rb'
    source=ruby.read_text(encoding='utf-8')
    source=source.replace('__PUBLIC_MODULUS__',key['n']).replace('__CONTENT_BASE__',base['base'])
    ruby.write_text(source,encoding='utf-8')
    return public


def build(version,title,notes,game=DEFAULT_GAME,output=None):
    if not BASE.is_file() or not PRIVATE.is_file():raise ValueError('Prepare a base inicial antes de gerar pacotes.')
    baseline=json.loads(BASE.read_text(encoding='utf-8'));key=signing_key();files=[];blobs={}
    expected={name:digest for name,digest in baseline.get('compatibility',compatibility(game)).items() if name!='Data/System.rxdata'}
    if expected!=compatibility(game):
        raise ValueError('Plugins, scripts ou banco de especies/itens mudaram. Esta alteracao requer um APK novo; mapas e recursos podem ser enviados depois de preparar a nova base.')
    touched_path=BASE.with_name('touched.json')
    touched=set(json.loads(touched_path.read_text(encoding='utf-8'))) if touched_path.is_file() else set()
    current=scan(game)
    for name,digest in sorted(current.items()):
        before=baseline['files'].get(name)
        if digest==before and name not in touched:continue
        raw=(game/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('O jogo mudou durante a preparacao. Salve e feche o editor e tente novamente.')
        packed=zlib.compress(raw,6);blob=hashlib.sha256(packed).hexdigest()
        files.append(dict(path=name,size=len(raw),sha256=digest,blob=blob,packed_size=len(packed),base_sha256=before));blobs[blob]=packed
    missing=set(baseline['files'])-set(current)
    if missing:raise ValueError('Arquivos da base foram removidos. O atualizador nao apaga arquivos; restaure-os ou gere outro APK: '+', '.join(sorted(missing)[:5]))
    if not files:raise ValueError('Nenhum mapa ou recurso mudou em relacao a base inicial.')
    manifest=dict(version=version,base=baseline['base'],title=title,notes=notes,files=files)
    raw=json.dumps(manifest,ensure_ascii=False,separators=(',',':'));validate_manifest(raw)
    encoded=DIGEST_INFO+hashlib.sha256(raw.encode()).digest()
    block=b'\x00\x01'+b'\xff'*(256-len(encoded)-3)+b'\x00'+encoded
    signature=f'{pow(int.from_bytes(block,"big"),int(key["d"],16),int(key["n"],16)):0512x}'
    verify_signature(raw,signature,dict(n=key['n']))
    for row in files:
        with (game/row['path']).open('rb') as stream:after=hashlib.file_digest(stream,'sha256').hexdigest()
        if after!=row['sha256']:raise ValueError('O jogo mudou durante a preparacao. Salve e feche o editor e tente novamente.')
    output=output or ROOT/'build/content-updates'/f'Nordeluna-conteudo-{version}.zip';output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json',raw.encode());archive.writestr('signature.txt',signature)
        for name,data in blobs.items():archive.writestr('blobs/'+name,data)
    touched_path.write_text(json.dumps(sorted(touched|{row['path'] for row in files}),ensure_ascii=False),encoding='utf-8')
    return output


def load_package(path):
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist()
        if len(infos)>502 or sum(i.file_size for i in infos)>33*1024*1024 or archive.testzip():raise ValueError('Pacote invalido.')
        raw=archive.read('manifest.json').decode('utf-8');signature=archive.read('signature.txt').decode('ascii');manifest=validate_manifest(raw)
        verify_signature(raw,signature,json.loads(PUBLIC.read_text(encoding='utf-8')))
        expected={'manifest.json','signature.txt'}|{'blobs/'+r['blob'] for r in manifest['files']}
        if set(archive.namelist())!=expected or len(archive.namelist())!=len(expected):raise ValueError('Arquivos inesperados no pacote.')
        blobs={}
        for row in manifest['files']:
            packed=archive.read('blobs/'+row['blob'])
            if len(packed)!=row['packed_size'] or hashlib.sha256(packed).hexdigest()!=row['blob']:raise ValueError('Bloco corrompido.')
            blobs[row['blob']]=packed
    return raw,signature,manifest,blobs


def publish_package(token,path,progress=lambda text:None,channel='testers',expected_manifest=None):
    spec=importlib.util.spec_from_file_location('package_gifts',ROOT/'scripts/gift-manager.py');manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(manager)
    raw,signature,manifest,blobs=load_package(path)
    if expected_manifest is not None and hashlib.sha256(raw.encode()).hexdigest()!=expected_manifest:
        raise ValueError('O pacote mudou depois da previa. Confira novamente antes de publicar.')
    # Reuse a single connection context/token in memory; no server restart.
    with manager.AdminSession(token) as session:
        capabilities=session.publish(dict(action='capabilities'),'update')
        if not capabilities.get('tester_releases'):raise ValueError('Atualize o servidor para 0.9.1 antes de publicar pacotes.')
        begun=session.publish(dict(action='begin',manifest=raw,signature=signature,channel=channel),'update')
        if begun.get('published'):return begun
        total=sum((len(blob)+CHUNK-1)//CHUNK for blob in blobs.values());count=0
        for digest,blob in blobs.items():
            for part,start in enumerate(range(0,len(blob),CHUNK)):
                session.publish(dict(action='put',version=manifest['version'],blob=digest,part=part,data=blob[start:start+CHUNK].hex()),'update')
                count+=1;progress(f'Enviando mapas e recursos: {count}/{total} blocos')
        return session.publish(dict(action='finish',version=manifest['version']),'update')


def make_panel(parent,root,status,token):
    import tkinter as tk
    from tkinter import ttk,filedialog
    ttk.Label(parent,text='A base inicial ja vem preparada para o primeiro APK com atualizador.\nDepois de editar e salvar o projeto, gere um pacote cumulativo das alteracoes.\nInclui mapas, eventos dos mapas, tilesets, imagens, audio e videos compativeis.\nMudancas no motor, plugins Ruby e novas especies ainda exigem outro APK.',wraplength=900).pack(anchor='w',pady=8)
    line=ttk.Frame(parent);line.pack(fill='x',pady=10)
    ttk.Label(line,text='Versao do pacote:').pack(side='left');version=tk.StringVar(value='1');ttk.Entry(line,textvariable=version,width=9).pack(side='left',padx=8)
    ttk.Label(line,text='Titulo:').pack(side='left');title=tk.StringVar(value='Novidades de Nordeluna');ttk.Entry(line,textvariable=title,width=40).pack(side='left',padx=8)
    ttk.Label(parent,text='Novidades para os jogadores:').pack(anchor='w')
    notes=tk.Text(parent,height=5,wrap='word');notes.pack(fill='x',pady=6)
    package=tk.StringVar();ttk.Entry(parent,textvariable=package).pack(fill='x',pady=8)
    audience=ttk.Frame(parent);audience.pack(fill='x',pady=5)
    ttk.Label(audience,text='Disponibilizar para:').pack(side='left')
    channel=tk.StringVar(value='Testers')
    ttk.Combobox(audience,textvariable=channel,values=['Testers','Todos'],state='readonly',width=16).pack(side='left',padx=8)
    ttk.Label(audience,text='Cadastre os nicks autorizados na aba Testers.').pack(side='left')
    events=queue.Queue();busy=False
    def work(action,approved=None,chosen_path=None,chosen_channel=None):
        nonlocal busy
        if busy:return
        secret=token.get().strip()
        if action=='publish' and not secret:status.set('Informe o token Discloud no campo mascarado.');return
        try:v=int(version.get())
        except ValueError:status.set('Versao deve ser um numero inteiro.');return
        chosen=chosen_path or package.get();label=title.get();description=notes.get('1.0','end').strip();busy=True
        status.set('Preparando pacote...' if action=='build' else 'Enviando pacote ao servidor...')
        def task():
            try:
                if action=='build':events.put(('built',str(build(v,label,description))))
                else:events.put(('published',publish_package(secret,Path(chosen),lambda message:events.put(('progress',message)),channel=chosen_channel,expected_manifest=approved)))
            except Exception as error:events.put(('error',str(error).replace(secret,'[oculto]') if secret else str(error)))
        threading.Thread(target=task,daemon=True).start()
    buttons=ttk.Frame(parent);buttons.pack(fill='x',pady=8)
    ttk.Button(buttons,text='1. Gerar pacote das alteracoes',command=lambda:work('build')).pack(side='left')
    def browse():
        path=filedialog.askopenfilename(parent=root,filetypes=[('Pacote Nordeluna','*.zip')])
        if path:package.set(path)
    ttk.Button(buttons,text='Abrir pacote existente',command=browse).pack(side='left',padx=8)
    def preview_publish():
        if busy:return
        try:
            spec=importlib.util.spec_from_file_location('pack_review',ROOT/'scripts/publication-tools.py');review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
            chosen=package.get();raw,_,manifest,_=load_package(Path(chosen));selected='testers' if channel.get()=='Testers' else 'stable'
            if review.show_preview(root,review.package_diff(manifest),'Previa do pacote',f"Pacote {manifest['version']}: {manifest['title']} / Publico: {channel.get()}",confirm='Publicar para '+channel.get()):
                work('publish',hashlib.sha256(raw.encode()).hexdigest(),chosen,selected)
        except Exception as error:status.set('Falha: '+str(error))
    ttk.Button(buttons,text='2. Conferir e publicar',command=preview_publish).pack(side='left')
    def poll():
        nonlocal busy
        while not events.empty():
            kind,value=events.get()
            if kind!='progress':busy=False
            if kind=='built':package.set(value);status.set('Pacote pronto. Publique para disponibilizar no menu Online do jogo.')
            elif kind=='published':status.set('Pacote publicado no publico selecionado. A aba Testers permite liberar para todos depois.')
            elif kind=='error':status.set('Falha: '+value)
            else:status.set(value)
        root.after(150,poll)
    poll()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--initialize',action='store_true');parser.add_argument('--capture-apk',type=Path);parser.add_argument('--version',type=int);parser.add_argument('--title',default='Novidades de Nordeluna');parser.add_argument('--notes',default='')
    args=parser.parse_args()
    if args.initialize:initialize();print('Base e chave publica preparadas. Chave privada somente em .cache/content-updates/.')
    elif args.capture_apk:print('Base registrada do pacote APK.' if capture_apk_base(args.capture_apk) else 'Pacote sem atualizador; base nao alterada.')
    elif args.version:print(build(args.version,args.title,args.notes))
