"""Account-based moderation, dedicated staff keys and durable chat/audit history."""
import hashlib
import json
import re
import secrets
import time
try:
    from gifts import check
except ModuleNotFoundError:
    from server.gifts import check


class ModerationError(ValueError):
    def __init__(self,code,message,until=0):
        super().__init__(message);self.code=code;self.until=until


class StaffAuthError(ValueError):pass


class ModerationService:
    def setup_moderation(self):
        for sql in (
            'CREATE TABLE IF NOT EXISTS moderation_owner(id INTEGER PRIMARY KEY CHECK(id=1),account TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS moderators(account TEXT PRIMARY KEY,key_hash TEXT UNIQUE NOT NULL,active INTEGER NOT NULL,created INTEGER NOT NULL)',
            "CREATE TABLE IF NOT EXISTS moderation_sanctions(account TEXT PRIMARY KEY,muted_until INTEGER NOT NULL DEFAULT 0,kicked_until INTEGER NOT NULL DEFAULT 0,banned INTEGER NOT NULL DEFAULT 0,mute_reason TEXT NOT NULL DEFAULT '',kick_reason TEXT NOT NULL DEFAULT '',ban_reason TEXT NOT NULL DEFAULT '')",
            'CREATE TABLE IF NOT EXISTS moderation_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,created INTEGER NOT NULL,actor TEXT NOT NULL,actor_label TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,detail TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS chat_history(id INTEGER PRIMARY KEY AUTOINCREMENT,build TEXT NOT NULL,room TEXT NOT NULL,account TEXT NOT NULL,sender TEXT NOT NULL,client_id TEXT NOT NULL,nickname TEXT NOT NULL,text TEXT NOT NULL,created INTEGER NOT NULL,hidden INTEGER NOT NULL DEFAULT 0,UNIQUE(account,client_id))',
            'CREATE INDEX IF NOT EXISTS chat_room_history ON chat_history(room,build,id)',
            'CREATE INDEX IF NOT EXISTS chat_account_history ON chat_history(account,id)',
            'CREATE INDEX IF NOT EXISTS moderation_target_history ON moderation_audit(target,id)',
            'CREATE TABLE IF NOT EXISTS moderation_state(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL,chat_revision INTEGER NOT NULL)',
        ):self.db.execute(sql)
        self.db.execute('INSERT OR IGNORE INTO moderation_state VALUES(1,0,0)')
        self._moderation_checked=0;self._moderation_revision=None;self._sanctions={};self._chat_revision=0

    def moderation_refresh(self):
        now=time.monotonic()
        if now<self._moderation_checked:return
        revision,chat_revision=self.db.execute('SELECT revision,chat_revision FROM moderation_state WHERE id=1').fetchone()
        if revision!=self._moderation_revision:
            self._sanctions.clear();self._moderation_revision=revision
        if chat_revision!=self._chat_revision:
            self.chat_rooms.clear();self._chat_revision=chat_revision
        self._moderation_checked=now+1

    def moderation_status(self,account):
        self.moderation_refresh()
        if account not in self._sanctions:
            row=self.db.execute('SELECT muted_until,kicked_until,banned,mute_reason,kick_reason,ban_reason FROM moderation_sanctions WHERE account=?',(account,)).fetchone()
            if len(self._sanctions)>=2048:self._sanctions.clear()
            self._sanctions[account]=dict(zip(('muted_until','kicked_until','banned','mute_reason','kick_reason','ban_reason'),row or (0,0,0,'','','')))
        return self._sanctions[account]

    def moderation_require_online(self,account):
        state=self.moderation_status(account)
        if state['banned']:raise ModerationError('BANNED','Acesso online banido. Motivo: '+state['ban_reason'])

    def moderation_require_map(self,account,room):
        self.moderation_require_online(account)
        state=self.moderation_status(account)
        if room=='PRACA' and state['kicked_until']>time.time():
            raise ModerationError('KICKED','Voce foi retirado da praca geral. Aguarde para retornar. Motivo: '+state['kick_reason'],state['kicked_until'])

    def moderation_peer_allowed(self,row):
        state=self.moderation_status(row.get('account_id',''))
        return not state['banned'] and not (row.get('room')=='PRACA' and state['kicked_until']>time.time())

    def moderation_require_chat(self,account):
        state=self.moderation_status(account)
        if state['muted_until']>time.time():
            raise ModerationError('CHAT_MUTED','Mensagem: voce esta silenciado no chat. Motivo: '+state['mute_reason'],state['muted_until'])

    def moderation_bump(self,chat=False):
        self.db.execute('UPDATE moderation_state SET revision=revision+1,chat_revision=chat_revision+? WHERE id=1',(int(chat),))
        self._moderation_checked=0

    def moderation_owner(self):
        row=self.db.execute('SELECT account FROM moderation_owner WHERE id=1').fetchone()
        return row[0] if row else None

    def moderation_role(self,account):
        if account==self.moderation_owner():return 'owner'
        row=self.db.execute('SELECT active FROM moderators WHERE account=?',(account,)).fetchone()
        return 'moderator' if row and row[0] else 'player'

    def moderation_admin(self,request):
        # Only the trusted Discloud console can call this method.
        owner=self.moderation_owner()
        return self.moderation_run(request,dict(role='owner',id=owner or 'discloud-owner',nickname='Administrador'))

    def moderation_staff(self,key,request):
        check(isinstance(request,dict),'Pedido de moderacao invalido.')
        with self.lock,self.db:
            if request.get('action') not in ('session','accounts','history','audit'):
                self.db.execute('BEGIN IMMEDIATE')
            if not isinstance(key,str) or not re.fullmatch(r'nmod_[0-9a-f]{64}',key):raise StaffAuthError('Chave de moderacao invalida.')
            digest=hashlib.sha256(key.encode()).hexdigest()
            row=self.db.execute('SELECT m.account,a.nickname,m.active FROM moderators m JOIN accounts a ON a.id=m.account WHERE m.key_hash=?',(digest,)).fetchone()
            if not row or not row[2]:raise StaffAuthError('Chave revogada ou invalida.')
            if self.db.execute('SELECT 1 FROM moderation_sanctions WHERE account=? AND banned=1',(row[0],)).fetchone():raise StaffAuthError('Acesso de moderacao suspenso.')
            return self.moderation_run(request,dict(role='moderator',id=row[0],nickname=row[1]),in_transaction=True)

    def moderation_run(self,request,actor,in_transaction=False):
        check(isinstance(request,dict),'Pedido de moderacao invalido.')
        action=request.get('action')
        with self.lock,self.db:
            if action in ('session','accounts','history','audit'):
                if action=='session':return dict(actor=dict(actor))
                return self.moderation_read(request,actor)
            if not in_transaction:self.db.execute('BEGIN IMMEDIATE')
            check(action in ('set_owner','grant','revoke','mute','unmute','kick','ban','unban','hide_message','restore_message'),'Acao de moderacao desconhecida.')
            if action in ('set_owner','grant','revoke'):check(actor['role']=='owner','Somente o administrador gerencia a equipe.')
            target=request.get('target')
            if action in ('hide_message','restore_message'):
                identity=request.get('message_id');check(type(identity) is int and identity>0,'Selecione uma mensagem.')
                row=self.db.execute('SELECT account FROM chat_history WHERE id=?',(identity,)).fetchone();check(row,'Mensagem nao encontrada.');target=row[0]
            else:
                check(isinstance(target,str) and re.fullmatch(r'[0-9a-f]{32}',target),'Selecione uma conta pelo ID.')
                check(self.db.execute('SELECT 1 FROM accounts WHERE id=?',(target,)).fetchone(),'Conta nao encontrada.')
            if action not in ('set_owner','revoke','hide_message','restore_message'):
                check(target!=self.moderation_owner(),'Esta conta e do administrador e esta protegida.')
            if actor['role']!='owner':check(self.moderation_role(target)=='player','Moderadores nao podem aplicar acoes na equipe administrativa.')
            reason=request.get('reason','Acao administrativa.').strip() if isinstance(request.get('reason',''),str) else ''
            check(1<=len(reason)<=200 and all(ord(c)>=32 for c in reason),'Informe um motivo de 1 a 200 caracteres.')
            result={}
            if action=='set_owner':
                self.db.execute('INSERT INTO moderation_owner VALUES(1,?) ON CONFLICT(id) DO UPDATE SET account=excluded.account',(target,))
                self.db.execute('UPDATE moderators SET active=0 WHERE account=?',(target,))
                self.db.execute('DELETE FROM moderation_sanctions WHERE account=?',(target,))
            elif action=='grant':
                check(not self.db.execute('SELECT 1 FROM moderation_sanctions WHERE account=? AND banned=1',(target,)).fetchone(),'Retire o ban antes de conceder acesso de moderador.')
                key='nmod_'+secrets.token_hex(32);digest=hashlib.sha256(key.encode()).hexdigest()
                self.db.execute('INSERT INTO moderators VALUES(?,?,1,?) ON CONFLICT(account) DO UPDATE SET key_hash=excluded.key_hash,active=1,created=excluded.created',(target,digest,int(time.time())))
                result['moderator_key']=key
            elif action=='revoke':self.db.execute('UPDATE moderators SET active=0 WHERE account=?',(target,))
            elif action in ('hide_message','restore_message'):
                self.db.execute('UPDATE chat_history SET hidden=? WHERE id=?',(int(action=='hide_message'),request['message_id']))
                reason=f"Mensagem #{request['message_id']}: "+reason
            else:
                self.db.execute('INSERT OR IGNORE INTO moderation_sanctions(account) VALUES(?)',(target,))
                if action=='mute':
                    seconds=request.get('seconds');check(type(seconds) is int and 1<=seconds<=7200,'Silencio deve durar no maximo duas horas (7200 segundos).')
                    until=int(time.time())+seconds
                    self.db.execute('UPDATE moderation_sanctions SET muted_until=?,mute_reason=? WHERE account=?',(until,reason,target));result['until']=until
                elif action=='unmute':self.db.execute("UPDATE moderation_sanctions SET muted_until=0,mute_reason='' WHERE account=?",(target,))
                elif action=='kick':
                    until=int(time.time())+60
                    self.db.execute('UPDATE moderation_sanctions SET kicked_until=?,kick_reason=? WHERE account=?',(until,reason,target));result['until']=until
                elif action=='ban':self.db.execute('UPDATE moderation_sanctions SET banned=1,ban_reason=? WHERE account=?',(reason,target))
                elif action=='unban':self.db.execute("UPDATE moderation_sanctions SET banned=0,ban_reason='' WHERE account=?",(target,))
            self.db.execute('INSERT INTO moderation_audit(created,actor,actor_label,action,target,detail) VALUES(?,?,?,?,?,?)',(int(time.time()),actor['id'],actor['nickname'],action,target,reason+(' / '+str(request.get('seconds'))+'s' if action=='mute' else '')))
            self.moderation_bump(action in ('hide_message','restore_message'))
            return dict(ok=True,action=action,target=target,**result)

    def moderation_read(self,request,actor):
        action=request['action'];limit=request.get('limit',100)
        check(type(limit) is int and 1<=limit<=100,'Limite invalido.')
        if action=='accounts':
            query=request.get('search','');offset=request.get('offset',0)
            check(isinstance(query,str) and len(query)<=48 and type(offset) is int and 0<=offset<=100000,'Filtro de contas invalido.')
            query=query.strip().casefold().replace('!','!!').replace('%','!%').replace('_','!_')+'%'
            rows=self.db.execute("SELECT id,nickname,created,updated FROM accounts WHERE normalized LIKE ? ESCAPE '!' OR id LIKE ? ESCAPE '!' ORDER BY normalized LIMIT ? OFFSET ?",(query,query,limit,offset)).fetchall()
            result=[]
            for identity,nick,created,updated in rows:
                state=self.db.execute('SELECT muted_until,kicked_until,banned FROM moderation_sanctions WHERE account=?',(identity,)).fetchone() or (0,0,0)
                result.append(dict(id=identity,nickname=nick,created=created,updated=updated,role=self.moderation_role(identity),muted_until=state[0],kicked_until=state[1],banned=bool(state[2])))
            return dict(accounts=result,total=self.db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0],offset=offset,owner=self.moderation_owner(),actor=dict(actor))
        cursor=request.get('before',2**63-1)
        check(type(cursor) is int and 0<cursor<2**63,'Cursor invalido.')
        if action=='history':
            room=request.get('room','PRACA');target=request.get('target','')
            check(isinstance(room,str) and (room in ('','PRACA') or re.fullmatch(r'[A-Z2-9]{8}',room)),'Sala invalida.')
            check(isinstance(target,str) and (not target or re.fullmatch(r'[0-9a-f]{32}',target)),'Conta invalida.')
            rows=self.db.execute('SELECT id,created,room,account,nickname,text,hidden,build FROM chat_history WHERE id<? AND (?=\'\' OR room=?) AND (?=\'\' OR account=?) ORDER BY id DESC LIMIT ?',(cursor,room,room,target,target,limit)).fetchall()
            return dict(messages=[dict(id=r[0],timestamp=r[1],room=r[2],account_id=r[3],nickname=r[4],text=r[5],hidden=bool(r[6]),build=r[7]) for r in rows],next_before=rows[-1][0] if rows else None)
        check(action=='audit','Consulta desconhecida.')
        rows=self.db.execute('SELECT id,created,actor_label,action,target,detail,actor FROM moderation_audit WHERE id<? ORDER BY id DESC LIMIT ?',(cursor,limit)).fetchall()
        return dict(audit=[dict(id=r[0],timestamp=r[1],actor=r[2],action=r[3],target=r[4],detail=r[5],actor_id=r[6]) for r in rows],next_before=rows[-1][0] if rows else None)

    def persistent_chat_rows(self,build,room):
        rows=self.db.execute('SELECT id,client_id,sender,nickname,text,created FROM chat_history WHERE build=? AND room=? AND hidden=0 ORDER BY id DESC LIMIT 80',(build,room)).fetchall()
        return [dict(id=r[0],client_id=r[1],sender=r[2],nick=r[3],text=r[4],timestamp=r[5]) for r in reversed(rows)]

    def persist_chat(self,row,client_id,text):
        old=self.db.execute('SELECT id,build,room,text FROM chat_history WHERE account=? AND client_id=?',(row['account_id'],client_id)).fetchone()
        if old:
            check((old[1],old[2],old[3])==(row['build'],row['room'],text),'ID de mensagem ja utilizado.')
            return None
        check(time.monotonic()-row.get('last_chat',-10)>=2,'Espere 2 segundos entre mensagens.')
        self.moderation_require_chat(row['account_id'])
        now=int(time.time())
        cursor=self.db.execute('INSERT INTO chat_history(build,room,account,sender,client_id,nickname,text,created) VALUES(?,?,?,?,?,?,?,?)',(row['build'],row['room'],row['account_id'],row['id'],client_id,row['name'],text,now))
        return dict(id=cursor.lastrowid,client_id=client_id,sender=row['id'],nick=row['name'],text=text,timestamp=now)
