"""Versioned live content. Administration is local/hosting-console only, never HTTP."""
import copy
import json
import re
import time
try:
    from gifts import check, rewards_data
except ModuleNotFoundError:
    from server.gifts import check, rewards_data

DEFAULT_CONTENT = dict(
    missions={
        'visit': dict(title='Visita diaria', kind='visit', target=1, coins=10, enabled=True),
        'battle1': dict(title='Conclua uma batalha (2+ turnos)', kind='battle', target=1, coins=20, enabled=True),
        'battle3': dict(title='Conclua tres batalhas (2+ turnos)', kind='battle', target=3, coins=40, enabled=True),
        'trade1': dict(title='Conclua uma troca', kind='trade', target=1, coins=15, enabled=True),
    },
    shop={
        'balls5': dict(title='5 Poke Balls', price=25, rewards=[dict(kind='item', id='POKEBALL', quantity=5)], enabled=True),
        'potion3': dict(title='3 Pocoes', price=15, rewards=[dict(kind='item', id='POTION', quantity=3)], enabled=True),
        'aipom_egg': dict(title='Ovo de Aipom', price=80, rewards=[dict(kind='pokemon', species='AIPOM', level=1, form=0, shiny=False, egg=True)], enabled=True),
        'outfits': dict(title='Roupas / em breve', price=0, rewards=[], enabled=False),
    },
    community=dict(id='praca-50-v1', title='Praca unida: 50 batalhas', target=50, coins=100, enabled=True),
)


def identity(value):
    check(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,47}', value), 'ID: use 1 a 48 letras minusculas, numeros, _ ou -.')
    return value


def integer(value, minimum, maximum, label):
    check(type(value) is int and minimum <= value <= maximum, label+' fora do limite.')
    return value


def title(value):
    check(isinstance(value, str) and 1 <= len(value.strip()) <= 72 and all(ord(c) >= 32 for c in value), 'Titulo: 1 a 72 caracteres sem quebras de linha.')
    return value.strip()


def validate_content(value):
    check(isinstance(value, dict) and set(value) == {'missions', 'shop', 'community'}, 'Conteudo precisa de missions, shop e community.')
    value = copy.deepcopy(value)
    for group, maximum in [('missions', 30), ('shop', 100)]:
        check(isinstance(value[group], dict) and len(value[group]) <= maximum, 'Quantidade invalida em '+group+'.')
        for key, row in value[group].items():
            identity(key)
            keys = {'title', 'kind', 'target', 'coins', 'enabled'} if group == 'missions' else {'title', 'price', 'rewards', 'enabled'}
            check(isinstance(row, dict) and set(row) == keys, 'Campos invalidos em '+key+'.')
            row['title'] = title(row['title'])
            check(type(row['enabled']) is bool, 'Ativo precisa ser verdadeiro ou falso.')
            if group == 'missions':
                check(row['kind'] in ('visit', 'battle', 'trade'), 'Atividade deve ser visit, battle ou trade.')
                integer(row['target'], 1, 9999, 'Meta')
                integer(row['coins'], 1, 100000, 'Luna Coins')
                check(row['kind'] != 'visit' or row['target'] == 1, 'Visita diaria tem meta 1.')
            else:
                integer(row['price'], 0, 1000000, 'Preco')
                check(not row['enabled'] or row['rewards'], 'Produto ativo precisa de recompensa.')
                if row['rewards']:
                    row['rewards'] = rewards_data(row['rewards'])
                else:
                    check(row['rewards'] == [], 'Recompensas invalidas.')
    event = value['community']
    check(isinstance(event, dict) and set(event) == {'id', 'title', 'target', 'coins', 'enabled'}, 'Campos invalidos no evento.')
    identity(event['id']); event['title'] = title(event['title'])
    check(event['id'] not in value['missions'], 'O ID do evento deve ser diferente dos IDs das missoes.')
    integer(event['target'], 1, 1000000, 'Meta comunitaria')
    integer(event['coins'], 1, 100000, 'Recompensa comunitaria')
    check(type(event['enabled']) is bool, 'Ativo precisa ser verdadeiro ou falso.')
    check(len(json.dumps(value).encode()) <= 100000, 'Conteudo excede 100 KB.')
    return value


class ContentService:
    def setup_content(self):
        self.db.execute('CREATE TABLE IF NOT EXISTS content_revisions(revision INTEGER PRIMARY KEY,created INTEGER NOT NULL,data TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS server_notices(id TEXT PRIMARY KEY,text TEXT NOT NULL,kind TEXT NOT NULL,starts INTEGER NOT NULL,ends INTEGER NOT NULL,duration INTEGER NOT NULL,active INTEGER NOT NULL,created INTEGER NOT NULL)')
        self.db.execute('CREATE INDEX IF NOT EXISTS notices_active ON server_notices(active,ends)')
        self._content_cache = None
        self._content_checked = 0
        self._notice_cache=[];self._notice_checked=0

    def notice_view(self):
        now=time.time()
        if time.monotonic()>=self._notice_checked:
            self._notice_cache=[dict(id=r[0],text=r[1],kind=r[2],starts=r[3],ends=r[4],duration=r[5]) for r in self.db.execute('SELECT id,text,kind,starts,ends,duration FROM server_notices WHERE active=1 AND ends>? ORDER BY created DESC,rowid DESC LIMIT 20',(int(now),))]
            self._notice_checked=time.monotonic()+15
        return [dict(row) for row in reversed(self._notice_cache) if row['starts']<=now<row['ends']][-5:]

    def notice_admin(self,request):
        import secrets
        with self.lock,self.db:
            action=request.get('action');now=int(time.time())
            if action=='create':
                text=request.get('text');kind=request.get('kind')
                check(isinstance(text,str) and 1<=len(text.strip())<=180 and all(ord(c)>=32 for c in text),'Aviso: 1 a 180 caracteres sem quebras de linha.')
                check(kind in ('info','event','maintenance'),'Tipo de aviso invalido.')
                starts=integer(request.get('starts',now),now-60,now+30*86400,'Inicio')
                ends=integer(request.get('ends'),starts+60,starts+30*86400,'Fim')
                duration=integer(request.get('duration',8),6,12,'Tempo na tela')
                check(self.db.execute('SELECT COUNT(*) FROM server_notices WHERE active=1 AND ends>?',(now,)).fetchone()[0]<20,'Encerre um aviso antes de publicar outro; limite de 20.')
                identity=secrets.token_hex(16)
                self.db.execute('INSERT INTO server_notices VALUES(?,?,?,?,?,?,1,?)',(identity,text.strip(),kind,starts,ends,duration,now))
            elif action=='disable':
                check(isinstance(request.get('id'),str) and re.fullmatch(r'[0-9a-f]{32}',request['id']),'Aviso invalido.')
                self.db.execute('UPDATE server_notices SET active=0 WHERE id=?',(request['id'],))
            else:check(action=='list','Acao administrativa desconhecida.')
            self._notice_checked=0
            return dict(notices=[dict(id=r[0],text=r[1],kind=r[2],starts=r[3],ends=r[4],duration=r[5],active=bool(r[6]) and r[3]<=now<r[4]) for r in self.db.execute('SELECT id,text,kind,starts,ends,duration,active FROM server_notices ORDER BY created DESC,rowid DESC LIMIT 30')])

    def content_snapshot(self):
        # A separate console process can edit SQLite; refresh once a second only
        # when economy is accessed. No work is added to map/position polling.
        now = time.monotonic()
        if self._content_cache is None or now >= self._content_checked:
            row = self.db.execute('SELECT revision,data FROM content_revisions ORDER BY revision DESC LIMIT 1').fetchone()
            revision = row[0] if row else 0
            if self._content_cache is None or revision != self._content_cache[0]:
                self._content_cache = (revision, json.loads(row[1]) if row else copy.deepcopy(DEFAULT_CONTENT))
                self._community_goals={DEFAULT_CONTENT['community']['id']:DEFAULT_CONTENT['community']['target']}
                for (raw,) in self.db.execute('SELECT data FROM content_revisions'):
                    event=json.loads(raw)['community'];self._community_goals[event['id']]=event['target']
                self.badge_cache.clear()
            self._content_checked = now + 1
        return self._content_cache

    def content_admin(self, request):
        """Trusted console entry point; no game request may call this method."""
        with self.lock, self.db:
            action = request.get('action')
            if action == 'history':
                return dict(history=[dict(revision=r[0], created=r[1]) for r in self.db.execute('SELECT revision,created FROM content_revisions ORDER BY revision DESC LIMIT 30')])
            if action == 'get':
                self._content_cache = None
                revision, data = self.content_snapshot()
                return dict(revision=revision, content=copy.deepcopy(data))
            if action == 'get_revision':
                number=request.get('revision')
                check(type(number) is int and number>=0,'Revisao invalida.')
                row=self.db.execute('SELECT data FROM content_revisions WHERE revision=?',(number,)).fetchone()
                check(number==0 or row,'Revisao nao encontrada.')
                current=self.db.execute('SELECT COALESCE(MAX(revision),0) FROM content_revisions').fetchone()[0]
                return dict(revision=current,source_revision=number,content=json.loads(row[0]) if row else copy.deepcopy(DEFAULT_CONTENT))
            check(action == 'set', 'Acao administrativa desconhecida.')
            data = validate_content(request.get('content'))
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT revision,data FROM content_revisions ORDER BY revision DESC LIMIT 1').fetchone()
            revision = row[0] if row else 0
            check(type(request.get('expected_revision')) is int and request['expected_revision'] == revision,
                  'O conteudo mudou no servidor. Carregue novamente antes de publicar.')
            previous = json.loads(row[1]) if row else DEFAULT_CONTENT
            if data == previous:
                return dict(revision=revision, content=copy.deepcopy(data), unchanged=True)
            # Keep stable IDs meaningful across edits and restores.
            versions = [DEFAULT_CONTENT] + [json.loads(r[0]) for r in self.db.execute('SELECT data FROM content_revisions')]
            for old in versions:
                for key, mission in data['missions'].items():
                    if key in old['missions']:
                        check(mission['kind'] == old['missions'][key]['kind'], 'Para mudar o tipo da missao, use um ID novo: '+key)
                before, after = old['community'], data['community']
                if before['id'] == after['id']:
                    check((before['target'], before['coins']) == (after['target'], after['coins']),
                          'Meta e premio de um evento existente sao fixos. Use um ID novo para outro evento.')
            self.db.execute('INSERT INTO content_revisions VALUES(?,?,?)', (revision+1, int(time.time()), json.dumps(data, ensure_ascii=False)))
            self._content_cache = None
            return dict(revision=revision+1, content=copy.deepcopy(data))
