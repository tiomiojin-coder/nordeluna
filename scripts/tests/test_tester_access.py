import json
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from server.relay import Store,RelayHTTPServer,Handler


class TesterAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/'relay.db';self.store=Store(str(self.file))
        self.addCleanup(lambda:self.store.db.close())

    def call(self,action,**data):return self.store.handle(dict(protocol=1,action=action,**data))
    def invite(self):return self.store.tester_admin(dict(action='create',label='Amigo',days=7))
    def redeem(self,invite,device=None):return self.call('tester_redeem',code=invite['invitation'],device=device or secrets.token_hex(16))['credentials']

    def test_once_persistent_hashed_and_revocable(self):
        invite=self.invite();credentials=self.redeem(invite)
        self.assertTrue(self.call('tester_access',tester=credentials)['authorized'])
        with self.assertRaises(ValueError):self.redeem(invite)
        with self.assertRaises(ValueError):self.call('tester_access',tester=dict(credentials,device=secrets.token_hex(16)))
        rows=self.store.tester_admin(dict(action='list'))
        self.assertNotIn(invite['invitation'],json.dumps(rows));self.assertNotIn(credentials['token'],json.dumps(rows))
        stored=json.dumps(list(self.store.db.execute('SELECT * FROM tester_access')))
        self.assertNotIn(invite['invitation'],stored);self.assertNotIn(credentials['token'],stored)
        self.store.db.close();self.store=Store(str(self.file))
        self.assertTrue(self.call('tester_access',tester=credentials)['authorized'])
        self.store.tester_admin(dict(action='revoke',id=invite['id']))
        with self.assertRaises(ValueError):self.call('tester_access',tester=credentials)

    def test_expiry_and_public_routes_cannot_manage_or_read_keys(self):
        invite=self.invite();credentials=self.redeem(invite)
        self.store.db.execute('UPDATE tester_access SET expires=1');self.store.db.commit()
        with self.assertRaises(ValueError):self.call('tester_access',tester=credentials)
        for action in ('tester_admin','tester_publish','tester_create','tester_delete'):
            with self.assertRaises(Exception):self.call(action)
        self.assertNotIn('keys',self.call('health'))

    def test_delete_invalidates_redeemed_key_without_removing_online_account(self):
        account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32))
        self.call('account_register',nickname='KeepCoins',account=account)
        invitation=self.invite();credentials=self.redeem(invitation)
        self.call('account_info',account=account,channel='testers',tester=credentials)
        other=self.invite()
        result=self.store.tester_admin(dict(action='delete',id=invitation['id']))
        self.assertTrue(result['deleted'])
        self.assertEqual([r['id'] for r in self.store.tester_admin(dict(action='list'))['invitations']],[other['id']])
        with self.assertRaises(ValueError):self.call('tester_access',tester=credentials)
        with self.assertRaises(ValueError):self.redeem(invitation)
        self.assertEqual(self.call('account_info',account=account)['nickname'],'KeepCoins')
        self.store.db.close();self.store=Store(str(self.file))
        with self.assertRaises(ValueError):self.call('tester_access',tester=credentials)

    def test_delete_unclaimed_key_does_not_affect_other_invites(self):
        invitation=self.invite();other=self.invite()
        with self.assertRaises(ValueError):self.store.tester_admin(dict(action='delete',id='missing'))
        self.assertEqual(len(self.store.tester_admin(dict(action='list'))['invitations']),2)
        self.store.tester_admin(dict(action='delete',id=invitation['id']))
        with self.assertRaises(ValueError):self.redeem(invitation)
        self.assertTrue(self.call('tester_access',tester=self.redeem(other))['authorized'])

    def test_gate_binds_online_identity_and_stable_stays_open(self):
        account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32))
        self.call('account_register',nickname='Teste',account=account)
        # Stable identity remains usable without any invitation.
        self.assertEqual(self.call('account_info',account=account)['nickname'],'Teste')
        with self.assertRaises(ValueError):self.call('account_info',account=account,channel='testers')
        invitation=self.invite();credentials=self.redeem(invitation)
        self.call('account_info',account=account,channel='testers',tester=credentials)
        self.assertTrue(self.store.update_is_tester(dict(account=account,tester=credentials)))
        other=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32));self.call('account_register',nickname='Outro',account=other)
        with self.assertRaises(ValueError):self.call('account_info',account=other,channel='testers',tester=credentials)
        self.store.tester_admin(dict(action='revoke',id=invitation['id']))
        with self.assertRaises(ValueError):self.call('account_info',account=account,channel='testers',tester=credentials)

    def test_room_and_presence_cannot_omit_channel_to_bypass(self):
        self.store.db.execute('INSERT INTO rooms VALUES(?,?)',('ABCDEF',json.dumps(dict(build='test-build-testers'))))
        with self.assertRaises(ValueError):self.call('peek',code='ABCDEF')
        self.store.presence['token']=dict(build='test-build-testers')
        with self.assertRaises(ValueError):self.call('map_update',token='token')
        with self.assertRaises(ValueError):self.call('account_info',build='version-testers')

    def test_signed_catalog_only_and_no_plaintext_packages(self):
        row=dict(encrypted=True,code=22,compatibility='fixture-testers',size=48,sha256='a'*64,plain=dict(size=20,sha256='b'*64),url='https://github.com/tiomiojin-coder/nordeluna/releases/download/test/test.apk.locked')
        data=dict(schema=1,channels=dict(testers=dict(android=row)))
        payload=dict(catalog=dict(manifest=json.dumps(data),signature='f'*512),keys=dict(android='c'*64))
        with self.assertRaises(ValueError):self.store.tester_admin(dict(action='publish',payload=payload))
        with patch('server.testers.verify_signature'):
            self.store.tester_admin(dict(action='publish',payload=payload))
            credentials=self.redeem(self.invite())
            self.assertEqual(self.call('tester_access',tester=credentials)['release'],payload)
            row['encrypted']=False;payload['catalog']['manifest']=json.dumps(data)
            with self.assertRaises(ValueError):self.store.tester_admin(dict(action='publish',payload=payload))

    def test_invitation_rate_limit_does_not_apply_to_gameplay(self):
        http=RelayHTTPServer(('127.0.0.1',0),Handler)
        self.addCleanup(http.server_close)
        self.assertTrue(all(http.tester_limit('127.0.0.1') for _ in range(30)))
        self.assertFalse(http.tester_limit('127.0.0.1'))
        self.assertTrue(http.tester_limit('127.0.0.2'))


if __name__=='__main__':unittest.main()
