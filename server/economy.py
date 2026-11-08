"""Luna Coins, durable rewards, community progress and ephemeral matchmaking."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import time
try:
    from gifts import check, rewards_data
    from content import ContentService, DEFAULT_CONTENT
except ModuleNotFoundError:
    from server.gifts import check, rewards_data
    from server.content import ContentService, DEFAULT_CONTENT

BADGES = {
    'lunar_participant': dict(title='Participante lunar',description='Participe de uma batalha valida do evento da praca.'),
    'community_50': dict(title='Praca unida',description='Participe do evento que completou 50 batalhas.'),
}


def day():
    return datetime.fromtimestamp(time.time(), timezone(timedelta(hours=-3))).date().isoformat()


class EconomyService(ContentService):
    def setup_economy(self):
        for sql in (
            'CREATE TABLE IF NOT EXISTS wallets(account TEXT PRIMARY KEY,balance INTEGER NOT NULL CHECK(balance>=0))',
            'CREATE TABLE IF NOT EXISTS coin_ledger(account TEXT,event TEXT,amount INTEGER,created INTEGER,PRIMARY KEY(account,event))',
            'CREATE TABLE IF NOT EXISTS daily_stats(account TEXT,day TEXT,kind TEXT,value INTEGER,PRIMARY KEY(account,day,kind))',
            'CREATE TABLE IF NOT EXISTS economy_activity(event TEXT PRIMARY KEY,kind TEXT,created INTEGER)',
            'CREATE TABLE IF NOT EXISTS battle_reports(room TEXT,account TEXT,decision INTEGER,PRIMARY KEY(room,account))',
            'CREATE TABLE IF NOT EXISTS community_events(id TEXT PRIMARY KEY,progress INTEGER NOT NULL)',
            'CREATE TABLE IF NOT EXISTS community_members(account TEXT,event TEXT,value INTEGER,PRIMARY KEY(account,event))',
            'CREATE TABLE IF NOT EXISTS shop_orders(account TEXT,id TEXT,sku TEXT,claim TEXT,created INTEGER,PRIMARY KEY(account,id))',
            'CREATE INDEX IF NOT EXISTS ledger_recent ON coin_ledger(account,created DESC)',
            'CREATE TABLE IF NOT EXISTS cosmetic_preferences(account TEXT PRIMARY KEY,badge TEXT NOT NULL)',
        ):
            self.db.execute(sql)
        self.matchmaking = {}
        self.badge_cache = {}
        self.setup_content()

    def badge_view(self, account):
        now=time.monotonic()
        cached=self.badge_cache.get(account)
        if cached and now<cached[0]:
            return cached[1]
        # Earned badges survive rotating the current community challenge.
        _,config=self.content_snapshot()
        goals=self._community_goals
        rows=self.db.execute('SELECT m.event,m.value,COALESCE(e.progress,0) FROM community_members m LEFT JOIN community_events e ON e.id=m.event WHERE m.account=?',(account,)).fetchall()
        earned=[]
        if any(row[1]>0 for row in rows):
            earned.append('lunar_participant')
            if any(row[1]>0 and row[2]>=goals.get(row[0],50) for row in rows):earned.append('community_50')
        pref=self.db.execute('SELECT badge FROM cosmetic_preferences WHERE account=?',(account,)).fetchone()
        equipped=pref[0] if pref else (earned[-1] if earned else '')
        if equipped not in earned:equipped=''
        data=dict(badges=[dict(id=key,**BADGES[key]) for key in earned],equipped_badge=equipped)
        if len(self.badge_cache)>2048:
            self.badge_cache={key:value for key,value in self.badge_cache.items() if now<value[0]}
        self.badge_cache[account]=(now+60,data)
        return data

    def balance(self, account):
        row = self.db.execute('SELECT balance FROM wallets WHERE account=?', (account,)).fetchone()
        return row[0] if row else 0

    def credit(self, account, event, amount):
        if self.db.execute('SELECT 1 FROM coin_ledger WHERE account=? AND event=?', (account,event)).fetchone():
            return False
        self.db.execute('INSERT OR IGNORE INTO wallets VALUES(?,0)', (account,))
        self.db.execute('UPDATE wallets SET balance=balance+? WHERE account=?', (amount,account))
        self.db.execute('INSERT INTO coin_ledger VALUES(?,?,?,?)', (account,event,amount,int(time.time())))
        return True

    def activity(self, kind, room):
        _,config=self.content_snapshot()
        community=config['community'];event_id=community['id']
        people = [p['profile'].get('account_id') for p in room['players']]
        if len(people)!=2 or not all(people) or people[0]==people[1]:
            return False
        event = kind+':'+room['code']
        if self.db.execute('SELECT 1 FROM economy_activity WHERE event=?', (event,)).fetchone():
            return False
        self.db.execute('INSERT INTO economy_activity VALUES(?,?,?)', (event,kind,int(time.time())))
        for account in people:
            self.badge_cache.pop(account,None)
            self.db.execute('INSERT INTO daily_stats VALUES(?,?,?,1) ON CONFLICT(account,day,kind) DO UPDATE SET value=MIN(value+1,9999)', (account,day(),kind))
            if kind=='battle' and community['enabled']:
                self.db.execute('INSERT INTO community_members VALUES(?,?,1) ON CONFLICT(account,event) DO UPDATE SET value=value+1', (account,event_id))
        if kind=='battle' and community['enabled']:
            self.db.execute('INSERT INTO community_events VALUES(?,1) ON CONFLICT(id) DO UPDATE SET progress=MIN(progress+1,?)', (event_id,community['target']))
            if getattr(self,'community_badges_announced',None)!=event_id and self.db.execute('SELECT progress FROM community_events WHERE id=?',(event_id,)).fetchone()[0]==community['target']:
                self.badge_cache.clear()
                self.community_badges_announced=event_id
        return True

    def battle_result(self, room, side, result):
        check(room['mode']=='battle' and len(room['players'])==2, 'Esta sala nao e uma batalha em dupla de jogadores.')
        check(type(result) is int and result in (1,2,5), 'Batalha interrompida nao concede progresso.')
        people = [p['profile'].get('account_id') for p in room['players']]
        check(all(people) and people[0]!=people[1], 'Uma conta nao pode enfrentar a si mesma.')
        prior = self.db.execute('SELECT decision FROM battle_reports WHERE room=? AND account=?', (room['code'],people[side])).fetchone()
        check(not prior or prior[0]==result, 'Resultado ja registrado.')
        reports = self.db.execute('SELECT decision FROM battle_reports WHERE room=?', (room['code'],)).fetchall()
        turns = sum(key.startswith('turn:') and len(values)==2 for key,values in room['exchanges'].items())
        check(reports or room.get('economy_verified_turns') or turns>=2, 'Missao exige ao menos dois turnos confirmados.')
        if not prior:
            self.db.execute('INSERT INTO battle_reports VALUES(?,?,?)', (room['code'],people[side],result))
        results = self.db.execute('SELECT decision FROM battle_reports WHERE room=?', (room['code'],)).fetchall()
        confirmed = len(results)==2 and results[0][0]==results[1][0]
        if confirmed:
            self.activity('battle',room)
        return dict(confirmed=confirmed, disputed=len(results)==2 and not confirmed)

    def economy_view(self, account):
        revision,config=self.content_snapshot()
        community=config['community'];event_id=community['id']
        today = day()
        stats = dict(self.db.execute('SELECT kind,value FROM daily_stats WHERE account=? AND day=?', (account,today)))
        if 'visit' not in stats:
            self.db.execute('INSERT OR IGNORE INTO daily_stats VALUES(?,?,?,1)', (account,today,'visit'))
            stats['visit']=1
        claimed = {r[0] for r in self.db.execute('SELECT event FROM coin_ledger WHERE account=? AND event LIKE ?', (account,'daily:'+today+':%'))}
        progress = self.db.execute('SELECT progress FROM community_events WHERE id=?', (event_id,)).fetchone()
        member = self.db.execute('SELECT value FROM community_members WHERE account=? AND event=?', (account,event_id)).fetchone()
        community_claimed = bool(self.db.execute('SELECT 1 FROM coin_ledger WHERE account=? AND event=?', (account,'community:'+event_id)).fetchone())
        return dict(balance=self.balance(account), day=today, content_revision=revision, **self.badge_view(account),
            missions=[dict(id=key, **data, progress=min(stats.get(data['kind'],0),data['target']), claimed='daily:'+today+':'+key in claimed) for key,data in config['missions'].items() if data['enabled']],
            shop=[dict(id=key, **row) for key,row in config['shop'].items()],
            community=dict(**community,progress=progress[0] if progress else 0,contributed=bool(member),claimed=community_claimed))

    def economy_action(self, request):
        account = self.account(request)['id']
        action = request['action']
        if action=='economy_badges':
            selected=request.get('badge')
            view=self.badge_view(account)
            check(isinstance(selected,str) and (selected=='' or selected in [r['id'] for r in view['badges']]),'Este emblema ainda nao foi conquistado.')
            self.db.execute('INSERT INTO cosmetic_preferences VALUES(?,?) ON CONFLICT(account) DO UPDATE SET badge=excluded.badge',(account,selected))
            self.badge_cache.pop(account,None)
            return self.economy_view(account)
        if action=='economy_sync':
            return self.economy_view(account)
        if action=='economy_ledger':
            return dict(balance=self.balance(account), entries=[dict(event=r[0],amount=r[1],created=r[2]) for r in self.db.execute('SELECT event,amount,created FROM coin_ledger WHERE account=? ORDER BY created DESC,rowid DESC LIMIT 30',(account,))])
        if action=='economy_order':
            order = self.db.execute('SELECT claim FROM shop_orders WHERE account=? AND id=?',(account,str(request.get('order')))).fetchone()
            row = self.db.execute('SELECT * FROM gift_claims WHERE id=? AND account=?',(order[0],account)).fetchone() if order else None
            return {'claim':self.gift_ticket(row) if row else None,'balance':self.balance(account)}
        self.db.execute('BEGIN IMMEDIATE')
        # Refresh inside the write transaction so a console edit cannot race a charge.
        self._content_checked=0
        revision,config=self.content_snapshot()
        community=config['community'];event_id=community['id']
        if action=='economy_claim':
            key = request.get('mission')
            if key==event_id:
                view = self.economy_view(account)['community']
                check(community['enabled'] and view['progress']>=view['target'] and view['contributed'], 'A meta ainda nao foi atingida ou voce nao participou.')
                self.credit(account,'community:'+event_id,community['coins'])
            else:
                check(isinstance(key,str) and key in config['missions'] and config['missions'][key]['enabled'],'Missao desconhecida ou encerrada.')
                data = config['missions'][key]
                row = self.db.execute('SELECT value FROM daily_stats WHERE account=? AND day=? AND kind=?',(account,day(),data['kind'])).fetchone()
                check(row and row[0]>=data['target'],'Esta missao ainda nao foi concluida.')
                self.credit(account,'daily:'+day()+':'+key,data['coins'])
            return self.economy_view(account)
        check(action=='economy_buy','Operacao de Luna Coins desconhecida.')
        order,sku = request.get('order'),request.get('sku')
        check(isinstance(order,str) and len(order)==32 and all(c in '0123456789abcdef' for c in order),'Identificador de compra invalido.')
        old = self.db.execute('SELECT sku,claim FROM shop_orders WHERE account=? AND id=?',(account,order)).fetchone()
        if old:
            check(old[0]==sku,'Esta compra pertence a outro produto.')
            row=self.db.execute('SELECT * FROM gift_claims WHERE id=?',(old[1],)).fetchone()
            return dict(balance=self.balance(account),claim=self.gift_ticket(row))
        check(isinstance(sku,str) and sku in config['shop'] and config['shop'][sku].get('enabled',True),'Este produto ainda nao esta disponivel.')
        item = config['shop'][sku]
        check('expected_price' not in request or (type(request['expected_price']) is int and request['expected_price']==item['price']),
              'O preco mudou. Atualize a loja antes de confirmar a compra.')
        check(self.balance(account)>=item['price'],'Luna Coins insuficientes.')
        rewards = rewards_data(item['rewards'])
        self.db.execute('UPDATE wallets SET balance=balance-? WHERE account=?',(item['price'],account))
        self.db.execute('INSERT INTO coin_ledger VALUES(?,?,?,?)',(account,'purchase:'+order,-item['price'],int(time.time())))
        identity=secrets.token_hex(16)
        data=dict(code='LOJA-'+sku,gift='order:'+order,title=item['title'],rewards=rewards)
        self.db.execute('INSERT INTO gift_claims VALUES(?,?,?,?,?,?,?)',(identity,account,'order:'+order,json.dumps(data),'reserved',int(time.time()),int(time.time())))
        self.db.execute('INSERT INTO shop_orders VALUES(?,?,?,?,?)',(account,order,sku,identity,int(time.time())))
        return dict(balance=self.balance(account),claim=dict(data,id=identity,state='reserved',created=int(time.time())))

    def match_action(self, request):
        account=self.account(request)['id'];action=request['action'];now=time.monotonic()
        for identity,row in list(self.matchmaking.items()):
            if now-row['seen']>(120 if row.get('code') else 25):
                self.matchmaking.pop(identity,None)
        entry=self.matchmaking.get(account)
        if action=='match_enter':
            if not entry:
                check(len(self.matchmaking)<500,'Fila cheia. Tente novamente em instantes.')
                rules=request.get('rules')
                # Use the same strict validation as normal battle rooms.
                from_rules=self.validate_match_rules(rules)
                player=self.player(dict(request,mode='battle'))
                count=from_rules['count'] if isinstance(from_rules,dict) else None
                check(not count or len(player['payload'])==count,'Equipe diferente das regras.')
                build=request.get('build')
                check(isinstance(build,str) and 1<=len(build)<=100,'Versao invalida.')
                key=hashlib.sha256(json.dumps([build,from_rules],sort_keys=True).encode()).hexdigest()
                entry=dict(id=secrets.token_hex(16),seen=now,player=player,rules=from_rules,build=build,key=key)
                self.matchmaking[account]=entry
        else:
            check(entry and request.get('ticket')==entry['id'],'Busca expirada. Inicie novamente.')
        entry['seen']=now
        if action=='match_cancel':
            if entry.get('code'):
                room=self.load(entry['code'])
                if not room['exchanges'] and room['status']=='active':
                    room['status']='cancelled';self.save(room)
            self.matchmaking.pop(account,None)
            return {'state':'cancelled'}
        check(action in ('match_enter','match_poll'),'Acao de busca desconhecida.')
        if not entry.get('code'):
            for other,peer in self.matchmaking.items():
                if other==account or peer.get('code') or peer['key']!=entry['key']:
                    continue
                check(self.db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]<100000,'Servidor cheio. Contate o administrador.')
                code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
                while self.db.execute('SELECT 1 FROM rooms WHERE code=?',(code,)).fetchone():
                    code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
                room=dict(code=code,mode='battle',build=entry['build'],rules=entry['rules'],status='active',seed=secrets.randbelow(2**30),
                          players=[peer['player'],entry['player']],exchanges={},updated=time.time())
                self.save(room)
                peer.update(code=code,side=0);entry.update(code=code,side=1)
                break
        if entry.get('code'):
            room=self.load(entry['code'])
            if room['status']!='active':
                self.matchmaking.pop(account,None)
                return {'state':'cancelled'}
            return dict(state='matched',ticket=entry['id'],room=dict(self.view(room,entry['side']),token=entry['player']['token']))
        return dict(state='waiting',ticket=entry['id'],poll_after=2)
