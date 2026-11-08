import concurrent.futures
import importlib.util
import json
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('luna_relay',Path(__file__).resolve().parents[2]/'server/relay.py')
relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)


class LunaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=str(Path(self.temp.name)/'relay.sqlite3');self.store=relay.Store(self.path)
        self.addCleanup(lambda:self.store.db.close())
        self.a=self.register('Lunar');self.b=self.register('Solar');self.c=self.register('Noctgeist')
    def register(self,name):
        account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32))
        self.store.handle(dict(protocol=1,action='account_register',account=account,nickname=name));return account
    def call(self,action,account=None,**data):return self.store.handle(dict(protocol=1,action=action,account=account or self.a,**data))
    def player(self,**data):return dict(profile=dict(name='Lunar',id=1,type='PLAYER'),payload=[dict(species='NOCTGEIST')],build='luna-test',**data)
    def pair(self,mode='battle'):
        a=self.call('create',mode=mode,**self.player())
        b=self.call('join',account=self.b,mode=mode,code=a['code'],**self.player())
        return a,b
    def auth(self,row):return dict(code=row['code'],token=row['token'])
    def credit(self,amount):
        with self.store.db:self.store.credit(self.a['id'],'test-credit',amount)
    def test_daily_claim_is_atomic_and_only_server_sets_amount(self):
        self.call('economy_sync')
        second=relay.Store(self.path)
        try:
            def claim(store):return store.handle(dict(protocol=1,action='economy_claim',account=self.a,mission='visit',amount=9999999))
            with concurrent.futures.ThreadPoolExecutor(2) as pool:list(pool.map(claim,[self.store,second]))
            self.assertEqual(self.store.balance(self.a['id']),10)
            self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM coin_ledger').fetchone()[0],1)
        finally:second.db.close()
        with self.assertRaises(ValueError):self.call('economy_claim',mission='battle1')
        with self.assertRaises(relay.ProtocolError):self.call('economy_sync',account=dict(self.a,secret='f'*64))
    def test_purchase_retry_and_recovery_do_not_charge_twice(self):
        self.credit(200)
        order=secrets.token_hex(16)
        first=self.call('economy_buy',order=order,sku='aipom_egg')
        second=self.call('economy_buy',order=order,sku='aipom_egg')
        self.assertEqual(first,second);self.assertEqual(first['balance'],120)
        self.assertTrue(first['claim']['rewards'][0]['egg'])
        self.assertEqual(self.call('economy_order',order=order)['claim']['id'],first['claim']['id'])
        self.assertIsNone(self.call('economy_order',account=self.b,order=order)['claim'])
        with self.assertRaises(ValueError):self.call('economy_buy',order=order,sku='noctgeist')
        with self.assertRaises(ValueError):self.call('economy_buy',order=secrets.token_hex(16),sku='outfits')
        self.assertEqual(self.store.balance(self.a['id']),120)
    def test_simultaneous_purchases_cannot_overdraw(self):
        self.credit(100);second=relay.Store(self.path)
        try:
            def buy(store):
                try:return store.handle(dict(protocol=1,action='economy_buy',account=self.a,order=secrets.token_hex(16),sku='aipom_egg'))
                except ValueError:return None
            with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(buy,[self.store,second]))
            self.assertEqual(sum(r is not None for r in results),1)
            self.assertEqual(self.store.balance(self.a['id']),20)
        finally:second.db.close()
    def test_both_battle_results_required_and_cancel_preserves_proof(self):
        a,b=self.pair()
        with self.assertRaises(ValueError):self.call('battle_result',result=1,**self.auth(a))
        for turn in range(2):
            for player in [a,b]:self.call('exchange',key=f'turn:{turn}',value={'move':0},**self.auth(player))
        self.assertFalse(self.call('battle_result',result=1,**self.auth(a))['confirmed'])
        self.call('cancel',**self.auth(a))
        self.assertTrue(self.call('battle_result',account=self.b,result=1,**self.auth(b))['confirmed'])
        self.call('battle_result',account=self.b,result=1,**self.auth(b))
        view=self.call('economy_sync')
        self.assertEqual(next(r for r in view['missions'] if r['id']=='battle1')['progress'],1)
        self.assertEqual(view['community']['progress'],1)
        self.assertEqual(self.call('economy_claim',mission='battle1')['balance'],20)
        self.assertEqual(self.call('economy_claim',mission='battle1')['balance'],20)
    def test_disputed_results_and_unconfirmed_trade_do_not_grant_progress(self):
        a,b=self.pair()
        for turn in range(2):
            for player in [a,b]:self.call('exchange',key=f'turn:{turn}',value={},**self.auth(player))
        self.call('battle_result',result=1,**self.auth(a))
        self.assertTrue(self.call('battle_result',account=self.b,result=2,**self.auth(b))['disputed'])
        self.assertEqual(self.call('economy_sync')['community']['progress'],0)
        a,b=self.pair('trade');self.call('confirm',**self.auth(a))
        with self.assertRaises(ValueError):self.call('economy_claim',mission='trade1')
        self.call('confirm',account=self.b,**self.auth(b));self.call('confirm',account=self.b,**self.auth(b))
        self.assertEqual(self.call('economy_claim',mission='trade1')['balance'],15)
    def test_community_unlock_and_participation_survive_restart(self):
        with self.store.db:
            for n in range(50):self.store.activity('battle',dict(code=f'TEST{n:04d}',players=[{'profile':{'account_id':self.a['id']}},{'profile':{'account_id':self.b['id']}}]))
        result=self.call('economy_sync')['community'];self.assertEqual(result['progress'],50)
        self.assertEqual(self.call('economy_claim',mission=result['id'])['balance'],100)
        self.assertEqual(self.call('economy_claim',mission=result['id'])['balance'],100)
        with self.assertRaises(ValueError):self.call('economy_claim',account=self.c,mission=result['id'])
        self.store.db.close();self.store=relay.Store(self.path)
        self.assertEqual(self.call('economy_sync')['balance'],100)
    def test_matchmaking_is_scoped_authenticated_and_uses_normal_rooms(self):
        a=self.call('match_enter',rules='free',**self.player())
        self.assertEqual(a['state'],'waiting')
        self.assertEqual(self.call('match_enter',rules='free',**self.player())['ticket'],a['ticket'])
        c=self.call('match_enter',account=self.c,rules='level50',**self.player())
        self.assertEqual(c['state'],'waiting')
        b=self.call('match_enter',account=self.b,rules='free',**self.player())
        a=self.call('match_poll',ticket=a['ticket'])
        self.assertEqual(a['state'],'matched');self.assertEqual(b['state'],'matched')
        self.assertEqual(a['room']['code'],b['room']['code'])
        self.assertEqual(a['room']['side'],0);self.assertEqual(b['room']['side'],1)
        self.assertNotIn(b['room']['token'],json.dumps(a['room']))
        with self.assertRaises(ValueError):self.call('match_cancel',account=self.c,ticket=a['ticket'])
        self.call('match_cancel',ticket=a['ticket'])
        self.assertEqual(self.call('match_poll',account=self.b,ticket=b['ticket'])['state'],'cancelled')
    def test_expired_match_entries_are_removed(self):
        a=self.call('match_enter',rules='free',**self.player())
        self.store.matchmaking[self.a['id']]['seen']-=30
        with self.assertRaises(ValueError):self.call('match_poll',ticket=a['ticket'])
