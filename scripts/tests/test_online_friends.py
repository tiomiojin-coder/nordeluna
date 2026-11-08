import concurrent.futures
import importlib.util
import json
from pathlib import Path
import secrets
import tempfile
import time
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('friends_relay',Path(__file__).resolve().parents[2]/'server/relay.py')
relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)


class FriendsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=str(Path(self.temp.name)/'relay.sqlite3')
        self.store=relay.Store(self.path)
        self.addCleanup(lambda:self.store.db.close())
        self.a=self.register('Lunar');self.b=self.register('Solar');self.c=self.register('Noctgeist')
    def call(self,account,action,**data):
        return self.store.handle(dict(protocol=1,account=account,action=action,**data))
    def register(self,nickname):
        account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32))
        self.call(account,'account_register',nickname=nickname)
        return account
    def sync(self,account,status='available',busy=False,build='test-build'):
        return self.call(account,'social_sync',presence=dict(status=status,busy=busy,build=build))
    def friends(self):
        self.call(self.a,'social_add',nickname='solar')
        self.call(self.b,'social_friend_reply',target=self.a['id'],accept=True)
        self.sync(self.a);self.sync(self.b)
    def room(self,account,mode='battle'):
        return self.call(account,'create',mode=mode,build='test-build',profile=dict(name='Forged',id=1,type='PLAYER'),payload=[dict(species='NOCTGEIST')],rules='free')
    def invite(self,room=None):
        room=room or self.room(self.a)
        reply=self.call(self.a,'social_invite',target=self.b['id'],code=room['code'],mode=room['mode'],room_token=room['token'])
        return room,reply['invitation']

    def test_mutual_consent_persistence_rename_and_private_status(self):
        self.call(self.a,'social_add',nickname='SoLaR')
        self.assertEqual(self.sync(self.a)['friends'],[])
        self.assertEqual(self.sync(self.b)['incoming'][0]['nickname'],'Lunar')
        with self.assertRaises(relay.ProtocolError):self.call(self.c,'social_friend_reply',target=self.a['id'],accept=True)
        self.call(self.b,'social_friend_reply',target=self.a['id'],accept=True)
        self.call(self.b,'social_friend_reply',target=self.a['id'],accept=True)
        self.call(self.b,'account_register',nickname='SolarNovo')
        self.sync(self.b,'busy')
        view=self.sync(self.a)
        self.assertEqual(view['friends'][0]['nickname'],'SolarNovo')
        self.assertEqual(view['friends'][0]['status'],'busy')
        self.assertEqual(self.sync(self.c)['friends'],[])
        self.assertNotIn('secret',json.dumps(view))
        self.store.db.close();self.store=relay.Store(self.path)
        self.assertEqual(self.sync(self.a)['friends'][0]['status'],'offline')
        self.call(self.a,'social_remove',target=self.b['id'])
        self.assertEqual(self.sync(self.b)['friends'],[])

    def test_invite_ownership_confirmation_reserved_join_and_trade_receipt(self):
        self.friends();room,invitation=self.invite(self.room(self.a,'trade'))
        self.assertEqual(self.call(self.a,'social_invite',target=self.b['id'],code=room['code'],mode='trade',room_token=room['token'])['invitation'],invitation)
        with self.assertRaises(relay.ProtocolError):self.call(self.c,'social_invite_reply',invitation=invitation,accept=True)
        with self.assertRaises(relay.ProtocolError):self.call(self.b,'join',code=room['code'],mode='trade',build='test-build',profile=dict(name='X',type='PLAYER',id=1),payload=[{}])
        acceptance=self.call(self.b,'social_invite_reply',invitation=invitation,accept=True)
        self.assertEqual(acceptance['code'],room['code'])
        with self.assertRaises(relay.ProtocolError):self.call(self.c,'join',code=room['code'],mode='trade',build='test-build',profile=dict(name='X',type='PLAYER',id=1),payload=[{}])
        joined=self.call(self.b,'join',code=room['code'],mode='trade',build='test-build',profile=dict(name='X',type='PLAYER',id=1),payload=[{}])
        self.assertEqual(joined['status'],'active')
        self.store.handle(dict(protocol=1,action='confirm',code=room['code'],token=room['token']))
        self.store.handle(dict(protocol=1,action='confirm',code=room['code'],token=joined['token']))
        before=json.dumps(self.store.load(room['code']),sort_keys=True)
        self.call(self.a,'social_remove',target=self.b['id'])
        with patch.object(relay.time,'time',return_value=time.time()+200000):self.sync(self.a)
        self.assertEqual(json.dumps(self.store.load(room['code']),sort_keys=True),before)

    def test_decline_expiry_busy_build_and_host_cancellation(self):
        self.friends()
        room=self.room(self.a)
        self.sync(self.b,'busy')
        with self.assertRaises(relay.ProtocolError):self.invite(room)
        self.sync(self.b,build='other-build')
        with self.assertRaises(relay.ProtocolError):self.invite(room)
        self.sync(self.b)
        _,invitation=self.invite(room)
        self.call(self.b,'social_invite_reply',invitation=invitation,accept=False)
        self.assertEqual(self.store.load(room['code'])['status'],'cancelled')
        room,invitation=self.invite()
        with patch.object(relay.time,'time',return_value=time.time()+121):
            self.assertEqual(self.sync(self.b)['invite_count'],0)
            self.assertEqual(self.store.load(room['code'])['status'],'cancelled')
        room,invitation=self.invite()
        self.store.handle(dict(protocol=1,action='cancel',code=room['code'],token=room['token']))
        self.assertEqual(self.sync(self.b)['invite_count'],0)

    def test_authentication_status_ttl_and_bad_inputs(self):
        self.friends()
        bad=dict(self.a,secret='0'*64)
        for action in ['social_sync','social_add','social_remove','social_invite_reply']:
            with self.assertRaises(relay.ProtocolError):self.call(bad,action)
        with self.assertRaises(relay.ProtocolError):self.call(self.a,'social_friend_reply',target={},accept=True)
        self.assertEqual(self.sync(self.a)['friends'][0]['status'],'available')
        self.store.social_presence[self.b['id']]['seen']-=36
        self.assertEqual(self.sync(self.a)['friends'][0]['status'],'offline')
        self.sync(self.b)
        room=self.room(self.b)
        self.assertEqual(self.sync(self.a)['friends'][0]['status'],'busy')
        self.store.handle(dict(protocol=1,action='cancel',code=room['code'],token=room['token']))
        self.assertEqual(self.sync(self.a)['friends'][0]['status'],'available')

    def test_concurrent_request_is_single_pending_record(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _:self.call(self.a,'social_add',nickname='Solar'),range(8)))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM friend_requests').fetchone()[0],1)
        with self.assertRaises(relay.ProtocolError):self.call(self.a,'social_add',nickname='Lunar')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0],0)

    def map_join(self,account,room='PRACA',x=5,seq=1):
        joined=self.call(account,'map_join',room=room,profile={'name':'forged'},build='test-build')
        self.store.handle(dict(protocol=1,action='map_update',token=joined['token'],state=dict(
            map=39,x=x,y=5,seq=seq,direction=2,frame=0,moving=False,character='trainer_RED')))
        return joined

    def test_nearby_card_invitation_and_status_outside_metadata_cache(self):
        a=self.map_join(self.a)
        self.map_join(self.b,x=7)
        self.sync(self.a);self.sync(self.b)
        self.assertFalse(self.store.is_friend(self.a['id'],self.b['id']))
        room,invitation=self.invite()
        accepted=self.call(self.b,'social_invite_reply',invitation=invitation,accept=True)
        self.assertEqual(accepted['code'],room['code'])
        self.assertEqual(self.store.load(room['code'])['invite_scope'],'nearby')
        with self.assertRaises(relay.ProtocolError):
            self.call(self.c,'join',code=room['code'],build='test-build',profile={},payload=[{'species':'AIPOM'}])
        self.call(self.b,'social_sync',presence=dict(status='available',busy=True,activity='trade',build='test-build'))
        state=dict(map=39,x=5,y=5,seq=2,direction=2,frame=0,moving=False,character='trainer_RED')
        packet=self.store.handle(dict(protocol=1,action='map_update',token=a['token'],state=state))
        peer=packet['peers'][0]
        self.assertEqual(peer['status'],'trade')
        state['seq']=3
        self.sync(self.b,'busy')
        cached=self.store.handle(dict(protocol=1,action='map_update',token=a['token'],state=state,
                                      known_peers={peer['id']:peer['profile_revision']}))['peers'][0]
        self.assertNotIn('character',cached)
        self.assertEqual(cached['status'],'busy')
        self.assertEqual(cached['profile_revision'],peer['profile_revision'])
        self.assertNotIn('secret',json.dumps(cached))

    def test_nearby_invites_reject_other_instances_distance_expired_and_busy(self):
        self.map_join(self.a)
        self.map_join(self.b,room='ABCDEFGH')
        self.sync(self.a);self.sync(self.b)
        with self.assertRaises(relay.ProtocolError):self.invite()
        self.map_join(self.b,x=30)
        with self.assertRaises(relay.ProtocolError):self.invite()
        self.map_join(self.b,x=6)
        self.sync(self.b,'busy')
        with self.assertRaises(relay.ProtocolError):self.invite()
        self.sync(self.b)
        for row in self.store.presence.values():row['seen']-=16
        with self.assertRaises(relay.ProtocolError):self.invite()
        with self.assertRaises(relay.ProtocolError):
            self.call(self.b,'social_sync',presence=dict(status='available',busy=True,activity='forged',build='test-build'))
