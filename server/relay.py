"""Nordeluna relay. Python 3.10+, standard library only. Run behind HTTPS online."""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROTOCOL = 1
REVISION = 5
VERSION = "0.6.0"
MAX_BODY = 262144
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEFAULT_AREAS = {"plaza": 39, "coliseum": None, "market": None}


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


class Store:
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
        return {"id": row[0], "nickname": row[2]}

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
        now = int(time.time())
        try:
            if existing:
                self.db.execute("UPDATE accounts SET nickname=?,normalized=?,updated=? WHERE id=?", (nickname, normalized, now, identity))
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
            return self.map_action(request)
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
        result = self.map_action(request)
        row["movement_seq"] = sequence
        by_id = {p["id"]: p for p in self.presence.values()}
        for peer in result["peers"]:
            remote = by_id[peer["id"]]
            peer.update(account_id=remote["account_id"], direction=remote.get("direction", 2),
                        character=remote.get("character", ""), frame=remote.get("frame", 0),
                        moving=remote.get("moving", False), seq=remote["movement_seq"], map=remote["map"])
            fingerprint = hashlib.sha256((remote["name"] + "\0" + remote.get("character", "")).encode()).hexdigest()[:16]
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

    def chat_view(self, row, request):
        now = time.monotonic()
        self.chat_rooms = {key: room for key, room in self.chat_rooms.items() if now - room["seen"] < 1800}
        key = (row["build"], row["room"])
        if key not in self.chat_rooms:
            require(len(self.chat_rooms) < 200, "Limite de salas de chat atingido. Tente mais tarde.")
            self.chat_rooms[key] = {"messages": deque(maxlen=80), "seen": now}
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
                require(previous["sender"] == row["id"] and previous["text"] == text, "ID de mensagem ja utilizado.")
                acknowledgement = client_id
            else:
                require(now - row.get("last_chat", -10) >= 2, "Espere 2 segundos entre mensagens.")
                row["last_chat"] = now
                self.chat_sequence += 1
                message = {"id": self.chat_sequence, "client_id": client_id, "sender": row["id"],
                           "nick": row["name"], "text": text, "timestamp": int(time.time())}
                room["messages"].append(message)
                acknowledgement = client_id
        reset = request.get("chat_epoch") != self.chat_epoch
        messages = [m for m in room["messages"] if reset or m["id"] > after]
        return {"messages": messages[-80:], "chat_epoch": self.chat_epoch, "chat_ack": acknowledgement,
                "room": row["room"], "revision": REVISION, "version": VERSION,
                "members": sum(p["room"] == row["room"] and p["build"] == row["build"] for p in self.presence.values())}

    def map_action(self, request):
        now = time.monotonic()
        self.presence = {key: row for key, row in self.presence.items() if now - row["seen"] < 15}
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
        peers = [{"id": peer["id"], "name": peer["name"], "x": peer["x"], "y": peer["y"],
                  "emote": peer["emote"] if now - peer["last_emote"] < 4 else None,
                  "sequence": peer["sequence"]}
                 for peer in self.presence.values()
                 if peer["id"] != row["id"] and peer["build"] == row["build"] and peer["room"] == row["room"] and peer["map"] == row["map"]]
        # Legacy map clients remain compatible and do not receive chat payloads.
        peers.sort(key=lambda p: abs(p["x"] - row["x"]) + abs(p["y"] - row["y"]))
        result = {"peers": peers[:40], "cooldown": 3}
        if request.get("chat_enabled") is True:
            result.update(self.chat_view(row, request))
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
            return {"protocol": PROTOCOL, "revision": REVISION, "version": VERSION, "service": "Nordeluna Online", "areas": self.areas}
        with self.lock, self.db:
            if isinstance(action, str) and action.startswith("account_"):
                return self.account_action(request)
            if isinstance(action, str) and action.startswith("map_"):
                return self.area_action(request)
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
                require(room["mode"] != "trade" or len(p["payload"]) == 1, "Oferta invalida.")
                require(room["mode"] != "battle" or not isinstance(room.get("rules"), dict) or len(p["payload"]) == room["rules"]["count"], "Equipe diferente das regras da sala.")
                room["players"].append(p)
                room["status"] = "active"
                room["updated"] = time.time()
                self.save(room)
                return dict(self.view(room, 1), token=p["token"])
            token = request.get("token")
            require(isinstance(token, str), "Sessao invalida.")
            side = next((i for i, p in enumerate(room["players"]) if secrets.compare_digest(p["token"], token)), None)
            require(side is not None, "Sessao invalida.")
            if action == "cancel":
                if room["status"] != "committed":
                    room["status"] = "cancelled"
                    room["exchanges"] = {}
            elif action == "confirm":
                require(room["mode"] == "trade" and room["status"] in ("active", "committed"), "Troca indisponivel.")
                room["players"][side]["confirmed"] = True
                if all(p["confirmed"] for p in room["players"]):
                    room["status"] = "committed"
            elif action == "exchange":
                require(room["mode"] == "battle" and room["status"] == "active", "Batalha encerrada.")
                key = request.get("key")
                require(isinstance(key, str) and re.fullmatch(r"[a-z]+:[0-9]{1,5}", key), "Etapa invalida.")
                require(key in room["exchanges"] or len(room["exchanges"]) < 4000, "Limite de turnos excedido.")
                values = room["exchanges"].setdefault(key, {})
                s = str(side)
                if "value" in request:
                    value = request["value"]
                    require(len(json.dumps(value)) <= 8192, "Comando grande demais.")
                    require(s not in values or values[s] == value, "Comando ja confirmado.")
                    values[s] = value
                room["updated"] = time.time()
                self.save(room)
                # Sealed choices: no revealing the other choice until both submit.
                return {"ready": len(values) == 2, "values": [values["0"], values["1"]] if len(values) == 2 else None}
            else:
                require(action == "poll", "Acao desconhecida.")
            room["updated"] = time.time()
            self.save(room)
            return self.view(room, side)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self.reply(200, {"ok": True, "service": "Nordeluna Online", "protocol": PROTOCOL, "revision": REVISION, "version": VERSION,
                             "areas": self.server.store.areas})
        else:
            self.reply(404, {"ok": False, "error": "Rota desconhecida."})

    def do_POST(self):
        if self.path != "/api":
            self.reply(404, {"ok": False, "error": "Rota desconhecida."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            require(0 < length <= MAX_BODY, "Pedido grande demais ou vazio.")
            body = json.loads(self.rfile.read(length))
            response = self.server.store.handle(body)
            self.reply(200, dict(response, ok=True))
        except (ProtocolError, ValueError, UnicodeError, RecursionError) as exc:
            self.reply(400, {"ok": False, "error": str(exc)[:160]})
        except Exception:
            self.reply(500, {"ok": False, "error": "Erro interno do relay."})

    def reply(self, status, body):
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, fmt, *args):
        # No bearer tokens or Pokemon in logs.
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default="nordeluna-online.sqlite3")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
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
