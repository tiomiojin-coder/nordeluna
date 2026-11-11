"""Strict account/area protocol tests: no automatic authentication test helper."""
import concurrent.futures
import importlib.util
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("area_relay", Path(__file__).resolve().parents[2] / "server/relay.py")
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)


class AreasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "online.sqlite3")
        self.areas = dict(plaza=10, coliseum=11, market=12)
        self.store = relay.Store(self.path, self.areas)

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def call(self, action, **data):
        return self.store.handle(dict(protocol=1, action=action, **data))

    def register(self, name):
        account = dict(id=secrets.token_hex(16), secret=secrets.token_hex(32))
        self.call("account_register", account=account, nickname=name)
        return account

    def join(self, account, room="PRACA", **data):
        return self.call("map_join", account=account, room=room, profile=dict(name="ForgedName"), build="area-test", **data)

    @staticmethod
    def state(map=10, seq=1, **extra):
        value = dict(map=map, x=4, y=5, direction=2, character="trainer_RED", moving=False, frame=0, seq=seq)
        value.update(extra)
        return value

    def test_nearest_limit_keeps_chat_count_across_other_maps(self):
        sessions=[]
        for i in range(44):
            account=self.register('Crowd'+str(i));session=self.join(account);sessions.append(session)
            target=11 if i==43 else 10
            if target==11:self.call('map_enter',token=session['token'],map=11)
            self.call('map_update',token=session['token'],state=self.state(map=target,seq=1,x=i,y=0),chat_enabled=True)
        result=self.call('map_update',token=sessions[0]['token'],state=self.state(seq=2,x=0,y=0),chat_enabled=True)
        self.assertEqual(len(result['peers']),40)
        self.assertEqual([p['x'] for p in result['peers']],list(range(1,41)))
        self.assertEqual(result['members'],44)
        first=result['peers'][0]
        self.call('map_update',token=sessions[1]['token'],state=self.state(seq=2,x=1,y=0,character='trainer_NEW'))
        fresh=self.call('map_update',token=sessions[0]['token'],state=self.state(seq=3,x=0,y=0),known_peers={first['id']:first['profile_revision']})['peers'][0]
        self.assertNotEqual(first['profile_revision'],fresh['profile_revision'])
        self.assertEqual(fresh['character'],'trainer_NEW')

    def test_nickname_offline_persistence_case_and_owner(self):
        lunar = self.register("Lunar")
        other = dict(id=secrets.token_hex(16), secret=secrets.token_hex(32))
        with self.assertRaisesRegex(relay.ProtocolError, "utilizado"):
            self.call("account_register", account=other, nickname="lUnAr")
        self.assertFalse(self.call("account_check", nickname="LUNAR")["available"])
        self.assertTrue(self.call("account_check", nickname="LUNAR", account=lunar)["available"])
        self.store.db.close(); self.store = relay.Store(self.path, self.areas)
        self.assertEqual(self.call("account_info", account=lunar), dict(id=lunar["id"], nickname="Lunar"))
        with self.assertRaises(relay.ProtocolError):
            self.call("account_register", account=dict(lunar, secret="f" * 64), nickname="Stolen")
        self.call("account_register", account=lunar, nickname="LunarNew")
        self.assertTrue(self.call("account_check", nickname="Lunar")["available"])
        for nickname in ("", "aa", "X" * 17, " Lunar", "Lunar ", "Lu\u200bnar", "L\nunar", "ADMIN", "Ｎordeluna", "a-b"):
            with self.assertRaises(relay.ProtocolError):
                self.call("account_register", account=other, nickname=nickname)

    def test_atomic_nickname_race_across_database_connections(self):
        other_store = relay.Store(self.path, self.areas)
        try:
            def register(item):
                store, name = item
                try:
                    store.handle(dict(protocol=1, action="account_register", nickname=name,
                                      account=dict(id=secrets.token_hex(16), secret=secrets.token_hex(32))))
                    return "registered"
                except relay.ProtocolError:
                    return "rejected"
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                results = list(pool.map(register, [(self.store, "Lunar"), (other_store, "lunar")]))
            self.assertCountEqual(results, ["registered", "rejected"])
            self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 1)
        finally:
            other_store.db.close()

    def test_disabled_maps_and_unauthenticated_clients_do_not_create_presence(self):
        account = self.register("Trainer")
        with self.assertRaises(relay.ProtocolError):
            self.call("map_join", profile=dict(name="Trainer"), build="area-test")
        with self.assertRaises(relay.ProtocolError):
            self.join(account, area_map=99)
        self.assertEqual(self.store.presence, {})
        self.store.areas = dict(plaza=None, coliseum=None, market=None)
        with self.assertRaises(relay.ProtocolError):
            self.join(account)
        self.assertEqual(self.store.presence, {})

    def test_only_plaza_can_be_enabled_while_other_two_areas_are_pending(self):
        self.store.areas = dict(plaza=39, coliseum=None, market=None)
        player = self.join(self.register("Lunar"))
        result = self.call("map_update", token=player["token"], state=self.state(map=39))
        self.assertEqual(result["map"], 39)
        for target in (None, 10, 11, 12):
            with self.assertRaises(relay.ProtocolError):
                self.call("map_enter", token=player["token"], map=target)

    def test_three_maps_same_session_explicit_leave_and_ghost_scope(self):
        a = self.join(self.register("Lunar"))
        b = self.join(self.register("Solar"))
        private = self.join(self.register("Private"), room="ABCDEFGH")
        update = lambda player, state: self.call("map_update", token=player["token"], state=state)
        update(a, self.state())
        view = update(b, self.state())
        self.assertEqual(view["peers"][0]["name"], "Lunar")
        self.assertEqual(view["peers"][0]["account_id"], a["account_id"])
        self.assertNotIn("secret", str(view))
        self.assertEqual(update(private, self.state())["peers"], [])
        for index, target in enumerate((11, 12), 2):
            self.call("map_enter", token=a["token"], map=target)
            self.assertEqual(update(a, self.state(map=target, seq=index))["peers"], [])
        with self.assertRaises(relay.ProtocolError):
            self.call("map_enter", token=a["token"], map=99)
        with self.assertRaises(relay.ProtocolError):
            update(a, self.state(map=10, seq=8)) # no matching map_enter
        self.call("map_leave", token=a["token"])
        self.assertNotIn(a["token"], self.store.presence)
        self.assertNotIn(a["token"], self.store.resumable)
        self.call("map_leave", token=b["token"])
        self.assertEqual(len(self.store.presence), 1) # private instance only

    def test_old_packets_forged_identity_and_cached_metadata(self):
        a = self.join(self.register("Lunar")); b = self.join(self.register("Solar"))
        self.call("map_update", token=a["token"], state=self.state(seq=2))
        for state in (self.state(seq=1), self.state(seq=2), self.state(seq=3, name="Impostor"), self.state(seq=3, account_id="0"*32)):
            with self.assertRaises(relay.ProtocolError):
                self.call("map_update", token=a["token"], state=state)
        reply = self.call("map_update", token=b["token"], state=self.state())
        first = reply["peers"][0]
        second = self.call("map_update", token=b["token"], state=self.state(seq=2),
                           known_peers={first["id"]: first["profile_revision"]})["peers"][0]
        self.assertNotIn("name", second); self.assertNotIn("character", second)
        self.assertEqual(second["seq"], 2)
        self.assertEqual(self.store.presence[a["token"]]["name"], "Lunar")

    def test_same_account_single_presence_and_resume_owner(self):
        account = self.register("Lunar"); a = self.join(account)
        other = self.register("Solar")
        with self.assertRaises(relay.ProtocolError):
            self.join(other, resume=a["token"])
        b = self.join(account)
        self.assertNotIn(a["token"], self.store.presence)
        self.assertIn(b["token"], self.store.presence)
        self.assertEqual(len(self.store.presence), 1)

    def test_confirmation_keepalive_does_not_publish_campaign_position(self):
        account = self.register("Lunar")
        with patch.object(relay.time, "monotonic", return_value=100) as clock:
            player = self.join(account)
            for now in range(103, 163, 3):
                clock.return_value = now
                self.call("map_ping", token=player["token"])
            self.assertIsNone(self.store.presence[player["token"]]["map"])
            self.assertEqual(self.store.presence[player["token"]]["seen"], 160)
            self.call("map_leave", token=player["token"])
            self.assertEqual(self.store.presence, {})

    def test_account_migration_does_not_modify_existing_room_receipts(self):
        old = '{"code":"OLDROOM1","status":"committed","players":[]}'
        self.store.db.execute("INSERT INTO rooms VALUES(?,?)", ("OLDROOM1", old));self.store.db.commit()
        self.register("Lunar")
        self.store.db.close();self.store=relay.Store(self.path,self.areas)
        self.assertEqual(self.store.db.execute("SELECT data FROM rooms WHERE code='OLDROOM1'").fetchone()[0], old)
