"""Single-use tester invitations. Unlock material is never served publicly."""
import hashlib
import json
import re
import secrets
import time

try:
    from gifts import check
    from updates import verify_signature
except ModuleNotFoundError:
    from server.gifts import check
    from server.updates import verify_signature


def digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


class TesterService:
    def setup_tester_access(self):
        self.db.execute('CREATE TABLE IF NOT EXISTS tester_access(id TEXT PRIMARY KEY,label TEXT NOT NULL,code_hash TEXT UNIQUE NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,claimed INTEGER NOT NULL DEFAULT 0,device TEXT,token_hash TEXT,account TEXT)')
        self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS tester_access_token ON tester_access(token_hash)')
        self.db.execute('CREATE TABLE IF NOT EXISTS tester_catalog(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL)')

    def tester_admin(self, request):
        with self.lock, self.db:
            action=request.get('action')
            if action=='create':
                label=request.get('label','').strip();days=request.get('days',30)
                check(1<=len(label)<=48 and type(days) is int and 1<=days<=365,'Informe um nome e validade de 1 a 365 dias.')
                code='NLT-'+secrets.token_hex(16).upper();identity=secrets.token_hex(16);now=int(time.time())
                self.db.execute('INSERT INTO tester_access(id,label,code_hash,created,expires) VALUES(?,?,?,?,?)',(identity,label,digest(code),now,now+days*86400))
                return dict(id=identity,invitation=code)  # Plain code is shown once; never stored.
            if action=='revoke':
                target=self.db.execute('SELECT account FROM tester_access WHERE id=?',(request.get('id'),)).fetchone()
                check(target,'Convite nao encontrado.')
                self.db.execute('UPDATE tester_access SET revoked=1 WHERE id=?',(request['id'],))
                if target[0]:self.db.execute('DELETE FROM update_testers WHERE account=?',(target[0],))
                return dict(revoked=True)
            if action=='list':
                return dict(invitations=[dict(zip(('id','label','created','expires','revoked','claimed','account'),r)) for r in self.db.execute('SELECT id,label,created,expires,revoked,claimed,account FROM tester_access ORDER BY created DESC LIMIT 500')])
            if action=='publish':
                payload=request.get('payload');check(isinstance(payload,dict) and set(payload)=={'catalog','keys'},'Publicacao invalida.')
                outer=payload['catalog'];check(isinstance(outer,dict),'Catalogo invalido.')
                raw=outer.get('manifest');check(isinstance(raw,str) and len(raw)<180000,'Catalogo grande demais.')
                verify_signature(raw,outer.get('signature'),self.update_signing_key())
                data=json.loads(raw);check(data.get('schema')==1,'Schema invalido.')
                channels=data.get('channels',{});check(set(channels)=={'testers'},'Somente o canal testers pode ser publicado aqui.')
                keys=payload['keys'];check(isinstance(keys,dict) and set(keys)==set(channels['testers']),'Chaves incompletas.')
                for platform,row in channels['testers'].items():
                    check(platform in ('windows','android') and isinstance(row,dict),'Plataforma invalida.')
                    check(row.get('encrypted') is True and isinstance(row.get('plain'),dict),'Pacote de testes precisa estar criptografado.')
                    check(isinstance(keys[platform],str) and re.fullmatch('[0-9a-f]{64}',keys[platform]),'Chave de pacote invalida.')
                    for spec in (row,row['plain']):
                        check(type(spec.get('size')) is int and 0<spec['size']<=3*1024**3 and isinstance(spec.get('sha256'),str) and re.fullmatch('[0-9a-f]{64}',spec['sha256']),'Tamanho ou hash invalido.')
                    check(isinstance(row.get('url'),str) and row['url'].startswith('https://github.com/tiomiojin-coder/nordeluna/releases/download/') and row['url'].endswith('.locked'),'Download de testes invalido.')
                    check(type(row.get('code')) is int and row['code']>0 and isinstance(row.get('compatibility'),str) and row['compatibility'].endswith('-testers'),'Versao do cliente invalida.')
                old=self.db.execute('SELECT payload FROM tester_catalog WHERE id=1').fetchone()
                if old:
                    previous=json.loads(json.loads(old[0])['catalog']['manifest'])['channels']['testers']
                    for platform,row in channels['testers'].items():
                        before=previous.get(platform)
                        check(not before or row['code']>before['code'] or (row['code']==before['code'] and row['sha256']==before['sha256']),'A publicacao nao pode substituir uma revisao por outro pacote ou voltar a uma revisao antiga.')
                self.db.execute('INSERT INTO tester_catalog VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(json.dumps(payload,separators=(',',':')),))
                return dict(published=True)
            check(False,'Acao de testers desconhecida.')

    def tester_auth(self, credentials):
        check(isinstance(credentials,dict),'Ative o acesso de tester no launcher.')
        token,device=credentials.get('token',''),credentials.get('device','')
        check(isinstance(token,str) and re.fullmatch('[0-9a-f]{64}',token) and isinstance(device,str) and re.fullmatch('[0-9a-f]{32}',device),'Acesso de tester invalido.')
        row=self.db.execute('SELECT id,account FROM tester_access WHERE token_hash=? AND device=? AND revoked=0 AND expires>?',(digest(token),device,int(time.time()))).fetchone()
        check(row,'Acesso de tester expirou ou foi revogado. Fale com o administrador.')
        return row

    def tester_action(self, request):
        if request['action']=='tester_redeem':
            code=request.get('code','');device=request.get('device','')
            check(isinstance(code,str) and re.fullmatch(r'NLT-[0-9A-F]{32}',code.upper()) and isinstance(device,str) and re.fullmatch('[0-9a-f]{32}',device),'Chave de convite invalida.')
            token=secrets.token_hex(32);now=int(time.time())
            changed=self.db.execute('UPDATE tester_access SET claimed=?,device=?,token_hash=? WHERE code_hash=? AND claimed=0 AND revoked=0 AND expires>?',(now,device,digest(token),digest(code.upper()),now)).rowcount
            check(changed==1,'Convite utilizado, expirado ou revogado. Solicite outro ao administrador.')
            return dict(credentials=dict(token=token,device=device))
        check(request['action']=='tester_access','Acao desconhecida.')
        self.tester_auth(request.get('tester'))
        row=self.db.execute('SELECT payload FROM tester_catalog WHERE id=1').fetchone()
        return dict(authorized=True,release=json.loads(row[0]) if row else None)

    def tester_require_request(self, request):
        # Gate subsequent room/presence calls too, even if channel/build is omitted.
        protected=request.get('channel')=='testers' or str(request.get('build','')).endswith('-testers')
        for field in ('profile','social'):
            value=request.get(field)
            if isinstance(value,dict):protected=protected or str(value.get('build','')).endswith('-testers')
        if not protected and request.get('code'):
            room=self.db.execute('SELECT data FROM rooms WHERE code=?',(str(request['code'])[:16],)).fetchone()
            if room:protected=str(json.loads(room[0]).get('build','')).endswith('-testers')
        if not protected:
            token=request.get('token');presence=self.presence.get(token) if isinstance(token,str) else None
            protected=bool(presence and str(presence.get('build','')).endswith('-testers'))
        if not protected:return
        identity,account=self.tester_auth(request.get('tester'))
        if request.get('account'):
            # Bind only after authenticating an existing online account. Registration
            # is checked on its next request; an attacker cannot reserve another ID.
            row=self.db.execute('SELECT 1 FROM accounts WHERE id=?',(request['account'].get('id'),)).fetchone() if isinstance(request['account'],dict) else None
            if row:
                current=self.account(request)['id']
                check(account is None or account==current,'Este convite pertence a outra conta online.')
                self.db.execute('UPDATE tester_access SET account=? WHERE id=? AND account IS NULL',(current,identity))
