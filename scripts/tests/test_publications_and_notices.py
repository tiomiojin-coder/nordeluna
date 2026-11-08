import copy
import importlib.util
from pathlib import Path
import secrets
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
from server.relay import Store
from server.content import DEFAULT_CONTENT
spec=importlib.util.spec_from_file_location('publication_review',ROOT/'scripts/publication-tools.py');review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)


class ReviewTests(unittest.TestCase):
    def test_diff_shows_removed_product_and_old_and_new_prices(self):
        before=copy.deepcopy(DEFAULT_CONTENT);after=copy.deepcopy(before)
        after['shop']['balls5']['price']=45;after['shop'].pop('aipom_egg')
        rows=review.content_diff(before,after)
        self.assertTrue(any(r['change']=='Preco' and r['before']=='25 LC' and r['after']=='45 LC' for r in rows))
        self.assertTrue(any(r['change']=='Removido' and 'aipom_egg' in r['name'] for r in rows))
        self.assertEqual(before,DEFAULT_CONTENT)
    def test_map_summary_includes_ids_new_maps_events_and_resources(self):
        rows=review.package_diff(dict(files=[dict(path='Data/Map039.rxdata',size=123,base_sha256='a'*64),dict(path='Data/Map042.rxdata',size=456,base_sha256=None),dict(path='Data/CommonEvents.rxdata',size=30,base_sha256='b'*64),dict(path='Graphics/UI/test.png',size=50,base_sha256=None)]))
        self.assertIn('Mapa 39',rows[0]['name']);self.assertEqual(rows[1]['change'],'Novo');self.assertIn('Eventos comuns',rows[2]['name']);self.assertIn('Recurso',rows[3]['name'])


class NoticesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=str(Path(self.temp.name)/'relay.sqlite3');self.store=Store(self.path);self.addCleanup(lambda:self.store.db.close())
        self.account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32));self.call('account_register',nickname='Lunar')
    def call(self,action,**data):return self.store.handle(dict(protocol=1,action=action,account=self.account,**data))
    def create(self,**values):return self.store.notice_admin(dict(action='create',text='Evento na praca!',kind='event',duration=8,ends=int(time.time())+3600,**values))
    def test_scheduling_expiry_and_disable_are_enforced(self):
        now=int(time.time());self.create(starts=now+120)
        self.assertEqual(self.store.notice_view(),[])
        with patch('server.content.time.time',return_value=now+130):self.assertEqual(len(self.store.notice_view()),1)
        with patch('server.content.time.time',return_value=now+4000):self.assertEqual(self.store.notice_view(),[])
        row=self.create()['notices'][0];self.assertEqual(len(self.store.notice_view()),1)
        self.store.notice_admin(dict(action='disable',id=row['id']));self.assertEqual(self.store.notice_view(),[])
    def test_map_connection_piggybacks_notice_with_throttling_no_new_writes(self):
        self.create();joined=self.call('map_join',room='PRACA',profile={},build='notice-test')
        self.assertEqual(len(joined['notices']),1)
        state=dict(map=39,x=3,y=4,seq=1,direction=2,frame=0,moving=False,character='trainer_RED')
        reply=self.call('map_update',token=joined['token'],state=state)
        self.assertNotIn('notices',reply)
        self.store.presence[joined['token']]['notice_at']=0
        state['seq']=2;self.assertEqual(len(self.call('map_update',token=joined['token'],state=state)['notices']),1)
        queries=[];self.store.db.set_trace_callback(queries.append)
        for _ in range(100):self.store.notice_view()
        self.store.db.set_trace_callback(None);self.assertEqual(queries,[])
    def test_external_console_publish_reaches_running_process(self):
        self.assertEqual(self.store.notice_view(),[])
        editor=Store(self.path)
        try:editor.notice_admin(dict(action='create',text='Manutencao em breve',kind='maintenance',ends=int(time.time())+3600,duration=8))
        finally:editor.db.close()
        self.store._notice_checked=0
        self.assertEqual(self.store.notice_view()[0]['kind'],'maintenance')
    def test_players_cannot_publish_notices(self):
        for action in ('notice_admin','notice_create'):
            with self.assertRaises(Exception):self.call(action,text='forged',kind='info',ends=int(time.time())+3600,duration=8)
        self.assertEqual(self.store.notice_view(),[])
