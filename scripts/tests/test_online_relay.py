import concurrent.futures
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("relay", ROOT / "server/relay.py")
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "relay.sqlite3")
        self.store = relay.Store(self.path)

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def call(self, action, **data):
        return self.store.handle(dict(protocol=1, action=action, **data))

    def pair(self, mode="battle"):
        args = dict(mode=mode, build="cross-platform-1", profile=dict(name="Luna", type="POKEMONTRAINER_Red", id=1), payload=[{"test": "pokemon"}])
        a = self.call("create", **args)
        b = self.call("join", code=a["code"], **args)
        return a, b

    def auth(self, player):
        return dict(code=player["code"], token=player["token"])

    def test_rooms_auth_and_version(self):
        a, b = self.pair()
        self.assertEqual((a["side"], b["side"]), (0, 1))
        view = self.call("poll", **self.auth(a))
        self.assertNotIn("token", json.dumps(view))
        with self.assertRaises(relay.ProtocolError):
            self.call("poll", code=a["code"], token="wrong")
        with self.assertRaises(relay.ProtocolError):
            self.call("join", code=a["code"], build="old", mode="battle")
        with self.assertRaises(relay.ProtocolError):
            self.call("join", code=a["code"], build="cross-platform-1", mode="battle")
        with self.assertRaises(relay.ProtocolError):
            self.store.handle(dict(protocol=2, action="health"))

    def test_turns_sealed_immutable_and_idempotent(self):
        a, b = self.pair()
        first = self.call("exchange", key="turn:0", value={"kind": "move", "index": 0}, **self.auth(a))
        self.assertFalse(first["ready"])
        self.assertIsNone(first["values"])
        hidden = self.call("exchange", key="turn:0", **self.auth(b))
        self.assertIsNone(hidden["values"])
        with self.assertRaises(relay.ProtocolError):
            self.call("exchange", key="turn:0", value={"kind": "move", "index": 1}, **self.auth(a))
        last = self.call("exchange", key="turn:0", value={"kind": "move", "index": 2}, **self.auth(b))
        self.assertEqual(last["values"][0]["index"], 0)
        self.assertEqual(last["values"][1]["index"], 2)
        self.assertEqual(last, self.call("exchange", key="turn:0", value={"kind": "move", "index": 2}, **self.auth(b)))

    def test_rules_owned_by_host_and_persisted(self):
        args = dict(mode="battle", build="new", rules="level50",
                    profile=dict(name="Luna", type="TRAINER", id=3), payload=[{"pokemon": "Pikachu"}])
        a = self.call("create", **args)
        args["rules"] = "free"
        b = self.call("join", code=a["code"], **args)
        self.assertEqual(a["rules"], "level50")
        self.assertEqual(b["rules"], "level50")
        self.store.db.close()
        self.store = relay.Store(self.path)
        self.assertEqual(self.call("poll", **self.auth(a))["rules"], "level50")
        args["rules"] = "arbitrary_ruby_class"
        with self.assertRaises(relay.ProtocolError):
            self.call("create", **args)

    def test_preview_choices_stay_sealed(self):
        a, b = self.pair()
        first = self.call("exchange", key="preview:0", value={"lead": 2, "rules": "free"}, **self.auth(a))
        self.assertIsNone(first["values"])
        second = self.call("exchange", key="preview:0", value={"lead": 0, "rules": "free"}, **self.auth(b))
        self.assertEqual([choice["lead"] for choice in second["values"]], [2, 0])

    def test_custom_rules_inspection_and_team_size(self):
        rules = dict(level=50, count=2, legendaries=False, format="double")
        args = dict(mode="battle", build="new", rules=rules,
                    profile=dict(name="MeuNick", type="TRAINER", id=4), payload=[{}, {}])
        host = self.call("create", **args)
        info = self.call("inspect", code=host["code"])
        self.assertEqual(info, dict(mode="battle", build="new", rules=rules))
        self.assertNotIn("players", info)
        with self.assertRaises(relay.ProtocolError):
            self.call("join", **dict(args, code=host["code"], payload=[{}]))
        guest = self.call("join", **dict(args, code=host["code"], rules="free"))
        self.assertEqual(guest["rules"], rules)
        self.assertEqual(guest["players"][0]["profile"]["name"], "MeuNick")
        self.store.db.close()
        self.store = relay.Store(self.path)
        self.assertEqual(self.call("poll", **self.auth(host))["rules"], rules)
        for bad in (dict(rules, level=True), dict(rules, count=1), dict(rules, count=7),
                    dict(rules, legendaries=1), dict(rules, format="triple"), dict(rules, extra=True)):
            with self.assertRaises(relay.ProtocolError):
                self.call("create", **dict(args, rules=bad))

    def test_map_emotes_scope_cooldown_expiry_and_no_receipt_changes(self):
        args = dict(build="same", profile=dict(name="Nick", type="TRAINER", id=4))
        with patch.object(relay.time, "monotonic", return_value=100) as clock:
            a = self.call("map_join", **args)
            b = self.call("map_join", **args)
            other_version = self.call("map_join", **dict(args, build="old"))
            state = dict(map=5, x=10, y=11)
            self.call("map_update", token=a["token"], state=state, emote="wave")
            view = self.call("map_update", token=b["token"], state=state)
            self.assertEqual(view["peers"][0]["emote"], "wave")
            self.assertNotIn("token", json.dumps(view))
            self.assertEqual(self.call("map_update", token=other_version["token"], state=state)["peers"], [])
            self.assertEqual(self.call("map_update", token=b["token"], state=dict(state, map=6))["peers"], [])
            with self.assertRaises(relay.ProtocolError):
                self.call("map_update", token=a["token"], state=state, emote="battle")
            clock.return_value = 103
            self.call("map_update", token=a["token"], state=state, emote="battle")
            self.assertEqual(self.call("map_update", token=b["token"], state=state)["peers"][0]["sequence"], 2)
            clock.return_value = 108
            self.assertIsNone(self.call("map_update", token=b["token"], state=state)["peers"][0]["emote"])
            self.call("map_leave", token=b["token"])
            with self.assertRaises(relay.ProtocolError):
                self.call("map_update", token=b["token"], state=state)
            clock.return_value = 124
            with self.assertRaises(relay.ProtocolError):
                self.call("map_update", token=a["token"], state=state)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0], 0)

    def test_map_rejects_forged_positions_and_emotes(self):
        token = self.call("map_join", build="new", profile=dict(name="Nick"))["token"]
        for state in (dict(map=True, x=1, y=1), dict(map=1, x=-1, y=1), dict(map=1, x=1), dict(map=1, x=1, y=10000)):
            with self.assertRaises(relay.ProtocolError):
                self.call("map_update", token=token, state=state)
        with self.assertRaises(relay.ProtocolError):
            self.call("map_update", token=token, state=dict(map=1, x=1, y=1), emote="arbitrary text")

    def test_trade_commit_survives_restart_and_cancel(self):
        a, b = self.pair("trade")
        first = self.call("confirm", **self.auth(a))
        self.assertEqual(first["status"], "active")
        self.assertEqual(self.call("confirm", **self.auth(b))["status"], "committed")
        self.store.db.close()
        self.store = relay.Store(self.path)
        self.assertEqual(self.call("poll", **self.auth(a))["status"], "committed")
        self.assertEqual(self.call("cancel", **self.auth(b))["status"], "committed")
        self.assertEqual(self.call("confirm", **self.auth(a))["status"], "committed")

    def test_trade_cancel_wins_before_commit(self):
        a, b = self.pair("trade")
        self.call("confirm", **self.auth(a))
        self.assertEqual(self.call("cancel", **self.auth(b))["status"], "cancelled")
        with self.assertRaises(relay.ProtocolError):
            self.call("confirm", **self.auth(b))

    def test_cancel_confirm_race_is_atomic(self):
        for _ in range(20):
            a, b = self.pair("trade")
            self.call("confirm", **self.auth(a))
            def invoke(action):
                try:
                    return self.call(action, **self.auth(b))["status"]
                except relay.ProtocolError:
                    return "rejected"
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                results = list(pool.map(invoke, ["confirm", "cancel"]))
            final = self.call("poll", **self.auth(a))["status"]
            self.assertIn(final, ("committed", "cancelled"))
            self.assertFalse("committed" in results and "cancelled" in results)

    def test_mode_limits_and_cancelled_battle(self):
        a, b = self.pair()
        with self.assertRaises(relay.ProtocolError):
            self.call("confirm", **self.auth(a))
        with self.assertRaises(relay.ProtocolError):
            self.call("exchange", key="../../bad", value=1, **self.auth(a))
        self.call("cancel", **self.auth(a))
        with self.assertRaises(relay.ProtocolError):
            self.call("exchange", key="turn:0", value=1, **self.auth(b))

    def test_real_http_two_clients_and_rejected_payload(self):
        server = relay.ThreadingHTTPServer(("127.0.0.1", 0), relay.Handler)
        server.store = self.store
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/api"
        def post(data):
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as response:
                return json.load(response)
        try:
            args = dict(protocol=1, build="same-PC-Android", mode="trade", profile=dict(name="Sol", type="TRAINER", id=8), payload=[{"pokemon": "Pikachu"}])
            host = post(dict(args, action="create"))
            guest = post(dict(args, action="join", code=host["code"]))
            self.assertTrue(host["ok"] and guest["ok"])
            post(dict(protocol=1, action="confirm", **self.auth(host)))
            committed = post(dict(protocol=1, action="confirm", **self.auth(guest)))
            self.assertEqual(committed["status"], "committed")
            a = post(dict(protocol=1, action="map_join", build="same", profile=dict(name="NickA")))
            b = post(dict(protocol=1, action="map_join", build="same", profile=dict(name="NickB")))
            state = dict(map=1, x=2, y=3)
            post(dict(protocol=1, action="map_update", token=a["token"], state=state, emote="celebrate"))
            peers = post(dict(protocol=1, action="map_update", token=b["token"], state=state))["peers"]
            self.assertEqual((peers[0]["name"], peers[0]["emote"]), ("NickA", "celebrate"))
            with self.assertRaises(urllib.error.HTTPError) as caught:
                post(dict(protocol=1, action="poll", code=host["code"], token="stolen"))
            self.assertEqual(caught.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main(verbosity=2)
