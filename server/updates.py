"""Signed cumulative map/resource packs, streamed in bounded chunks from SQLite."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import time
try:
    from gifts import check
except ModuleNotFoundError:
    from server.gifts import check

CHUNK=16384
MAX_PACK=32*1024*1024
MAX_FILE=16*1024*1024
DIGEST_INFO=bytes.fromhex('3031300d060960864801650304020105000420')


def allowed_path(path):
    if not isinstance(path,str) or len(path)>220 or '\\' in path or ':' in path or any(ord(c)<32 for c in path):return False
    parts=path.split('/')
    if any(not p or p in ('.','..') or p.startswith('.') or p.endswith((' ','.')) for p in parts):return False
    if path in ('Data/MapInfos.rxdata','Data/Tilesets.rxdata','Data/CommonEvents.rxdata','Data/map_metadata.dat','Data/map_connections.dat','Data/encounters.dat'):return True
    if re.fullmatch(r'Data/Map[0-9]{3,6}\.rxdata',path):return True
    suffix=PurePosixPath(path).suffix.lower()
    return (parts[0]=='Graphics' and len(parts)>=3 and suffix in ('.png','.jpg','.jpeg')) or (parts[0]=='Audio' and len(parts)>=3 and suffix in ('.ogg','.mp3','.wav','.mid','.midi')) or (parts[0]=='Movies' and len(parts)>=2 and suffix=='.mp4')


def validate_manifest(raw):
    check(isinstance(raw,str) and len(raw.encode())<=150000,'Manifesto grande demais.')
    data=json.loads(raw)
    check(isinstance(data,dict) and set(data)=={'version','base','title','notes','files'},'Manifesto invalido.')
    check(type(data['version']) is int and 1<=data['version']<=999999,'Versao do pacote invalida.')
    check(isinstance(data['base'],str) and re.fullmatch(r'[0-9a-f]{32}',data['base']),'Base invalida.')
    check(isinstance(data['title'],str) and 1<=len(data['title'])<=72,'Titulo invalido.')
    check(isinstance(data['notes'],str) and len(data['notes'])<=1000,'Novidades excedem 1000 caracteres.')
    check(isinstance(data['files'],list) and 1<=len(data['files'])<=500,'Pacote deve ter 1 a 500 arquivos.')
    paths=set();size=0;unpacked=0
    for row in data['files']:
        check(isinstance(row,dict) and set(row)=={'path','size','sha256','blob','packed_size','base_sha256'},'Arquivo invalido.')
        path=row['path'];check(allowed_path(path) and path.casefold() not in paths,'Caminho invalido ou repetido no pacote.');paths.add(path.casefold())
        for key in ('sha256','blob'):check(isinstance(row[key],str) and re.fullmatch(r'[0-9a-f]{64}',row[key]),'Hash invalido.')
        check(row['base_sha256'] is None or (isinstance(row['base_sha256'],str) and re.fullmatch(r'[0-9a-f]{64}',row['base_sha256'])),'Hash da base invalido.')
        check(type(row['size']) is int and 0<row['size']<=MAX_FILE,'Arquivo excede 16 MB.')
        check(type(row['packed_size']) is int and 0<row['packed_size']<=MAX_FILE,'Arquivo comprimido invalido.')
        size+=row['packed_size'];unpacked+=row['size']
    check(size<=MAX_PACK and unpacked<=64*1024*1024,'Pacote excede 32 MB comprimido ou 64 MB extraido.')
    return data


def verify_signature(raw,signature,key):
    check(isinstance(signature,str) and re.fullmatch(r'[0-9a-f]{512}',signature),'Assinatura invalida.')
    encoded=DIGEST_INFO+hashlib.sha256(raw.encode()).digest()
    expected=b'\x00\x01'+b'\xff'*(256-len(encoded)-3)+b'\x00'+encoded
    check(pow(int(signature,16),65537,int(key['n'],16)).to_bytes(256,'big')==expected,'Pacote nao assinado pelo criador do jogo.')


class UpdateService:
    def setup_updates(self):
        self.db.execute('CREATE TABLE IF NOT EXISTS update_chunks(hash TEXT,part INTEGER,data BLOB NOT NULL,PRIMARY KEY(hash,part))')
        self.db.execute('CREATE TABLE IF NOT EXISTS update_packages(version INTEGER PRIMARY KEY,base TEXT NOT NULL,manifest TEXT NOT NULL,signature TEXT NOT NULL,published INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS update_drafts(version INTEGER PRIMARY KEY,manifest TEXT NOT NULL,signature TEXT NOT NULL)')
        self.db.execute("CREATE TABLE IF NOT EXISTS update_releases(version INTEGER PRIMARY KEY,channel TEXT NOT NULL CHECK(channel IN ('stable','testers')))" )
        self.db.execute('CREATE TABLE IF NOT EXISTS update_testers(account TEXT PRIMARY KEY,created INTEGER NOT NULL)')
        self._update_blob_sets={}

    def update_is_tester(self,request):
        if 'account' not in request:return False
        account=self.account(request)['id']
        if self.db.execute('SELECT 1 FROM update_testers WHERE account=?',(account,)).fetchone():return True
        if isinstance(request.get('tester'),dict):
            _,bound=self.tester_auth(request['tester'])
            return bound==account
        return False

    def update_signing_key(self):
        return json.loads(Path(__file__).with_name('content-key.json').read_text(encoding='utf-8'))

    def update_action(self,request):
        tester=self.update_is_tester(request)
        if request['action']=='update_manifest':
            row=self.db.execute("SELECT p.manifest,p.signature,COALESCE(r.channel,'stable') FROM update_packages p LEFT JOIN update_releases r ON r.version=p.version WHERE p.base=? AND (COALESCE(r.channel,'stable')='stable' OR ?) ORDER BY p.version DESC LIMIT 1",(str(request.get('base'))[:32],tester)).fetchone()
            return dict(manifest=row[0],signature=row[1],channel=row[2]) if row else dict(manifest=None)
        check(request['action']=='update_chunk','Acao de atualizacao desconhecida.')
        version,blob,part=request.get('version'),request.get('blob'),request.get('part')
        check(type(version) is int and type(part) is int and 0<=part<1024 and isinstance(blob,str) and re.fullmatch(r'[0-9a-f]{64}',blob),'Bloco invalido.')
        # Always authorize against SQLite: console edits happen in another
        # process, and revoking a tester must invalidate an ongoing download.
        release=self.db.execute("SELECT COALESCE(r.channel,'stable') FROM update_packages p LEFT JOIN update_releases r ON r.version=p.version WHERE p.version=?",(version,)).fetchone()
        check(release and (release[0]=='stable' or tester),'Pacote reservado ao grupo de testers.')
        if version not in self._update_blob_sets:
            package=self.db.execute('SELECT manifest FROM update_packages WHERE version=?',(version,)).fetchone()
            check(package,'Pacote nao publicado.')
            if len(self._update_blob_sets)>=8:self._update_blob_sets.clear()
            self._update_blob_sets[version]={row['blob'] for row in json.loads(package[0])['files']}
        check(blob in self._update_blob_sets[version],'Arquivo fora do pacote publicado.')
        row=self.db.execute('SELECT data FROM update_chunks WHERE hash=? AND part=?',(blob,part)).fetchone()
        check(row,'Bloco nao encontrado. Consulte novamente as atualizacoes.')
        return dict(data=bytes(row[0]).hex(),part=part)

    def update_admin(self,request):
        with self.lock,self.db:
            action=request.get('action')
            if action=='capabilities':return dict(tester_releases=True)
            if action in ('testers_get','testers_set'):
                if action=='testers_set':
                    names=request.get('testers')
                    check(isinstance(names,list) and len(names)<=100 and all(isinstance(n,str) and 1<=len(n.strip())<=32 for n in names),'Informe ate 100 nicks ou IDs existentes.')
                    identities=set()
                    for name in names:
                        row=self.db.execute('SELECT id FROM accounts WHERE normalized=? OR id=?',(name.strip().casefold(),name.strip())).fetchone()
                        check(row,'Conta nao encontrada: '+name[:32])
                        identities.add(row[0])
                    self.db.execute('DELETE FROM update_testers')
                    self.db.executemany('INSERT INTO update_testers VALUES(?,?)',[(value,int(time.time())) for value in identities])
                return dict(testers=[dict(account_id=r[0],nickname=r[1]) for r in self.db.execute('SELECT t.account,a.nickname FROM update_testers t JOIN accounts a ON a.id=t.account ORDER BY a.normalized')])
            if action=='list':
                return dict(packages=[dict(version=r[0],base=r[1],published=r[2],channel=r[3],title=json.loads(r[4])['title'],files=json.loads(r[4])['files'],signature=r[5]) for r in self.db.execute("SELECT p.version,p.base,p.published,COALESCE(r.channel,'stable'),p.manifest,p.signature FROM update_packages p LEFT JOIN update_releases r ON r.version=p.version ORDER BY p.version DESC LIMIT 20")])
            if action=='promote':
                version=request.get('version');check(type(version) is int,'Versao invalida.')
                row=self.db.execute('SELECT signature,base FROM update_packages WHERE version=?',(version,)).fetchone()
                check(row and row[0]==request.get('signature'),'Pacote mudou ou nao foi encontrado. Atualize a lista.')
                newer=self.db.execute("SELECT 1 FROM update_packages p LEFT JOIN update_releases r ON r.version=p.version WHERE p.base=? AND p.version>? AND COALESCE(r.channel,'stable')='stable'",(row[1],version)).fetchone()
                check(not newer,'Ja existe um pacote publico mais recente desta base.')
                self.db.execute("INSERT INTO update_releases VALUES(?,'stable') ON CONFLICT(version) DO UPDATE SET channel='stable'",(version,))
                return dict(promoted=version)
            key=self.update_signing_key()
            if action=='begin':
                channel=request.get('channel','stable');check(channel in ('stable','testers'),'Publico de atualizacao invalido.')
                raw,signature=request.get('manifest'),request.get('signature')
                manifest=validate_manifest(raw);verify_signature(raw,signature,key)
                check(manifest['base']==key['base'],'Pacote de outra base do aplicativo.')
                completed=self.db.execute('SELECT manifest,signature FROM update_packages WHERE version=?',(manifest['version'],)).fetchone()
                if completed:
                    check(tuple(completed)==(raw,signature),'Esta versao ja foi publicada com outro pacote.')
                    old_channel=self.db.execute('SELECT channel FROM update_releases WHERE version=?',(manifest['version'],)).fetchone()
                    check((old_channel[0] if old_channel else 'stable')==channel,'Use Liberar para todos para promover um pacote de teste.')
                    return dict(published=manifest['version'],channel=channel)
                previous=self.db.execute('SELECT COALESCE(MAX(version),0) FROM update_packages').fetchone()[0]
                check(manifest['version']>previous,'A versao deve ser maior que a ultima publicada.')
                old=self.db.execute('SELECT manifest,signature FROM update_drafts WHERE version=?',(manifest['version'],)).fetchone()
                check(not old or tuple(old)==(raw,signature),'Esta versao ja tem outro envio pendente. Use outro numero.')
                old_channel=self.db.execute('SELECT channel FROM update_releases WHERE version=?',(manifest['version'],)).fetchone()
                check(not old_channel or old_channel[0]==channel,'Este envio ja foi iniciado para outro publico.')
                check(old or self.db.execute('SELECT COUNT(*) FROM update_drafts').fetchone()[0]<3,'Ha tres envios pendentes. Retome um deles antes de criar outro.')
                self.db.execute('INSERT OR IGNORE INTO update_drafts VALUES(?,?,?)',(manifest['version'],raw,signature))
                self.db.execute('INSERT OR IGNORE INTO update_releases VALUES(?,?)',(manifest['version'],channel))
                return dict(ready=True)
            version=request.get('version');check(type(version) is int,'Versao invalida.')
            if action=='finish' and self.db.execute('SELECT 1 FROM update_packages WHERE version=?',(version,)).fetchone():
                return dict(published=version)
            draft=self.db.execute('SELECT manifest,signature FROM update_drafts WHERE version=?',(version,)).fetchone()
            check(draft,'Envio nao iniciado.')
            manifest=validate_manifest(draft[0])
            if action=='put':
                blob,part,hexdata=request.get('blob'),request.get('part'),request.get('data')
                row=next((r for r in manifest['files'] if r['blob']==blob),None)
                check(row and type(part) is int and 0<=part<(row['packed_size']+CHUNK-1)//CHUNK,'Bloco fora do pacote.')
                check(isinstance(hexdata,str) and re.fullmatch(r'[0-9a-f]{2,32768}',hexdata) and len(hexdata)%2==0,'Dados invalidos.')
                data=bytes.fromhex(hexdata)
                check(len(data)==min(CHUNK,row['packed_size']-part*CHUNK),'Tamanho do bloco incorreto.')
                old=self.db.execute('SELECT data FROM update_chunks WHERE hash=? AND part=?',(blob,part)).fetchone()
                check(not old or bytes(old[0])==data,'Bloco existente difere; envio cancelado.')
                self.db.execute('INSERT OR IGNORE INTO update_chunks VALUES(?,?,?)',(blob,part,data))
                return dict(received=True)
            check(action=='finish','Acao administrativa desconhecida.')
            verify_signature(draft[0],draft[1],key)
            for row in manifest['files']:
                digest=hashlib.sha256();length=0;parts=0
                for part,chunk in self.db.execute('SELECT part,data FROM update_chunks WHERE hash=? ORDER BY part',(row['blob'],)):
                    check(part==parts,'Pacote incompleto.');digest.update(chunk);length+=len(chunk);parts+=1
                check(length==row['packed_size'] and digest.hexdigest()==row['blob'],'Arquivo incompleto ou corrompido.')
            # Nothing is visible to clients before this single commit.
            latest=self.db.execute('SELECT COALESCE(MAX(version),0) FROM update_packages').fetchone()[0]
            check(version>latest,'Outro pacote mais novo ja foi publicado.')
            self.db.execute('INSERT INTO update_packages VALUES(?,?,?,?,?)',(version,manifest['base'],draft[0],draft[1],int(time.time())))
            self.db.execute('DELETE FROM update_drafts WHERE version=?',(version,))
            # Keep three per audience so many tester releases cannot evict the
            # stable package still used by the rest of the community.
            retained_versions=set()
            for audience in ('stable','testers'):
                retained_versions.update(r[0] for r in self.db.execute("SELECT p.version FROM update_packages p LEFT JOIN update_releases r ON r.version=p.version WHERE COALESCE(r.channel,'stable')=? ORDER BY p.version DESC LIMIT 3",(audience,)))
            for (old_version,) in self.db.execute('SELECT version FROM update_packages').fetchall():
                if old_version not in retained_versions:self.db.execute('DELETE FROM update_packages WHERE version=?',(old_version,))
            self.db.execute('DELETE FROM update_releases WHERE version NOT IN (SELECT version FROM update_packages UNION SELECT version FROM update_drafts)')
            retained=set()
            for (raw,) in self.db.execute('SELECT manifest FROM update_packages UNION ALL SELECT manifest FROM update_drafts'):
                retained.update(r['blob'] for r in json.loads(raw)['files'])
            for (digest,) in self.db.execute('SELECT DISTINCT hash FROM update_chunks').fetchall():
                if digest not in retained:self.db.execute('DELETE FROM update_chunks WHERE hash=?',(digest,))
            self._update_blob_sets.clear()
            return dict(published=version)
