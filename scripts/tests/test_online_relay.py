import concurrent.futures
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
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
            with self.assertRaises(urllib.error.HTTPError) as caught:
                post(dict(protocol=1, action="poll", code=host["code"], token="stolen"))
            self.assertEqual(caught.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main(verbosity=2)
