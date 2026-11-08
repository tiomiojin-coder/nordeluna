import importlib.util
from pathlib import Path
import secrets
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('badge_relay',Path(__file__).resolve().parents[2]/'server/relay.py')
relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)


class BadgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=str(Path(self.temp.name)/'relay.sqlite3');self.store=relay.Store(self.path)
        self.addCleanup(lambda:self.store.db.close())
        self.a=self.register('Lunar');self.b=self.register('Solar')
    def register(self,name):
        account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32))
        self.store.handle(dict(protocol=1,action='account_register',account=account,nickname=name));return account
    def call(self,action,account=None,**data):return self.store.handle(dict(protocol=1,action=action,account=account or self.a,**data))
    def participate(self,n=1):
        with self.store.db:
            for i in range(n):self.store.activity('battle',{'code':f'EVNT{i:04d}','players':[{'profile':{'account_id':self.a['id']}},{'profile':{'account_id':self.b['id']}}]})
    def test_unearned_badges_cannot_be_equipped(self):
        self.assertEqual(self.call('economy_sync')['badges'],[])
        for badge in ('lunar_participant','community_50',{},'forged'):
            with self.assertRaises(ValueError):self.call('economy_badges',badge=badge)
        self.assertEqual(self.store.balance(self.a['id']),0)
    def test_unlock_select_and_hide_survive_restart_without_currency_effect(self):
        self.participate(50)
        view=self.call('economy_sync')
        self.assertEqual({row['id'] for row in view['badges']},{'lunar_participant','community_50'})
        self.assertEqual(view['equipped_badge'],'community_50')
        self.assertEqual(self.call('economy_badges',badge='lunar_participant')['equipped_badge'],'lunar_participant')
        self.call('economy_badges',badge='')
        self.store.db.close();self.store=relay.Store(self.path)
        self.assertEqual(self.call('economy_sync')['equipped_badge'],'')
        self.assertEqual(self.store.balance(self.a['id']),0)
    def test_map_badge_updates_without_reloading_character_metadata(self):
        self.participate()
        a=self.call('map_join',room='PRACA',profile={},build='badge-test')
        b=self.call('map_join',account=self.b,room='PRACA',profile={},build='badge-test')
        def state(seq):return dict(map=39,x=4,y=5,seq=seq,direction=2,frame=0,moving=False,character='trainer_RED')
        self.call('map_update',account=self.b,token=b['token'],state=state(1))
        first=self.call('map_update',token=a['token'],state=state(1))['peers'][0]
        self.assertEqual(first['badge'],'lunar_participant')
        self.call('economy_badges',account=self.b,badge='')
        second=self.call('map_update',token=a['token'],state=state(2),known_peers={first['id']:first['profile_revision']})['peers'][0]
        self.assertEqual(second['badge'],'')
        self.assertEqual(second['profile_revision'],first['profile_revision'])
        self.assertNotIn('character',second)
        with self.assertRaises(relay.ProtocolError):self.call('map_update',token=a['token'],state=dict(state(3),badge='community_50'))
    def test_warm_badges_do_not_query_database_per_frame(self):
        self.store.badge_view(self.a['id'])
        statements=[];self.store.db.set_trace_callback(statements.append)
        for _ in range(100):self.store.badge_view(self.a['id'])
        self.assertEqual(statements,[])
        self.store.db.set_trace_callback(None)
        self.participate()
        self.assertEqual(self.store.badge_view(self.a['id'])['equipped_badge'],'lunar_participant')
