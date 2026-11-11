"""Nordeluna relay. Python 3.10+, standard library only. Run behind HTTPS online."""
import argparse
import hashlib
import gzip
import heapq
import hmac
import json
import os
import re
import secrets
import sqlite3
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
try:
    from gifts import GiftService
    from economy import EconomyService
    from updates import UpdateService
    from moderation import ModerationService, ModerationError, StaffAuthError
    from testers import TesterService
except ModuleNotFoundError:
    from server.gifts import GiftService
    from server.economy import EconomyService
    from server.updates import UpdateService
    from server.moderation import ModerationService, ModerationError, StaffAuthError
    from server.testers import TesterService

PROTOCOL = 1
REVISION = 20
VERSION = "0.10.8"
FEATURES = ["friends", "invitations", "gifts", "luna_coins", "missions", "matchmaking", "community", "cosmetic_badges", "live_content", "content_updates", "tester_releases", "tester_access", "notices", "moderation", "wardrobe"]
MAX_BODY = 262144
KEEPALIVE_REQUESTS = 128
KEEPALIVE_IDLE_SECONDS = 5
HTTP_WORKERS = 32
PERSISTENT_CONNECTIONS = 16
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEFAULT_AREAS = {"plaza": 39, "coliseum": 40, "market": 41}


class ProtocolError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise ProtocolError(message)


def validate_rules(rules):
    if isinstance(rules, str):
        require(rules in ("free", "level50"), "Regras desconhecidas.")
        return rules
    require(isinstance(rules, dict) and set(rules) == {"level", "count", "legendaries", "format"}, "Regras invalidas.")
    require(type(rules["level"]) is int and rules["level"] in (0, 25, 50, 100), "Nivel invalido.")
    require(type(rules["count"]) is int and 1 <= rules["count"] <= 6, "Quantidade invalida.")
    require(type(rules["legendaries"]) is bool, "Regra de lendarios invalida.")
    require(rules["format"] in ("single", "double"), "Formato invalido.")
    require(rules["format"] != "double" or rules["count"] >= 2, "Duplas precisam de pelo menos 2 Pokemon.")
    return dict(rules)


class Store(GiftService, EconomyService, UpdateService, ModerationService, TesterService):
    validate_match_rules = staticmethod(validate_rules)
    def __init__(self, path, areas=None):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS rooms(code TEXT PRIMARY KEY, data TEXT NOT NULL)")
        # Existing room/trade receipts remain unchanged. Accounts are additive.
        self.db.execute("""CREATE TABLE IF NOT EXISTS accounts(
            id TEXT PRIMARY KEY, secret_hash TEXT NOT NULL, nickname TEXT NOT NULL,
            normalized TEXT NOT NULL UNIQUE, created INTEGER NOT NULL, updated INTEGER NOT NULL)""")
        self.db.execute("CREATE TABLE IF NOT EXISTS friendships(a TEXT NOT NULL,b TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(a,b))")
        self.db.execute("CREATE TABLE IF NOT EXISTS friend_requests(sender TEXT NOT NULL,receiver TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(sender,receiver))")
        self.db.execute("""CREATE TABLE IF NOT EXISTS social_invites(
            id TEXT PRIMARY KEY,sender TEXT NOT NULL,receiver TEXT NOT NULL,code TEXT NOT NULL,
            mode TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL,state TEXT NOT NULL)""")
        self.db.execute("CREATE INDEX IF NOT EXISTS invites_receiver ON social_invites(receiver,state,expires)")
        self.db.execute("CREATE INDEX IF NOT EXISTS invites_expiry ON social_invites(state,expires)")
        self.db.execute("CREATE INDEX IF NOT EXISTS invites_sender ON social_invites(sender,created)")
        self.db.execute("CREATE INDEX IF NOT EXISTS requests_receiver ON friend_requests(receiver,created)")
        self.db.execute("CREATE INDEX IF NOT EXISTS friendships_b ON friendships(b)")
        self.setup_gifts()
        self.setup_economy()
        self.setup_updates()
        self.setup_tester_access()
        self.setup_moderation()
        self.db.commit()
        self.areas = areas if areas is not None else json.loads(os.environ.get("NORDELUNA_ONLINE_AREAS", json.dumps(DEFAULT_AREAS)))
        require(isinstance(self.areas, dict) and set(self.areas) == {"plaza", "coliseum", "market"}, "Configure somente plaza, coliseum e market.")
        values = [value for value in self.areas.values() if value is not None]
        require(all(type(value) is int and 0 < value <= 999999 for value in values) and len(set(values)) == len(values), "IDs de areas online invalidos ou repetidos.")
        # Ephemeral map presence must not touch trade receipts or survive restarts.
        self.presence = {}
        self.resumable = {}
        self.chat_rooms = {}
        self.chat_epoch = secrets.token_hex(8)
        self.chat_sequence = 0
        self.social_presence = {}
        self.social_rates = {}

    def friends_of(self, identity):
        return [row[0] for row in self.db.execute("SELECT CASE WHEN a=? THEN b ELSE a END FROM friendships WHERE a=? OR b=?", (identity, identity, identity))]

    def is_friend(self, a, b):
        a, b = sorted((a, b))
        return self.db.execute("SELECT 1 FROM friendships WHERE a=? AND b=?", (a, b)).fetchone() is not None

    def social_touch(self, identity, payload):
        require(isinstance(payload, dict) and payload.get("status") in ("available", "busy") and
                type(payload.get("busy")) is bool and isinstance(payload.get("build"), str) and
                1 <= len(payload["build"]) <= 100, "Presenca social invalida.")
        now = time.monotonic()
        # Dead presences are not persistent account state.
        self.social_presence = {key: row for key, row in self.social_presence.items() if now - row["seen"] < 45}
        activity = payload.get("activity", "busy" if payload["busy"] else "available")
        require(activity in ("available", "busy", "battle", "trade"), "Atividade social invalida.")
        self.social_presence[identity] = dict(status=payload["status"], busy=payload["busy"], activity=activity, build=payload["build"], seen=now)

    def map_status(self, identity):
        row = self.social_presence.get(identity, {})
        if time.monotonic() - row.get("seen", -100) >= 35:
            return "available"  # A live map peer may be using an older client.
        if row.get("busy") and row.get("activity") in ("battle", "trade"):
            return row["activity"]
        return "busy" if row.get("busy") or row.get("status") == "busy" else "available"

    def nearby_accounts(self, a, b):
        now = time.monotonic()
        people = {row.get("account_id"): row for row in self.presence.values() if now - row["seen"] < 15 and row.get("map") in self.areas.values()}
        first, second = people.get(a), people.get(b)
        return bool(first and second and first.get("map") is not None and first["map"] == second["map"] and
                    first["room"] == second["room"] and first["build"] == second["build"] and
                    abs(first.get("x", -9999) - second.get("x", 9999)) + abs(first.get("y", -9999) - second.get("y", 9999)) <= 8)

    def social_state(self, identity):
        if self.moderation_status(identity)['banned'] or identity in self._nickname_resets:return 'offline'
        row = self.social_presence.get(identity)
        if not row or time.monotonic() - row["seen"] >= 35:
            return "offline"
        return "busy" if row["busy"] or row["status"] == "busy" else "available"

    def social_room_activity(self, player, busy=True):
        identity = player.get("profile", {}).get("account_id")
        row = self.social_presence.get(identity)
        if row:
            row.update(busy=busy, seen=time.monotonic())

    def close_invite(self, invitation, state):
        invite_id, sender, receiver, code, mode, created, expires, previous = invitation
        if previous not in ("pending", "accepted"):
            return
        self.db.execute("UPDATE social_invites SET state=? WHERE id=?", (state, invite_id))
        try:
            room = self.load(code)
        except ProtocolError:
            return
        # Never touch active matches or completed trade receipts.
        if room["status"] == "waiting" and room.get("invite_id") == invite_id:
            room.update(status="cancelled", exchanges={})
            self.save(room)

    def prune_invites(self):
        now = int(time.time())
        if now < getattr(self, "next_invite_prune", 0):
            return
        self.next_invite_prune = now + 1
        for row in self.db.execute("SELECT * FROM social_invites WHERE expires<=? AND state IN ('pending','accepted')", (now,)).fetchall():
            self.close_invite(row, "expired")
        if now >= getattr(self, "next_invite_cleanup", 0):
            self.db.execute("DELETE FROM social_invites WHERE state NOT IN ('pending','accepted') AND created<?", (now - 86400,))
            self.next_invite_cleanup = now + 3600

    def social_view(self, identity, full=False):
        self.prune_invites()
        incoming = self.db.execute("SELECT r.sender,a.nickname FROM friend_requests r JOIN accounts a ON a.id=r.sender WHERE receiver=? ORDER BY r.created LIMIT 50", (identity,)).fetchall()
        invitations = self.db.execute("""SELECT i.id,i.sender,a.nickname,i.mode,i.code,i.expires,i.state
            FROM social_invites i JOIN accounts a ON a.id=i.sender WHERE receiver=? AND state IN ('pending','accepted') ORDER BY i.created LIMIT 10""", (identity,)).fetchall()
        result = dict(request_count=len(incoming), invite_count=len(invitations), status=self.social_state(identity), revision=REVISION)
        if full:
            outgoing = self.db.execute("SELECT r.receiver,a.nickname FROM friend_requests r JOIN accounts a ON a.id=r.receiver WHERE sender=? ORDER BY r.created LIMIT 50", (identity,)).fetchall()
            friends = []
            for friend, nickname in self.db.execute("""SELECT p.id,p.nickname FROM friendships f
                    JOIN accounts p ON p.id=CASE WHEN f.a=? THEN f.b ELSE f.a END WHERE f.a=? OR f.b=?""", (identity,identity,identity)):
                presence = self.social_presence.get(friend, {})
                friends.append(dict(id=friend, nickname=nickname, status=self.social_state(friend),
                                    compatible=presence.get("build") == self.social_presence.get(identity, {}).get("build")))
            result.update(friends=sorted(friends, key=lambda row: row["nickname"].casefold()),
                          incoming=[dict(id=row[0], nickname=row[1]) for row in incoming],
                          outgoing=[dict(id=row[0], nickname=row[1]) for row in outgoing],
                          invitations=[dict(id=row[0], sender=row[1], nickname=row[2], mode=row[3], code=row[4], expires=row[5], state=row[6]) for row in invitations])
        return result

    def social_action(self, request):
        account = self.account(request)
        identity, action = account["id"], request["action"]
        self.prune_invites()
        if action == "social_sync":
            self.social_touch(identity, request.get("presence"))
            return self.social_view(identity, True)
        if action not in ("social_invite", "social_invite_reply"):
            now = time.monotonic()
            self.social_rates = {key: times for key, times in self.social_rates.items() if times and now - times[-1] < 60}
            times = [stamp for stamp in self.social_rates.get(identity, []) if now - stamp < 60]
            require(len(times) < 20, "Muitos pedidos seguidos. Aguarde um minuto.")
            self.social_rates[identity] = times + [now]
        if action in ("social_friend_reply", "social_remove", "social_request_cancel"):
            require(isinstance(request.get("target"), str) and re.fullmatch(r"[0-9a-f]{32}", request["target"]), "Amigo invalido.")
        if action == "social_add":
            _, name = self.nickname(request.get("nickname"))
            row = self.db.execute("SELECT id FROM accounts WHERE normalized=?", (name,)).fetchone()
            require(row is not None, "Treinador nao encontrado. Confira o nick.")
            target = row[0]
            require(target != identity, "Voce nao pode adicionar a propria conta.")
            require(len(self.friends_of(identity)) < 100 and len(self.friends_of(target)) < 100, "Limite de amigos atingido.")
            if not self.is_friend(identity, target):
                require(self.db.execute("SELECT COUNT(*) FROM friend_requests WHERE sender=?", (identity,)).fetchone()[0] < 30,
                        "Voce ja tem 30 pedidos enviados. Cancele alguns antes de enviar mais.")
                require(self.db.execute("SELECT COUNT(*) FROM friend_requests WHERE receiver=?", (target,)).fetchone()[0] < 50,
                        "Este treinador tem muitos pedidos pendentes.")
                if not self.db.execute("SELECT 1 FROM friend_requests WHERE sender=? AND receiver=?", (target, identity)).fetchone():
                    self.db.execute("INSERT OR IGNORE INTO friend_requests VALUES(?,?,?)", (identity, target, int(time.time())))
        elif action == "social_friend_reply":
            target = request.get("target")
            require(type(request.get("accept")) is bool, "Resposta de amizade invalida.")
            pending = self.db.execute("SELECT 1 FROM friend_requests WHERE sender=? AND receiver=?", (target, identity)).fetchone()
            if not pending and request["accept"] and self.is_friend(identity, target):
                return self.social_view(identity, True)
            require(pending, "Pedido nao encontrado.")
            if request["accept"]:
                require(len(self.friends_of(identity)) < 100 and len(self.friends_of(target)) < 100, "Limite de amigos atingido.")
                a, b = sorted((identity, target))
                self.db.execute("INSERT OR IGNORE INTO friendships VALUES(?,?,?)", (a, b, int(time.time())))
            self.db.execute("DELETE FROM friend_requests WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)", (identity, target, target, identity))
        elif action in ("social_remove", "social_request_cancel"):
            target = request.get("target")
            require(isinstance(target, str) and re.fullmatch(r"[0-9a-f]{32}", target), "Amigo invalido.")
            if action == "social_remove":
                a, b = sorted((identity, target))
                self.db.execute("DELETE FROM friendships WHERE a=? AND b=?", (a, b))
                for row in self.db.execute("SELECT * FROM social_invites WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)", (identity, target, target, identity)).fetchall():
                    self.close_invite(row, "cancelled")
            self.db.execute("DELETE FROM friend_requests WHERE sender=? AND receiver=?", (identity, target))
        elif action == "social_invite":
            target, code = request.get("target"), request.get("code")
            require(isinstance(target, str) and re.fullmatch(r"[0-9a-f]{32}", target), "Treinador invalido.")
            friend = self.is_friend(identity, target)
            require(friend or self.nearby_accounts(identity, target), "Adicione este treinador ou aproxime-se dele na mesma area e sala.")
            require(isinstance(code, str) and re.fullmatch(r"[A-Z2-9]{8}", code), "Codigo invalido.")
            room = self.load(code)
            owner = room["players"][0]
            require(owner["profile"].get("account_id") == identity and isinstance(request.get("room_token"), str) and
                    hmac.compare_digest(owner["token"], request["room_token"]), "Somente o anfitriao pode convidar para esta sala.")
            require(room["status"] == "waiting" and len(room["players"]) == 1 and request.get("mode") == room["mode"], "Sala indisponivel para convite.")
            previous = self.db.execute("SELECT id FROM social_invites WHERE code=? AND sender=? AND receiver=? AND state IN ('pending','accepted')", (code, identity, target)).fetchone()
            if previous:
                return {"invitation": previous[0]}
            require(self.social_state(target) == "available", "Este amigo esta offline ou ocupado.")
            require(self.social_presence.get(target, {}).get("build") == room["build"], "As versoes do jogo sao diferentes.")
            require(not self.db.execute("SELECT 1 FROM social_invites WHERE receiver=? AND state IN ('pending','accepted')", (target,)).fetchone(), "Este amigo ja esta respondendo a outro convite.")
            require(self.db.execute("SELECT COUNT(*) FROM social_invites WHERE sender=? AND created>?", (identity, int(time.time())-60)).fetchone()[0] < 3,
                    "Espere um minuto antes de enviar mais convites.")
            require(not room.get("invite_id"), "Esta sala ja recebeu um convite.")
            invitation = secrets.token_hex(16);now = int(time.time())
            self.db.execute("INSERT INTO social_invites VALUES(?,?,?,?,?,?,?,?)", (invitation, identity, target, code, room["mode"], now, now+120, "pending"))
            room.update(invite_to=target, invite_id=invitation, invite_scope="friend" if friend else "nearby")
            self.save(room)
            return {"invitation": invitation}
        elif action == "social_invite_reply":
            invitation = request.get("invitation")
            require(isinstance(invitation, str) and re.fullmatch(r"[0-9a-f]{32}", invitation), "Convite invalido.")
            row = self.db.execute("SELECT * FROM social_invites WHERE id=? AND receiver=?", (invitation, identity)).fetchone()
            require(row is not None and row[7] in ("pending", "accepted") and row[6]>time.time(), "Convite expirado ou encerrado.")
            require(type(request.get("accept")) is bool, "Resposta de convite invalida.")
            if not request["accept"]:
                self.close_invite(row, "declined")
                return {"state": "declined"}
            room = self.load(row[3])
            require((self.is_friend(identity, row[1]) or room.get("invite_scope") == "nearby") and room["status"] == "waiting" and len(room["players"]) == 1, "Sala encerrada ou amizade removida.")
            # Acknowledging a request does not join, select a team or commit a trade.
            self.db.execute("UPDATE social_invites SET state='accepted' WHERE id=?", (invitation,))
            return dict(state="accepted", code=row[3], mode=row[4], build=room["build"], expires=row[6])
        else:
            raise ProtocolError("Acao social desconhecida.")
        return self.social_view(identity, True)

    @staticmethod
    def nickname(value):
        require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_]{3,16}", value), "Nick: use 3 a 16 letras A-Z, numeros ou underscore.")
        normalized = value.casefold()
        require(normalized not in {"admin", "administrador", "moderador", "gm", "system", "sistema", "server", "servidor", "suporte", "npc", "null", "nil"}, "Este nickname esta reservado.")
        return value, normalized

    @staticmethod
    def credentials(request):
        account = request.get("account")
        require(isinstance(account, dict) and isinstance(account.get("id"), str) and re.fullmatch(r"[0-9a-f]{32}", account["id"]) and
                isinstance(account.get("secret"), str) and re.fullmatch(r"[0-9a-f]{64}", account["secret"]), "Identidade online ausente. Atualize o cliente e configure seu nick.")
        return account["id"], hashlib.sha256(account["secret"].encode("ascii")).hexdigest()

    def account(self, request):
        identity, digest = self.credentials(request)
        row = self.db.execute("SELECT id,secret_hash,nickname FROM accounts WHERE id=?", (identity,)).fetchone()
        require(row is not None and hmac.compare_digest(row[1], digest), "Identidade online invalida. Use o save original desta conta.")
        reset=self.db.execute('SELECT previous_nickname FROM account_nickname_resets WHERE account=?',(identity,)).fetchone()
        # Keep old clients able to open "Meu nick" and finish existing receipts.
        # The previous name is display-only until a different name is registered.
        if reset:
            require(request.get('action') in ('account_info','account_check','gift_begin','gift_ack','gift_status','gift_history','economy_order','economy_ledger'),
                    'Seu nick foi removido pelo administrador. Abra Online > Meu nick e escolha outro nome. Sua conta, moedas e compras foram preservadas.')
        if request.get('action') not in ('account_info','account_check','gift_begin','gift_ack','gift_status','gift_history','economy_order','economy_ledger'):
            self.moderation_require_online(row[0])
        result={"id": row[0], "nickname": reset[0] if reset else row[2]}
        if reset:result['nickname_required']=True
        return result

    def account_action(self, request):
        action = request["action"]
        if action == "account_check":
            _, normalized = self.nickname(request.get("nickname"))
            owner = self.db.execute("SELECT id FROM accounts WHERE normalized=?", (normalized,)).fetchone()
            own = self.account(request)["id"] if request.get("account") else None
            return {"available": owner is None or owner[0] == own}
        if action == "account_info":
            return self.account(request)
        require(action == "account_register", "Acao de identidade invalida.")
        identity, digest = self.credentials(request)
        nickname, normalized = self.nickname(request.get("nickname"))
        existing = self.db.execute("SELECT secret_hash FROM accounts WHERE id=?", (identity,)).fetchone()
        if existing:
            require(hmac.compare_digest(existing[0], digest), "Esta identidade pertence a outra conta.")
            reset=self.db.execute('SELECT previous_nickname FROM account_nickname_resets WHERE account=?',(identity,)).fetchone()
            require(not reset or normalized!=reset[0].casefold(),'Seu nick anterior foi removido pelo administrador. Escolha um nome diferente.')
        now = int(time.time())
        try:
            if existing:
                self.db.execute("UPDATE accounts SET nickname=?,normalized=?,updated=? WHERE id=?", (nickname, normalized, now, identity))
                self.db.execute('DELETE FROM account_nickname_resets WHERE account=?',(identity,))
                if reset:self.moderation_bump()
            else:
                self.db.execute("INSERT INTO accounts VALUES(?,?,?,?,?,?)", (identity, digest, nickname, normalized, now, now))
        except sqlite3.IntegrityError:
            raise ProtocolError("Este nickname ja esta sendo utilizado. Escolha outro.") from None
        for row in self.presence.values():
            if row.get("account_id") == identity:
                row["name"] = nickname
        return {"id": identity, "nickname": nickname}

    def area_action(self, request):
        require(type(self.areas["plaza"]) is int, "A Praca Central ainda nao foi configurada no servidor.")
        action = request["action"]
        if action == "map_join":
            account = self.account(request)
            self.moderation_require_map(account['id'],self.map_room(request.get('room','PRACA')))
            data = dict(request, profile={"name": account["nickname"]})
            require(request.get("resume") is None or isinstance(request["resume"], str), "Sessao de reconexao invalida.")
            previous = self.resumable.get(request.get("resume"))
            require(not previous or previous.get("account_id") == account["id"], "Esta sessao pertence a outra conta.")
            target = request.get("area_map", self.areas["plaza"])
            require(type(target) is int and target in self.areas.values(), "Este mapa nao e uma area online.")
            reply = self.map_action(data)
            row = self.presence[reply["token"]]
            row["account_id"] = account["id"]
            row["authorized_map"] = target
            row.setdefault("movement_seq", -1)
            for old_token, old in list(self.presence.items()):
                if old_token != reply["token"] and old.get("account_id") == account["id"]:
                    self.presence.pop(old_token, None)
                    self.resumable.pop(old_token, None)
            reply.update(account_id=account["id"], nickname=account["nickname"], areas=self.areas)
            return reply
        token = request.get("token")
        require(isinstance(token, str), "Sessao de mapa invalida.")
        # Drop expired presences before authorizing a transition or a state packet.
        now = time.monotonic()
        self.presence = {key: row for key, row in self.presence.items() if now - row["seen"] < 15}
        row = self.presence.get(token)
        require(row is not None and row.get("account_id"), "Canal de mapa expirou. Entre novamente.")
        if action!='map_leave':self.moderation_require_map(row['account_id'],row['room'])
        if action == "map_ping":
            row["seen"] = now
            result = {"peers": [], "cooldown": 3}
            result.update(self.chat_view(row, request))
            return result
        if action == "map_enter":
            target = request.get("map")
            require(type(target) is int and target in self.areas.values(), "Este mapa nao e uma area online.")
            row.update(authorized_map=target, map=None, seen=now)
            return {"map": target, "room": row["room"], "revision": REVISION}
        if action == "map_leave":
            return self.map_action(request,presence_pruned=True)
        require(action == "map_update", "Acao de mapa invalida.")
        state = request.get("state")
        require(isinstance(state, dict) and set(state) == {"map", "x", "y", "seq", "direction", "frame", "moving", "character"}, "Posicao invalida.")
        require(type(state.get("map")) is int and state["map"] == row["authorized_map"] and state["map"] in self.areas.values(), "Transicao de area nao autorizada.")
        sequence = state.get("seq")
        require(type(sequence) is int and 0 <= sequence < 2**53 and sequence > row["movement_seq"], "Pacote de movimento antigo ou fora de ordem.")
        require(state.get("direction") in (2, 4, 6, 8) and type(state.get("direction")) is int, "Direcao invalida.")
        require(type(state.get("frame")) is int and 0 <= state["frame"] <= 3 and type(state.get("moving")) is bool, "Animacao invalida.")
        character = state.get("character")
        require(isinstance(character, str) and 1 <= len(character) <= 128 and not re.search(r"[\\<>\x00-\x1f]", character) and
                not character.startswith("/") and ".." not in character.split("/"), "Aparencia invalida.")
        known = request.get("known_peers", {})
        require(isinstance(known, dict) and len(known) <= 40 and all(isinstance(k, str) and isinstance(v, str) and len(v) <= 64 for k, v in known.items()), "Cache de aparencias invalido.")
        result = self.map_action(request,presence_pruned=True)
        row["movement_seq"] = sequence
        by_id = {p["id"]: p for p in self.presence.values()}
        for peer in result["peers"]:
            remote = by_id[peer["id"]]
            peer.update(account_id=remote["account_id"], direction=remote.get("direction", 2),
                        character=remote.get("character", ""), frame=remote.get("frame", 0),
                        moving=remote.get("moving", False), seq=remote["movement_seq"], map=remote["map"],
                        status=self.map_status(remote["account_id"]),badge=self.badge_view(remote["account_id"])['equipped_badge'])
            profile_key=(remote['name'],remote.get('character',''))
            if remote.get('_profile_key')!=profile_key:
                remote['_profile_key']=profile_key
                remote['_profile_revision']=hashlib.sha256((profile_key[0]+'\0'+profile_key[1]).encode()).hexdigest()[:16]
            fingerprint = remote['_profile_revision']
            peer["profile_revision"] = fingerprint
            if known.get(peer["id"]) == fingerprint:
                for field in ("name", "character", "account_id"):
                    peer.pop(field, None)
        result["request_sequence"] = sequence
        result["map"] = state["map"]
        return result

    @staticmethod
    def map_room(value):
        require(isinstance(value, str), "Sala de mapa invalida.")
        value = value.strip().upper()
        require(value == "PRACA" or re.fullmatch(r"[A-Z2-9]{8}", value), "Use PRACA ou um codigo de 8 caracteres.")
        return value

    def chat_view(self, row, request, members=None):
        self.moderation_refresh()
        now = time.monotonic()
        self.chat_rooms = {key: room for key, room in self.chat_rooms.items() if now - room["seen"] < 1800}
        key = (row["build"], row["room"])
        if key not in self.chat_rooms:
            require(len(self.chat_rooms) < 200, "Limite de salas de chat atingido. Tente mais tarde.")
            self.chat_rooms[key] = {"messages": deque(self.persistent_chat_rows(*key),maxlen=80), "seen": now}
        room = self.chat_rooms[key]
        room["seen"] = now
        after = request.get("after", 0)
        require(type(after) is int and 0 <= after < 2**63, "Cursor de chat invalido.")
        outgoing = request.get("chat")
        acknowledgement = None
        if outgoing is not None:
            require(isinstance(outgoing, dict), "Mensagem invalida.")
            client_id, text = outgoing.get("client_id"), outgoing.get("text")
            require(isinstance(client_id, str) and re.fullmatch(r"[a-f0-9]{32}", client_id), "ID de mensagem invalido.")
            require(isinstance(text, str) and 1 <= len(text.strip()) <= 120 and not re.search(r"[<>\x00-\x1f\x7f]", text), "Mensagem: use 1 a 120 caracteres sem tags ou quebras de linha.")
            text = text.strip()
            previous = next((m for m in room["messages"] if m["client_id"] == client_id), None)
            if previous:
                require(previous["text"] == text and self.db.execute('SELECT 1 FROM chat_history WHERE id=? AND account=?',(previous['id'],row['account_id'])).fetchone(), "ID de mensagem ja utilizado.")
                acknowledgement = client_id
            else:
                try:message=self.persist_chat(row,client_id,text)
                except ModerationError:raise
                except ValueError as error:raise ProtocolError(str(error)) from None
                if message:
                    row["last_chat"] = now
                    self.chat_sequence=message['id']
                    room["messages"].append(message)
                acknowledgement = client_id
        epoch=self.chat_epoch+':'+str(self._chat_revision)
        reset = request.get("chat_epoch") != epoch
        messages = [m for m in room["messages"] if reset or m["id"] > after]
        return {"messages": messages[-80:], "chat_epoch": epoch, "chat_ack": acknowledgement,
                "chat_muted_until":self.moderation_status(row['account_id'])['muted_until'],
                "room": row["room"], "revision": REVISION, "version": VERSION,
                "members": members if members is not None else sum(p["room"] == row["room"] and p["build"] == row["build"] and self.moderation_peer_allowed(p) for p in self.presence.values())}

    def map_action(self, request, presence_pruned=False):
        now = time.monotonic()
        if not presence_pruned:self.presence = {key: row for key, row in self.presence.items() if now - row["seen"] < 15}
        self.resumable = {key: row for key, row in self.resumable.items() if now - row["seen"] < 120}
        action = request["action"]
        if action == "map_join":
            profile = request.get("profile")
            require(isinstance(profile, dict), "Perfil invalido.")
            name = profile.get("name")
            require(isinstance(name, str) and 1 <= len(name.strip()) <= 24 and not re.search(r"[\\<>\x00-\x1f]", name), "Nick invalido.")
            build = request.get("build")
            require(isinstance(build, str) and 1 <= len(build) <= 100, "Build invalida.")
            room = self.map_room(request.get("room", "PRACA"))
            resume = request.get("resume")
            previous = self.resumable.get(resume) if isinstance(resume, str) else None
            if previous and previous["build"] == build and previous["room"] == room:
                previous.update(seen=now, name=name.strip())
                self.presence[resume] = previous
                return {"token": resume, "id": previous["id"], "room": room, "resumed": True,
                        "cooldown": 3, "revision": REVISION, "version": VERSION}
            require(len(self.presence) < 500, "Canal de mapa cheio.")
            token = secrets.token_urlsafe(32)
            self.presence[token] = {"id": secrets.token_hex(8), "name": name.strip(), "build": build,
                                    "seen": now, "map": None, "room": room, "emote": None, "last_emote": -10.0, "sequence": 0}
            self.resumable[token] = self.presence[token]
            return {"token": token, "id": self.presence[token]["id"], "room": room, "resumed": False,
                    "cooldown": 3, "revision": REVISION, "version": VERSION}
        token = request.get("token")
        require(isinstance(token, str) and token in self.presence, "Canal de mapa expirou. Entre novamente.")
        if action == "map_leave":
            del self.presence[token]
            self.resumable.pop(token, None)
            return {}
        require(action == "map_update", "Acao de mapa invalida.")
        row = self.presence[token]
        state = request.get("state")
        require(isinstance(state, dict), "Mapa invalido.")
        for key, maximum in (("map", 999999), ("x", 9999), ("y", 9999)):
            require(type(state.get(key)) is int and 0 <= state[key] <= maximum, "Posicao invalida.")
        emote = request.get("emote")
        if emote is not None:
            require(emote in ("wave", "celebrate", "battle"), "Emote invalido.")
            require(now - row["last_emote"] >= 3, "Espere 3 segundos entre emotes.")
            row["last_emote"] = now
            row["sequence"] += 1
            row["emote"] = emote
        elif row["map"] != state["map"]:
            row["emote"] = None
        row.update(state, seen=now)
        # Filter the room once for both visibility and chat counts. Build wire
        # records only for the nearest 40, rather than every player in the room.
        room_members=[peer for peer in self.presence.values() if peer['build']==row['build'] and peer['room']==row['room'] and self.moderation_peer_allowed(peer)]
        nearest=heapq.nsmallest(40,(peer for peer in room_members if peer['id']!=row['id'] and peer['map']==row['map']),
            key=lambda peer:abs(peer['x']-row['x'])+abs(peer['y']-row['y']))
        peers = [{"id": peer["id"], "name": peer["name"], "x": peer["x"], "y": peer["y"],
                  "emote": peer["emote"] if now - peer["last_emote"] < 4 else None,
                  "sequence": peer["sequence"]}
                 for peer in nearest]
        # Legacy map clients remain compatible and do not receive chat payloads.
        result = {"peers": peers, "cooldown": 3}
        if request.get("chat_enabled") is True:
            result.update(self.chat_view(row, request, members=len(room_members)))
        return result

    def save(self, room):
        self.db.execute("INSERT OR REPLACE INTO rooms VALUES(?,?)",
                        (room["code"], json.dumps(room, ensure_ascii=False, separators=(",", ":"))))

    def load(self, code):
        row = self.db.execute("SELECT data FROM rooms WHERE code=?", (code,)).fetchone()
        require(row is not None, "Sala nao encontrada.")
        return json.loads(row[0])

    def player(self, request):
        account = self.account(request)
        profile, payload = request.get("profile"), request.get("payload")
        require(isinstance(profile, dict) and isinstance(profile.get("name"), str), "Treinador invalido.")
        require(1 <= len(profile["name"]) <= 24 and not re.search(r"[\\<>\x00-\x1f]", profile["name"]), "Nome invalido.")
        require(isinstance(profile.get("type"), str) and len(profile["type"]) <= 64, "Tipo invalido.")
        require(type(profile.get("id")) is int and 0 <= profile["id"] < 2**32, "ID invalido.")
        require(isinstance(payload, list) and 1 <= len(payload) <= 6 and all(isinstance(x, dict) for x in payload), "Equipe invalida.")
        profile = dict(profile, name=account["nickname"], account_id=account["id"])
        return {"profile": profile, "payload": payload, "token": secrets.token_urlsafe(32), "confirmed": False}

    def view(self, room, side):
        return {"code": room["code"], "side": side, "mode": room["mode"], "status": room["status"],
                "rules": room.get("rules", "free"),
                "seed": room["seed"], "players": [{"profile": p["profile"], "payload": p["payload"],
                "confirmed": p["confirmed"]} for p in room["players"]]}

    def handle(self, request):
        require(isinstance(request, dict), "Pedido invalido.")
        require(request.get("protocol") == PROTOCOL, "Protocolo incompativel. Atualize o jogo.")
        action = request.get("action")
        if action == "health":
            return {"protocol": PROTOCOL, "revision": REVISION, "version": VERSION, "service": "Nordeluna Online", "areas": self.areas,
                    "features": FEATURES}
        with self.lock, self.db:
            if action in ('tester_redeem','tester_access'):
                return self.tester_action(request)
            self.tester_require_request(request)
            if action in ('update_manifest','update_chunk'):
                return self.update_action(request)
            if isinstance(action, str) and action.startswith('economy_'):
                return self.economy_action(request)
            if isinstance(action, str) and action.startswith('match_'):
                return self.match_action(request)
            if isinstance(action, str) and action.startswith("gift_"):
                return self.gift_action(request)
            if isinstance(action, str) and action.startswith("account_"):
                return self.account_action(request)
            if isinstance(action, str) and action.startswith("social_"):
                return self.social_action(request)
            if isinstance(action, str) and action.startswith("map_"):
                result = self.area_action(request)
                row = self.presence.get(request.get("token") or result.get("token"))
                if row and row.get('account_id'):
                    result['badge']=self.badge_view(row['account_id'])['equipped_badge']
                if row and time.monotonic()>=row.get('notice_at',0):
                    result['notices']=self.notice_view()
                    row['notice_at']=time.monotonic()+15
                if row and row.get("account_id") and request.get("social") is not None:
                    require(isinstance(request["social"], dict), "Presenca social invalida.")
                    require(request["social"].get("build") == row["build"], "Build social incompativel.")
                    self.social_touch(row["account_id"], request["social"])
                    if time.monotonic() >= row.get("social_at", 0):
                        result["social"] = self.social_view(row["account_id"])
                        row["social_at"] = time.monotonic() + 10
                return result
            self.prune_invites()
            if action == "create":
                require(request.get("mode") in ("battle", "trade"), "Modo invalido.")
                require(isinstance(request.get("build"), str) and 1 <= len(request["build"]) <= 100, "Build invalida.")
                rules = validate_rules(request.get("rules", "free"))
                # Only waiting rooms expire. Never delete a committed trade receipt.
                now = time.time()
                for code, data in self.db.execute("SELECT code,data FROM rooms").fetchall():
                    old = json.loads(data)
                    if old["status"] not in ("committed", "cancelled") and now - old["updated"] > 86400:
                        old["status"] = "cancelled"
                        old["exchanges"] = {}
                        self.save(old)
                count = self.db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
                require(count < 100000, "Servidor cheio. Contate o administrador.")
                code = "".join(secrets.choice(ALPHABET) for _ in range(8))
                while self.db.execute("SELECT 1 FROM rooms WHERE code=?", (code,)).fetchone():
                    code = "".join(secrets.choice(ALPHABET) for _ in range(8))
                p = self.player(request)
                require(request["mode"] != "trade" or len(p["payload"]) == 1, "Oferta invalida.")
                require(request["mode"] != "battle" or not isinstance(rules, dict) or len(p["payload"]) == rules["count"], "Equipe diferente das regras da sala.")
                room = {"code": code, "mode": request["mode"], "build": request["build"], "rules": rules, "status": "waiting",
                        "seed": secrets.randbelow(2**30), "players": [p], "exchanges": {}, "updated": now}
                self.save(room)
                self.social_room_activity(p)
                return dict(self.view(room, 0), token=p["token"])
            code = request.get("code")
            require(isinstance(code, str) and re.fullmatch(r"[A-Z2-9]{8}", code), "Codigo invalido.")
            room = self.load(code)
            if action == "inspect":
                require(room["status"] == "waiting", "Sala cheia ou encerrada.")
                return {"mode": room["mode"], "rules": room.get("rules", "free"), "build": room["build"]}
            if action == "join":
                require(request.get("build") == room["build"], "As versoes do jogo sao diferentes.")
                require(request.get("mode") == room["mode"], "Essa sala e de outro modo.")
                require(room["status"] == "waiting" and len(room["players"]) == 1, "Sala cheia ou encerrada.")
                p = self.player(request)
                if room.get("invite_to"):
                    require(p["profile"].get("account_id") == room["invite_to"], "Esta sala esta reservada para o amigo convidado.")
                    invitation = self.db.execute("SELECT state,expires FROM social_invites WHERE id=?", (room.get("invite_id"),)).fetchone()
                    require(invitation and invitation[0] == "accepted" and invitation[1]>time.time(), "Aceite um convite valido antes de entrar nesta sala.")
                require(room["mode"] != "trade" or len(p["payload"]) == 1, "Oferta invalida.")
                require(room["mode"] != "battle" or not isinstance(room.get("rules"), dict) or len(p["payload"]) == room["rules"]["count"], "Equipe diferente das regras da sala.")
                room["players"].append(p)
                room["status"] = "active"
                room["updated"] = time.time()
                self.save(room)
                if room.get("invite_id"):
                    self.db.execute("UPDATE social_invites SET state='joined' WHERE id=?", (room["invite_id"],))
                self.social_room_activity(p)
                return dict(self.view(room, 1), token=p["token"])
            token = request.get("token")
            require(isinstance(token, str), "Sessao invalida.")
            side = next((i for i, p in enumerate(room["players"]) if secrets.compare_digest(p["token"], token)), None)
            require(side is not None, "Sessao invalida.")
            if action!='cancel' and not (action=='poll' and room['status']=='committed'):
                self.moderation_require_online(room['players'][side]['profile'].get('account_id',''))
            if room['status'] not in ('committed','cancelled') and any(self.moderation_status(p['profile'].get('account_id',''))['banned'] for p in room['players']):
                room['status']='cancelled';room['exchanges']={};self.save(room)
            self.social_room_activity(room["players"][side], action != "cancel" and room["status"] not in ("committed", "cancelled"))
            if action == 'battle_result':
                return self.battle_result(room,side,request.get('result'))
            if action == "cancel":
                if room["status"] != "committed":
                    room["status"] = "cancelled"
                    room["exchanges"] = {}
                    self.db.execute("UPDATE social_invites SET state='cancelled' WHERE code=? AND state IN ('pending','accepted')", (code,))
            elif action == "confirm":
                require(room["mode"] == "trade" and room["status"] in ("active", "committed"), "Troca indisponivel.")
                room["players"][side]["confirmed"] = True
                if all(p["confirmed"] for p in room["players"]):
                    room["status"] = "committed"
                    self.activity('trade',room)
            elif action == "exchange":
                require(room["mode"] == "battle" and room["status"] == "active", "Batalha encerrada.")
                key = request.get("key")
                require(isinstance(key, str) and re.fullmatch(r"[a-z]+:[0-9]{1,5}", key), "Etapa invalida.")
                require(key in room["exchanges"] or len(room["exchanges"]) < 4000, "Limite de turnos excedido.")
                values = room["exchanges"].setdefault(key, {})
                s = str(side)
                changed = s not in values and "value" in request
                if "value" in request:
                    value = request["value"]
                    require(len(json.dumps(value)) <= 8192, "Comando grande demais.")
                    require(s not in values or values[s] == value, "Comando ja confirmado.")
                    values[s] = value
                if changed and not room.get('economy_verified_turns') and sum(k.startswith('turn:') and len(v)==2 for k,v in room['exchanges'].items())>=2:
                    room['economy_verified_turns']=True
                if changed or time.time()-room["updated"]>=30:
                    room["updated"] = time.time()
                    self.save(room)
                # Sealed choices: no revealing the other choice until both submit.
                return {"ready": len(values) == 2, "values": [values["0"], values["1"]] if len(values) == 2 else None}
            else:
                require(action == "poll", "Acao desconhecida.")
                if room["status"] in ("committed", "cancelled") or time.time()-room["updated"]<30:
                    return self.view(room, side)
            room["updated"] = time.time()
            self.save(room)
            return self.view(room, side)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def setup(self):
        super().setup()
        self.connection.settimeout(KEEPALIVE_IDLE_SECONDS)
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.persistent_slot = False
        self.served_count = 0

    def finish(self):
        try:
            super().finish()
        finally:
            if self.persistent_slot:
                self.server.keepalive_slots.release()
                self.persistent_slot = False

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError):
            self.close_connection=True

    def do_GET(self):
        self.processing_started=time.perf_counter()
        if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length','0')!='0':
            self.close_connection=True
            return self.reply(400,dict(ok=False,error='GET nao aceita corpo.'))
        if self.path.split("?", 1)[0] == "/health":
            self.reply(200, {"ok": True, "service": "Nordeluna Online", "protocol": PROTOCOL, "revision": REVISION, "version": VERSION,
                             "areas": self.server.store.areas, "features": FEATURES})
        else:
            self.reply(404, {"ok": False, "error": "Rota desconhecida."})

    def do_POST(self):
        self.processing_started=None
        if self.path not in ("/api","/moderation"):
            self.close_connection=True
            self.reply(404, {"ok": False, "error": "Rota desconhecida."})
            return
        try:
            # Persistent connections must never interpret an unread body as the
            # next request. Reject ambiguous framing and close on body errors.
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[]))!=1:
                self.close_connection=True
                return self.reply(400,dict(ok=False,error='Content-Length unico obrigatorio.'))
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.close_connection=True
                return self.reply(400,dict(ok=False,error='Pedido grande demais ou vazio.'))
            self.connection.settimeout(15)
            raw=self.rfile.read(length)
            if len(raw)!=length:
                self.close_connection=True
                return self.reply(400,dict(ok=False,error='Pedido incompleto.'))
            body = json.loads(raw)
            self.processing_started=time.perf_counter()
            if isinstance(body,dict) and body.get('action')=='tester_redeem' and not self.server.tester_limit(self.client_address[0]):
                self.reply(429,dict(ok=False,error='Muitas tentativas. Aguarde um minuto.'))
                return
            if self.path=='/moderation':
                header=self.headers.get('Authorization','')
                key=header[7:] if header.startswith('Bearer ') else ''
                response=self.server.store.moderation_staff(key,body)
            else:response = self.server.store.handle(body)
            self.reply(200, dict(response, ok=True))
        except StaffAuthError as exc:
            self.reply(401,{"ok":False,"error":str(exc)[:160]})
        except ModerationError as exc:
            self.reply(400,{"ok":False,"error":str(exc)[:240],"code":exc.code,"until":exc.until})
        except (ProtocolError, ValueError, UnicodeError, RecursionError) as exc:
            if self.processing_started is None:self.close_connection=True
            self.reply(400, {"ok": False, "error": str(exc)[:160]})
        except Exception:
            self.close_connection=True
            self.reply(500, {"ok": False, "error": "Erro interno do relay."})

    def reply(self, status, body):
        started=getattr(self,'processing_started',None)
        # Installed PC/Android clients use an integer-only JSON codec. Timing
        # metadata must remain readable even before players update the game.
        if started is not None:body=dict(body,server_ms=max(0,round((time.perf_counter()-started)*1000)))
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        compressed=False
        if len(raw)>=1024 and self.accepts_gzip():
            packed=gzip.compress(raw,compresslevel=1,mtime=0)
            if len(packed)<len(raw):raw=packed;compressed=True
        self.served_count+=1
        slots=getattr(self.server,'keepalive_slots',None)
        if not self.close_connection and not self.persistent_slot and slots:
            self.persistent_slot=slots.acquire(blocking=False)
        if not self.persistent_slot or self.served_count>=KEEPALIVE_REQUESTS:self.close_connection=True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header('Vary','Accept-Encoding')
        if compressed:self.send_header('Content-Encoding','gzip')
        self.send_header('Connection','close' if self.close_connection else 'keep-alive')
        if not self.close_connection:self.send_header('Keep-Alive','timeout='+str(KEEPALIVE_IDLE_SECONDS)+', max='+str(KEEPALIVE_REQUESTS-self.served_count))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection=True
        finally:
            self.connection.settimeout(KEEPALIVE_IDLE_SECONDS)

    def accepts_gzip(self):
        for item in self.headers.get('Accept-Encoding','').split(','):
            parts=item.strip().lower().split(';')
            if parts[0].strip()!='gzip':continue
            quality=1.0
            for parameter in parts[1:]:
                key,_,value=parameter.partition('=')
                if key.strip()=='q':
                    try:quality=float(value.strip())
                    except ValueError:return False
            return 0<quality<=1
        return False

    def log_message(self, fmt, *args):
        # No bearer tokens or Pokemon in logs.
        pass


class RelayHTTPServer(ThreadingHTTPServer):
    """Bound idle/slow clients instead of creating unlimited server threads."""
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, *args, **kwargs):
        self.workers = threading.BoundedSemaphore(HTTP_WORKERS)
        # Persistent sockets cannot consume the workers reserved for new requests.
        self.keepalive_slots = threading.BoundedSemaphore(PERSISTENT_CONNECTIONS)
        self.tester_attempts={}
        self.tester_rate_lock=threading.Lock()
        super().__init__(*args, **kwargs)

    def tester_limit(self, address):
        # Only invitation endpoints; gameplay is never rate-limited by this gate.
        now=int(time.monotonic()//60)
        with self.tester_rate_lock:
            if len(self.tester_attempts)>4096:self.tester_attempts={k:v for k,v in self.tester_attempts.items() if v[0]==now}
            old,count=self.tester_attempts.get(address,(now,0))
            count=count+1 if old==now else 1
            self.tester_attempts[address]=(now,count)
            return count<=30

    def process_request(self, request, address):
        if not self.workers.acquire(blocking=False):
            try:
                body = b'{"ok":false,"error":"Servidor ocupado. Tente novamente."}'
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.workers.release()
            raise

    def process_request_thread(self, *args):
        try:
            super().process_request_thread(*args)
        finally:
            self.workers.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default="nordeluna-online.sqlite3")
    args = parser.parse_args()
    server = RelayHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    server.store = Store(args.db)
    print(f"Nordeluna Online: http://{args.host}:{args.port} (Ctrl+C para parar)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.store.db.close()


if __name__ == "__main__":
    main()
