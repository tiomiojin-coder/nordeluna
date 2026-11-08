"""Moderation uses temporary accounts/keys and never contacts an external relay."""
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("moderation_relay", ROOT / "server/relay.py")
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)


class ModerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "relay.sqlite3")
        self.areas = dict(plaza=1, coliseum=5, market=6)
        self.store = relay.Store(self.path, self.areas)
        self.addCleanup(lambda: self.store.db.close())
        self.owner = self.register("TiagoTeste")
        self.mod = self.register("NoctisTeste")
        self.player = self.register("Lunar")
        self.other = self.register("Solar")
        self.admin("set_owner", self.owner)
        self.key = self.admin("grant", self.mod)["moderator_key"]

    def register(self, nickname):
        account = dict(id=secrets.token_hex(16), secret=secrets.token_hex(32))
        self.call("account_register", account=account, nickname=nickname)
        return account

    def call(self, action, account=None, **data):
        return self.store.handle(dict(protocol=1, action=action, account=account or self.player, **data))

    def admin(self, action, account=None, **data):
        if account is not None:
            data["target"] = account["id"]
        return self.store.moderation_admin(dict(action=action, reason="Teste administrativo", **data))

    def staff(self, action, account=None, key=None, **data):
        if account is not None:
            data["target"] = account["id"]
        return self.store.moderation_staff(self.key if key is None else key,
                                           dict(action=action, reason="Teste de moderacao", **data))

    def restart(self):
        self.store.db.close()
        self.store = relay.Store(self.path, self.areas)

    def join_map(self, account=None, room="PRACA", build="moderation-test"):
        return self.call("map_join", account=account, room=room, build=build,
                         profile=dict(name="Nome forjado"))

    def update_map(self, session, **data):
        row = self.store.presence[session["token"]]
        state = dict(map=row["authorized_map"], x=1, y=2,
                     seq=row["movement_seq"] + 1, direction=2, frame=0,
                     moving=False, character="trainer_RED")
        return self.call("map_update", token=session["token"], state=state,
                         chat_enabled=True, **data)

    def chat(self, session, text="Mensagem de teste", client_id=None, **data):
        return self.update_map(session, chat=dict(client_id=client_id or secrets.token_hex(16), text=text), **data)

    def pair(self, mode="trade"):
        args = dict(mode=mode, build="moderation-test", rules="free",
                    profile=dict(name="Lunar", type="PLAYER", id=1), payload=[{}])
        host = self.call("create", **args)
        guest = self.call("join", account=self.other, code=host["code"], **args)
        return host, guest

    @staticmethod
    def auth(session):
        return dict(code=session["code"], token=session["token"])

    def test_staff_key_is_separate_hashed_and_never_returned_by_reads(self):
        self.assertRegex(self.key, r"^nmod_[0-9a-f]{64}$")
        stored = self.store.db.execute("SELECT key_hash FROM moderators WHERE account=?", (self.mod["id"],)).fetchone()[0]
        self.assertEqual(stored, hashlib.sha256(self.key.encode()).hexdigest())
        for action in ("session", "accounts", "history", "audit"):
            response = self.staff(action)
            encoded = json.dumps(response)
            self.assertNotIn(self.key, encoded)
            self.assertNotIn(stored, encoded)
            for account in (self.owner, self.mod, self.player, self.other):
                self.assertNotIn(account["secret"], encoded)
        actor = self.staff("session")["actor"]
        self.assertEqual((actor["id"], actor["role"]), (self.mod["id"], "moderator"))

    def test_invalid_or_game_credentials_do_not_authenticate_staff(self):
        for key in (None, "", "Bearer " + self.key, self.player["secret"],
                    self.mod["secret"], "nmod_" + "0" * 64, "nmod_" + "f" * 63,
                    "nmod_" + "A" * 64, {}, 1):
            with self.subTest(key_type=type(key).__name__):
                with self.assertRaises(relay.StaffAuthError):
                    self.store.moderation_staff(key, dict(action="session"))

    def test_player_api_cannot_assign_roles_or_reach_console_actions(self):
        for action in ("moderation", "moderation_admin", "moderation_staff", "set_owner", "grant", "ban"):
            with self.subTest(action=action):
                with self.assertRaises((ValueError, relay.ProtocolError)):
                    self.call(action, account=self.player, target=self.player["id"],
                              role="owner", actor=dict(role="owner"), moderator_key=self.key)
        self.assertEqual(self.store.moderation_role(self.player["id"]), "player")
        self.assertEqual(self.store.moderation_owner(), self.owner["id"])

    def test_staff_cannot_self_assign_manage_team_or_spoof_owner(self):
        for action, target in (("set_owner", self.mod), ("grant", self.mod),
                               ("grant", self.player), ("revoke", self.owner),
                               ("revoke", self.mod)):
            with self.subTest(action=action, target=target["id"]):
                with self.assertRaises(ValueError):
                    self.staff(action, target, role="owner", actor=dict(role="owner", id=self.owner["id"]))
        self.assertEqual(self.store.moderation_owner(), self.owner["id"])
        self.assertEqual(self.store.moderation_role(self.mod["id"]), "moderator")
        self.assertEqual(self.store.moderation_role(self.player["id"]), "player")

    def test_staff_cannot_punish_owner_self_or_other_moderators(self):
        self.admin("grant", self.other)
        before = self.store.db.execute("SELECT COUNT(*) FROM moderation_audit").fetchone()[0]
        for target in (self.owner, self.mod, self.other):
            for action in ("mute", "unmute", "kick", "ban", "unban"):
                with self.subTest(action=action, target=target["id"]):
                    with self.assertRaises(ValueError):
                        self.staff(action, target, seconds=60, role="owner")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM moderation_audit").fetchone()[0], before)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM moderation_sanctions").fetchone()[0], 0)

    def test_staff_cannot_hide_messages_by_owner_or_moderators(self):
        for account in (self.owner, self.mod):
            message = self.chat(self.join_map(account))["messages"][-1]
            for action in ("hide_message", "restore_message"):
                with self.subTest(action=action, account=account["id"]):
                    with self.assertRaises(ValueError):
                        self.staff(action, message_id=message["id"])
        self.assertEqual(self.store.db.execute("SELECT SUM(hidden) FROM chat_history").fetchone()[0], 0)

    def test_mute_bounds_require_integer_and_failed_actions_are_atomic(self):
        before = self.store.db.execute("SELECT COUNT(*) FROM moderation_audit").fetchone()[0]
        for seconds in (0, -1, 7201, 2**63, True, False, 1.5, "7200", None):
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    self.staff("mute", self.player, seconds=seconds)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM moderation_audit").fetchone()[0], before)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM moderation_sanctions").fetchone()[0], 0)
        for seconds in (1, 7200):
            with patch("time.time", return_value=1800000000):
                response = self.staff("mute", self.player, seconds=seconds)
                self.assertEqual(response["until"], 1800000000 + seconds)

    def test_mute_blocks_new_chat_until_expiry_but_maps_remain_usable(self):
        session = self.join_map()
        with patch("time.time", return_value=1800000000):
            result = self.staff("mute", self.player, seconds=2)
            self.assertEqual(self.update_map(session)["messages"], [])
            self.call("map_ping", token=session["token"], chat_enabled=True)
            with self.assertRaises(relay.ModerationError) as error:
                self.chat(session)
            self.assertEqual((error.exception.code, error.exception.until), ("CHAT_MUTED", result["until"]))
        with patch("time.time", return_value=result["until"]):
            self.assertEqual(self.chat(session)["messages"][-1]["text"], "Mensagem de teste")

    def test_unmute_takes_effect_immediately(self):
        session = self.join_map()
        self.staff("mute", self.player, seconds=7200)
        with self.assertRaises(relay.ModerationError):
            self.chat(session)
        self.staff("unmute", self.player)
        self.assertEqual(len(self.chat(session)["messages"]), 1)

    def test_kick_only_rejects_general_plaza_for_sixty_seconds(self):
        plaza = self.join_map()
        with patch("time.time", return_value=1800000000):
            result = self.staff("kick", self.player)
            self.assertEqual(result["until"], 1800000060)
            with self.assertRaises(relay.ModerationError) as error:
                self.update_map(plaza)
            self.assertEqual(error.exception.code, "KICKED")
            with self.assertRaises(relay.ModerationError):
                self.join_map()
            private = self.join_map(room="ABCDEFGH")
            self.assertEqual(self.update_map(private)["room"], "ABCDEFGH")
        with patch("time.time", return_value=result["until"]):
            self.assertEqual(self.join_map()["room"], "PRACA")

    def test_ban_blocks_existing_and_new_presence_and_new_online_rooms(self):
        session = self.join_map()
        self.staff("ban", self.player)
        for operation in (lambda: self.update_map(session),
                          lambda: self.call("map_ping", token=session["token"]),
                          lambda: self.call("map_enter", token=session["token"], map=5),
                          lambda: self.join_map(), lambda: self.join_map(room="ABCDEFGH"),
                          lambda: self.call("create", mode="trade", build="moderation-test",
                                           profile=dict(name="Lunar", type="PLAYER", id=1), payload=[{}]),
                          lambda: self.call("match_enter", rules="free", build="moderation-test",
                                           profile=dict(name="Lunar", type="PLAYER", id=1), payload=[{}])):
            with self.subTest(operation=operation):
                with self.assertRaises(relay.ModerationError) as error:
                    operation()
                self.assertEqual(error.exception.code, "BANNED")
        self.staff("unban", self.player)
        self.assertEqual(self.join_map()["account_id"], self.player["id"])

    def test_ban_hides_live_peer_from_unpunished_players(self):
        punished = self.join_map()
        witness = self.join_map(self.other)
        self.update_map(punished)
        self.assertEqual(len(self.update_map(witness)["peers"]), 1)
        self.staff("ban", self.player)
        self.assertEqual(self.update_map(witness)["peers"], [])

    def test_committed_trade_receipts_remain_recoverable_after_ban_and_restart(self):
        host, guest = self.pair()
        self.call("confirm", **self.auth(host))
        self.assertEqual(self.call("confirm", **self.auth(guest))["status"], "committed")
        self.staff("ban", self.player)
        self.restart()
        for action in ("poll", "cancel"):
            self.assertEqual(self.call(action, **self.auth(host))["status"], "committed")
        self.assertEqual(self.call("poll", account=self.other, **self.auth(guest))["status"], "committed")

    def test_paid_order_and_existing_gift_claim_recovery_survive_ban(self):
        with self.store.db:
            self.store.credit(self.player["id"], "moderation-test-credit", 200)
        order = secrets.token_hex(16)
        bought = self.call("economy_buy", order=order, sku="aipom_egg")
        claim = bought["claim"]["id"]
        self.staff("ban", self.player)
        self.restart()
        self.assertEqual(self.call("economy_order", order=order)["claim"]["id"], claim)
        self.assertEqual(self.call("gift_status", claim=claim)["state"], "reserved")
        self.assertEqual(self.call("gift_begin", claim=claim)["state"], "issued")
        self.assertEqual(self.call("gift_ack", claim=claim)["state"], "delivered")
        self.assertEqual(self.call("gift_ack", claim=claim)["state"], "delivered")
        self.assertEqual(self.store.balance(self.player["id"]), bought["balance"])

    def test_sanctions_follow_account_through_rename_and_restart(self):
        muted = self.staff("mute", self.player, seconds=7200)
        kicked = self.staff("kick", self.player)
        self.call("account_register", nickname="LunarRenomeado")
        self.staff("ban", self.player)
        self.restart()
        account = next(row for row in self.staff("accounts")["accounts"] if row["id"] == self.player["id"])
        self.assertEqual(account["nickname"], "LunarRenomeado")
        self.assertEqual((account["muted_until"], account["kicked_until"], account["banned"]),
                         (muted["until"], kicked["until"], True))
        with self.assertRaises(relay.ModerationError):
            self.join_map()
        self.assertEqual(self.staff("session")["actor"]["role"], "moderator")

    def test_revocation_and_key_rotation_apply_across_live_connections(self):
        second = relay.Store(self.path, self.areas)
        self.addCleanup(second.db.close)
        self.assertEqual(second.moderation_staff(self.key, dict(action="session"))["actor"]["id"], self.mod["id"])
        replacement = self.admin("grant", self.mod)["moderator_key"]
        self.assertNotEqual(self.key, replacement)
        with self.assertRaises(relay.StaffAuthError):
            second.moderation_staff(self.key, dict(action="session"))
        second.moderation_staff(replacement, dict(action="session"))
        self.admin("revoke", self.mod)
        for action in ("session", "accounts", "mute"):
            with self.assertRaises(relay.StaffAuthError):
                second.moderation_staff(replacement, dict(action=action, target=self.player["id"], seconds=1))
        self.restart()
        with self.assertRaises(relay.StaffAuthError):
            self.store.moderation_staff(replacement, dict(action="session"))

    def test_cross_connection_sanctions_refresh_without_restart(self):
        second = relay.Store(self.path, self.areas)
        self.addCleanup(second.db.close)
        with patch("time.monotonic", return_value=100) as clock:
            second.moderation_require_online(self.player["id"])
            self.staff("ban", self.player)
            clock.return_value = 102
            with self.assertRaises(relay.ModerationError):
                second.moderation_require_online(self.player["id"])
            self.staff("unban", self.player)
            clock.return_value = 104
            second.moderation_require_online(self.player["id"])

    def test_cross_connection_hide_resets_live_client_and_restore_survives_restart(self):
        session = self.join_map()
        sent = self.chat(session)
        identity = sent["messages"][-1]["id"]
        second = relay.Store(self.path, self.areas)
        self.addCleanup(second.db.close)
        clock_start = relay.time.monotonic()
        with patch("time.monotonic", return_value=clock_start + 2):
            second.moderation_staff(self.key, dict(action="hide_message", message_id=identity))
            hidden = self.update_map(session, chat_epoch=sent["chat_epoch"], after=identity)
            self.assertEqual(hidden["messages"], [])
            self.assertNotEqual(hidden["chat_epoch"], sent["chat_epoch"])
        second.moderation_staff(self.key, dict(action="restore_message", message_id=identity))
        self.restart()
        restored = self.update_map(self.join_map(), chat_epoch=hidden["chat_epoch"], after=identity)
        self.assertEqual(restored["messages"][-1]["id"], identity)

    def test_kick_cannot_be_bypassed_with_resume_room_case_or_forged_account(self):
        plaza = self.join_map()
        self.staff("kick", self.player)
        for room in ("PRACA", "praca", " PrAcA "):
            with self.subTest(room=room):
                with self.assertRaises(relay.ModerationError):
                    self.call("map_join", room=room, build="moderation-test",
                              profile=dict(name="Solar"), resume=plaza["token"])
        with self.assertRaises(relay.ModerationError):
            self.call("map_ping", account=self.other, token=plaza["token"], room="ABCDEFGH")
        self.call("map_leave", token=plaza["token"])
        self.assertEqual(self.join_map(room="ABCDEFGH")["room"], "ABCDEFGH")

    def test_ban_cancels_active_online_session_without_blocking_cleanup(self):
        host, guest = self.pair("battle")
        self.staff("ban", self.player)
        with self.assertRaises(relay.ModerationError):
            self.call("poll", **self.auth(host))
        self.assertEqual(self.call("poll", account=self.other, **self.auth(guest))["status"], "cancelled")
        self.assertEqual(self.call("cancel", **self.auth(host))["status"], "cancelled")
        with self.assertRaises(relay.ModerationError):
            self.call("exchange", key="turn:0", value={}, **self.auth(host))

    def test_banned_moderator_key_is_suspended_and_cannot_be_regranted(self):
        second = relay.Store(self.path, self.areas)
        self.addCleanup(second.db.close)
        self.admin("ban", self.mod)
        for action in ("session", "history", "mute"):
            with self.assertRaises(relay.StaffAuthError):
                second.moderation_staff(self.key, dict(action=action, target=self.player["id"], seconds=1))
        with self.assertRaises(ValueError):
            self.admin("grant", self.mod)

    def test_account_search_escapes_wildcards_and_history_pagination_is_stable(self):
        self.assertEqual(self.staff("accounts", search="lun")["accounts"][0]["id"], self.player["id"])
        for search in ("%", "_", "!", "' OR 1=1 --"):
            with self.subTest(search=search):
                self.assertEqual(self.staff("accounts", search=search)["accounts"], [])
        for account in (self.player, self.other, self.owner):
            self.chat(self.join_map(account))
        first = self.staff("history", limit=2)
        second = self.staff("history", limit=2, before=first["next_before"])
        self.assertEqual(len(first["messages"]), 2)
        self.assertEqual(len(second["messages"]), 1)
        self.assertGreater(first["messages"][-1]["id"], second["messages"][0]["id"])

    def test_persistent_history_keeps_sender_and_supports_idempotent_retry(self):
        session = self.join_map()
        client_id = secrets.token_hex(16)
        sent = self.chat(session, "Mensagem duravel", client_id)
        original = sent["messages"][-1]
        self.call("account_register", nickname="LunarNovo")
        self.restart()
        resumed = self.join_map()
        view = self.update_map(resumed, chat_epoch=sent["chat_epoch"], after=original["id"])
        self.assertNotEqual(view["chat_epoch"], sent["chat_epoch"])
        self.assertEqual(view["messages"][-1], original)
        again = self.chat(resumed, "Mensagem duravel", client_id)
        self.assertEqual(again["chat_ack"], client_id)
        self.assertEqual(len(again["messages"]), 1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0], 1)
        history = self.staff("history")["messages"][0]
        self.assertEqual((history["account_id"], history["nickname"], history["id"]),
                         (self.player["id"], "Lunar", original["id"]))
        with self.assertRaises((ValueError, relay.ProtocolError)):
            self.chat(resumed, "Mensagem alterada", client_id)

    def test_hide_restore_invalidates_cursors_without_deleting_history(self):
        session = self.join_map()
        client_id = secrets.token_hex(16)
        sent = self.chat(session, client_id=client_id)
        identity = sent["messages"][-1]["id"]
        self.staff("hide_message", message_id=identity)
        hidden = self.update_map(session, chat_epoch=sent["chat_epoch"], after=identity)
        self.assertNotEqual(hidden["chat_epoch"], sent["chat_epoch"])
        self.assertEqual(hidden["messages"], [])
        history = self.staff("history")["messages"]
        self.assertEqual((len(history), history[0]["hidden"]), (1, True))
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0], 1)
        retry = self.chat(session, client_id=client_id)
        self.assertEqual((retry["chat_ack"], retry["messages"]), (client_id, []))
        self.staff("restore_message", message_id=identity)
        restored = self.update_map(session, chat_epoch=hidden["chat_epoch"], after=identity)
        self.assertNotEqual(restored["chat_epoch"], hidden["chat_epoch"])
        self.assertEqual(restored["messages"][-1]["id"], identity)

    def test_history_and_live_chat_are_scoped_by_room_build_and_account(self):
        self.chat(self.join_map(), "Mensagem geral")
        self.chat(self.join_map(self.other, room="ABCDEFGH"), "Mensagem privada")
        self.chat(self.join_map(self.mod, build="other-build"), "Outra versao")
        messages = self.update_map(self.join_map())["messages"]
        self.assertEqual([row["text"] for row in messages], ["Mensagem geral"])
        all_history = self.staff("history", room="")["messages"]
        self.assertEqual(len(all_history), 3)
        private = self.staff("history", room="ABCDEFGH")["messages"]
        self.assertEqual([row["text"] for row in private], ["Mensagem privada"])
        account = self.staff("history", room="", target=self.mod["id"])["messages"]
        self.assertEqual([row["text"] for row in account], ["Outra versao"])

    def test_every_successful_mutation_is_audited_and_reads_are_read_only(self):
        session = self.join_map()
        identity = self.chat(session)["messages"][-1]["id"]
        actions = ("mute", "unmute", "kick", "ban", "unban", "hide_message", "restore_message")
        for action in actions:
            if action in ("hide_message", "restore_message"):
                self.staff(action, message_id=identity)
            else:
                self.staff(action, self.player, seconds=1)
        audit = self.staff("audit")["audit"]
        self.assertEqual([row["action"] for row in audit[:len(actions)]], list(reversed(actions)))
        self.assertTrue(all(row["target"] == self.player["id"] for row in audit[:len(actions)]))
        statements = []
        self.store.db.set_trace_callback(statements.append)
        try:
            for action in ("session", "accounts", "history", "audit"):
                self.staff(action)
        finally:
            self.store.db.set_trace_callback(None)
        self.assertEqual([sql for sql in statements if sql.split(" ", 1)[0].upper() in
                          ("INSERT", "UPDATE", "DELETE", "REPLACE")], [])

    def test_existing_room_and_economy_data_survive_schema_setup(self):
        host, _ = self.pair()
        with self.store.db:
            self.store.credit(self.player["id"], "moderation-preservation", 123)
        room_data = self.store.db.execute("SELECT data FROM rooms WHERE code=?", (host["code"],)).fetchone()[0]
        account_rows = self.store.db.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        self.restart()
        self.assertEqual(self.store.db.execute("SELECT data FROM rooms WHERE code=?", (host["code"],)).fetchone()[0], room_data)
        self.assertEqual(self.store.db.execute("SELECT * FROM accounts ORDER BY id").fetchall(), account_rows)
        self.assertEqual(self.store.balance(self.player["id"]), 123)
        self.assertEqual(self.call("poll", **self.auth(host))["status"], "active")

    def test_moderation_schema_is_additive_for_a_database_without_new_tables(self):
        path = str(Path(self.temp.name) / "legacy.sqlite3")
        with sqlite3.connect(path) as database:
            database.execute("CREATE TABLE rooms(code TEXT PRIMARY KEY,data TEXT NOT NULL)")
            database.execute("INSERT INTO rooms VALUES(?,?)", ("ABCDEFGH", '{"receipt":"preservado"}'))
        database.close()
        store = relay.Store(path, self.areas)
        try:
            self.assertEqual(store.db.execute("SELECT data FROM rooms").fetchone()[0], '{"receipt":"preservado"}')
            self.assertEqual(store.db.execute("SELECT COUNT(*) FROM moderation_audit").fetchone()[0], 0)
        finally:
            store.db.close()

    def test_http_staff_auth_is_separate_and_sanction_errors_include_code_and_until(self):
        server = relay.RelayHTTPServer(("127.0.0.1", 0), relay.Handler)
        server.store = self.store
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def post(path, body, authorization=None):
            headers = {"Content-Type": "application/json"}
            if authorization is not None:
                headers["Authorization"] = authorization
            request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}{path}",
                                             data=json.dumps(body).encode(), headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=3) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)

        try:
            body = dict(action="session", account=self.mod, role="owner")
            for authorization in (None, "Bearer " + self.mod["secret"], "Bearer nmod_" + "0" * 64):
                status, response = post("/moderation", body, authorization)
                self.assertEqual(status, 401)
                self.assertFalse(response["ok"])
            status, response = post("/moderation", body, "Bearer " + self.key)
            self.assertEqual(status, 200)
            self.assertEqual(response["actor"]["role"], "moderator")
            for malformed in (None, [], "session", 1):
                status, response = post("/moderation", malformed, "Bearer " + self.key)
                self.assertEqual(status, 400)
                self.assertFalse(response["ok"])
            status, response = post("/moderation", dict(action="grant", target=self.player["id"],
                                                       role="owner"), "Bearer " + self.key)
            self.assertEqual(status, 400)
            self.assertFalse(response["ok"])
            session = self.join_map()
            until = self.staff("mute", self.player, seconds=7200)["until"]
            status, response = post("/api", dict(protocol=1, action="map_ping", token=session["token"],
                                                 chat_enabled=True, chat=dict(client_id=secrets.token_hex(16), text="Bloqueada")))
            self.assertEqual((status, response["code"], response["until"]), (400, "CHAT_MUTED", until))
            self.admin("revoke", self.mod)
            status, _ = post("/moderation", body, "Bearer " + self.key)
            self.assertEqual(status, 401)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
