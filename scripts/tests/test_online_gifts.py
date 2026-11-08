import concurrent.futures
import importlib.util
import json
from pathlib import Path
import secrets
import tempfile
import time
import unittest
from unittest.mock import Mock
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('gift_relay',Path(__file__).resolve().parents[2]/'server/relay.py')
relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)


class GiftTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=str(Path(self.temp.name)/'relay.sqlite3');self.store=relay.Store(self.path)
        self.addCleanup(lambda:self.store.db.close())
        self.a=self.register('Lunar');self.b=self.register('Solar')
    def register(self,name):
        account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32))
        self.store.handle(dict(protocol=1,action='account_register',account=account,nickname=name))
        return account
    def call(self,action,account=None,**data):
        return self.store.handle(dict(protocol=1,action=action,account=account or self.a,**data))
    def create(self,**data):
        return self.store.gift_admin(dict(action='create',code='BEMVINDO',title='Boas vindas',rewards=[dict(kind='item',id='POKEBALL',quantity=5),dict(kind='pokemon',species='NOCTGEIST',level=10,shiny=True)],**data))
    def test_preview_reserve_begin_ack_and_rename_are_idempotent(self):
        self.create()
        self.assertIn('preview',self.call('gift_preview',code='bemvindo'))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM gift_claims').fetchone()[0],0)
        a=self.call('gift_reserve',code='BEMVINDO')['claim']
        self.assertEqual(a,self.call('gift_reserve',code='BEMVINDO')['claim'])
        with self.assertRaises(ValueError):self.call('gift_ack',claim=a['id'])
        self.assertEqual(self.call('gift_begin',claim=a['id'])['state'],'issued')
        self.assertEqual(self.call('gift_begin',claim=a['id'])['state'],'issued')
        self.call('gift_ack',claim=a['id']);self.call('gift_ack',claim=a['id'])
        self.store.handle(dict(protocol=1,action='account_register',account=self.a,nickname='LunarNovo'))
        self.assertEqual(self.call('gift_reserve',code='BEMVINDO')['claim']['state'],'delivered')
        self.assertEqual(len(self.call('gift_history')['claims']),1)
        with self.assertRaises(ValueError):self.call('gift_status',account=self.b,claim=a['id'])
        self.assertNotIn('secret',json.dumps(self.call('gift_history')))
    def test_recovery_survives_restart_expiry_and_disable(self):
        self.create(expires=int(time.time())+60)
        a=self.call('gift_reserve',code='BEMVINDO')['claim']
        self.store.gift_admin(dict(action='disable',code='BEMVINDO'))
        with self.assertRaises(ValueError):self.call('gift_reserve',account=self.b,code='BEMVINDO')
        self.store.db.close();self.store=relay.Store(self.path)
        with patch('time.time',return_value=time.time()+120):
            self.assertEqual(self.call('gift_status',claim=a['id'])['state'],'reserved')
            self.assertEqual(self.call('gift_begin',claim=a['id'])['state'],'issued')
            self.call('gift_ack',claim=a['id'])
    def test_last_global_slot_is_atomic_across_connections(self):
        self.create(limit=1)
        second=relay.Store(self.path)
        try:
            def reserve(pair):
                store,account=pair
                try:return store.handle(dict(protocol=1,action='gift_reserve',account=account,code='BEMVINDO'))
                except ValueError:return None
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                results=list(pool.map(reserve,[(self.store,self.a),(second,self.b)]))
            self.assertEqual(sum(row is not None for row in results),1)
            self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM gift_claims').fetchone()[0],1)
        finally:second.db.close()
    def test_authentication_public_admin_and_immutable_rewards(self):
        self.create()
        with self.assertRaises(relay.ProtocolError):self.call('gift_preview',account=dict(self.a,secret='0'*64),code='BEMVINDO')
        with self.assertRaises(ValueError):self.call('gift_admin',code='BEMVINDO')
        with self.assertRaises(ValueError):self.create()
        with self.assertRaises(ValueError):self.store.gift_admin(dict(action='create',code='INVALID',title='Bad',rewards=[dict(kind='pokemon',species='NOCTGEIST',level=True)]))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM gifts').fetchone()[0],1)
    def test_expired_and_invalid_codes_do_not_consume_claims(self):
        self.create(expires=int(time.time())+5)
        with patch('time.time',return_value=time.time()+10):
            with self.assertRaises(ValueError):self.call('gift_reserve',code='BEMVINDO')
        for code in ['?','a'*100,{},'NAOEXISTE']:
            with self.assertRaises(ValueError):self.call('gift_reserve',code=code)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM gift_claims').fetchone()[0],0)


    def test_1000_read_polls_do_not_write_database(self):
        player=dict(profile=dict(name='Lunar',id=1,type='PLAYER'),payload=[{}],build='test',mode='battle')
        room=self.call('create',**player)
        statements=[];self.store.db.set_trace_callback(statements.append)
        for _ in range(1000):self.call('poll',code=room['code'],token=room['token'])
        writes=[s for s in statements if s.lstrip().split(' ',1)[0].upper() in ('INSERT','UPDATE','DELETE','REPLACE')]
        self.assertEqual(writes,[])
        self.store.db.set_trace_callback(None)

    def test_http_worker_limit_recovers_without_unbounded_threads(self):
        server=relay.RelayHTTPServer(('127.0.0.1',0),relay.Handler);server.store=self.store
        try:
            for _ in range(24):self.assertTrue(server.workers.acquire(False))
            request=Mock()
            server.shutdown_request=Mock()
            server.process_request(request,('127.0.0.1',1234))
            self.assertTrue(request.sendall.call_args[0][0].startswith(b'HTTP/1.0 503'))
            server.shutdown_request.assert_called_once_with(request)
            for _ in range(24):server.workers.release()
            self.assertTrue(server.workers.acquire(False));server.workers.release()
        finally:
            server.server_close()
