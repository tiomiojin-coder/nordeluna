import concurrent.futures
import importlib.util
import json
import re
import secrets
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
        self.areas = dict(plaza=1, coliseum=5, market=6)
        self.store = relay.Store(self.path, self.areas)
        self.credentials = {}

    def prepare(self, action, data, invoke=None):
        invoke = invoke or (lambda action, **data: self.store.handle(dict(protocol=1, action=action, **data)))
        if action in ("create", "join", "map_join") and isinstance(data.get("profile"), dict) and "account" not in data:
            credentials = self.credentials.get(data.get("resume"))
            if credentials is None:
                name = re.sub("[^A-Za-z0-9_]", "", data["profile"].get("name", "Tester"))[:12]
                if len(name) < 3:
                    name = "Tester"
                base, counter = name, 1
                while self.store.db.execute("SELECT 1 FROM accounts WHERE normalized=?", (name.lower(),)).fetchone():
                    counter += 1; name = base + str(counter)
                credentials = dict(id=secrets.token_hex(16), secret=secrets.token_hex(32))
                invoke("account_register", account=credentials, nickname=name)
            data = dict(data, account=credentials)
        if action == "map_update" and isinstance(data.get("state"), dict):
            row = self.store.presence.get(data.get("token"))
            if row:
                state = dict(direction=2, frame=0, moving=False, character="trainer_RED", seq=row["movement_seq"] + 1)
                state.update(data["state"])
                target = state.get("map")
                if type(target) is int and target in self.areas.values() and target != row["authorized_map"]:
                    invoke("map_enter", token=data["token"], map=target)
                data = dict(data, state=state)
        return data

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def call(self, action, **data):
        data = self.prepare(action, data)
        result = self.store.handle(dict(protocol=1, action=action, **data))
        if action == "map_join":
            self.credentials[result["token"]] = data["account"]
        return result

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
        self.store = relay.Store(self.path, self.areas)
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
        self.store = relay.Store(self.path, self.areas)
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

    def test_chat_room_isolation_server_nick_time_and_idempotent_send(self):
        def join(room="ABCDEFGH", build="new", name="Luna"):
            return self.call("map_join", room=room, build=build, profile=dict(name=name))
        a, b = join(), join(name="Sol")
        outside, old = join("BCDEFGHJ"), join(build="old")
        state = dict(map=1, x=3, y=4)
        def update(player, **data):
            return self.call("map_update", token=player["token"], state=state, chat_enabled=True, **data)
        client_id = "a" * 32
        with patch.object(relay.time, "time", return_value=1794012345):
            sent = update(a, chat=dict(client_id=client_id, text="Olá Noctgeist!", nick="Impostor", timestamp=0))
        self.assertEqual(sent["chat_ack"], client_id)
        row = sent["messages"][0]
        self.assertEqual((row["nick"], row["timestamp"], row["text"]), ("Luna", 1794012345, "Olá Noctgeist!"))
        self.assertEqual(update(b)["messages"], sent["messages"])
        self.assertEqual(update(outside)["messages"], [])
        self.assertEqual(update(old)["messages"], [])
        again = update(a, chat=dict(client_id=client_id, text="Olá Noctgeist!"))
        self.assertEqual(len(again["messages"]), 1)
        self.assertEqual(update(b, after=row["id"], chat_epoch=sent["chat_epoch"])["messages"], [])
        with self.assertRaises(relay.ProtocolError):
            update(a, chat=dict(client_id="b" * 32, text="spam"))
        with self.assertRaises(relay.ProtocolError):
            update(b, chat=dict(client_id=client_id, text="Olá Noctgeist!"))
        with self.assertRaises(relay.ProtocolError):
            update(a, chat=dict(client_id=client_id, text="edited"))
        for text in ("", "x" * 121, "<red>bad", "line\nbreak"):
            with self.assertRaises(relay.ProtocolError):
                update(b, chat=dict(client_id="c" * 32, text=text))
        self.assertNotIn(a["token"], json.dumps(sent))

    def test_room_resume_after_presence_expiry_and_explicit_leave(self):
        args = dict(room="ABCDEFGH", build="new", profile=dict(name="Luna"))
        with patch.object(relay.time, "monotonic", return_value=100) as clock:
            original = self.call("map_join", **args)
            self.call("map_update", token=original["token"], state=dict(map=1, x=1, y=1),
                      chat_enabled=True, chat=dict(client_id="a" * 32, text="Mensagem com resposta perdida"))
            clock.return_value = 120
            restored = self.call("map_join", resume=original["token"], **args)
            self.assertTrue(restored["resumed"])
            self.assertEqual((restored["token"], restored["id"], restored["room"]),
                             (original["token"], original["id"], "ABCDEFGH"))
            retried = self.call("map_update", token=restored["token"], state=dict(map=1, x=1, y=1),
                                chat_enabled=True, chat=dict(client_id="a" * 32, text="Mensagem com resposta perdida"))
            self.assertEqual(len(retried["messages"]), 1)
            self.assertEqual(retried["chat_ack"], "a" * 32)
            wrong = self.call("map_join", resume=original["token"], **dict(args, room="BCDEFGHJ"))
            self.assertFalse(wrong["resumed"])
            self.assertNotEqual(wrong["id"], original["id"])
            with self.assertRaises(relay.ProtocolError):
                self.call("map_leave", token=restored["token"])
            fresh = self.call("map_join", resume=original["token"], **args)
            self.assertFalse(fresh["resumed"])
            clock.return_value = 250
            expired = self.call("map_join", resume=fresh["token"], **args)
            self.assertFalse(expired["resumed"])

    def test_chat_history_bounded_epoch_restart_and_no_trade_database_changes(self):
        args = dict(room="ABCDEFGH", build="new", profile=dict(name="Luna"))
        with patch.object(relay.time, "monotonic", return_value=100) as clock:
            player = self.call("map_join", **args)
            for number in range(85):
                clock.return_value = 100 + number * 3
                view = self.call("map_update", token=player["token"], state=dict(map=1, x=1, y=1),
                                 chat_enabled=True, chat=dict(client_id=format(number, "032x"), text="Oi " + str(number)))
            self.assertEqual(len(view["messages"]), 80)
            self.assertEqual(view["messages"][0]["text"], "Oi 5")
            old_epoch = view["chat_epoch"]
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0], 0)
        self.store.db.close()
        self.store = relay.Store(self.path, self.areas)
        fresh = self.call("map_join", **args)
        view = self.call("map_update", token=fresh["token"], state=dict(map=1, x=1, y=1),
                         chat_enabled=True, chat_epoch=old_epoch, after=99999)
        self.assertNotEqual(old_epoch, view["chat_epoch"])
        self.assertEqual([message["text"] for message in view["messages"]],
                         ["Oi " + str(number) for number in range(5, 85)])

    def test_trade_commit_survives_restart_and_cancel(self):
        a, b = self.pair("trade")
        first = self.call("confirm", **self.auth(a))
        self.assertEqual(first["status"], "active")
        self.assertEqual(self.call("confirm", **self.auth(b))["status"], "committed")
        self.store.db.close()
        self.store = relay.Store(self.path, self.areas)
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
        def raw_post(data):
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as response:
                return json.load(response)
        def invoke(action, **data):
            return raw_post(dict(protocol=1, action=action, **data))
        def post(data):
            action = data["action"]
            return raw_post(self.prepare(action, data, invoke))
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
            sent = post(dict(protocol=1, action="map_update", token=a["token"], state=state,
                             chat_enabled=True, chat=dict(client_id="a" * 32, text="Olá, praça!")))
            history = post(dict(protocol=1, action="map_update", token=b["token"], state=state, chat_enabled=True))
            self.assertEqual(history["messages"], sent["messages"])
            self.assertEqual(history["messages"][0]["nick"], "NickA")
            self.assertIsInstance(history["messages"][0]["timestamp"], int)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                post(dict(protocol=1, action="poll", code=host["code"], token="stolen"))
            self.assertEqual(caught.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main(verbosity=2)
