"""Nordeluna relay. Python 3.10+, standard library only. Run behind HTTPS online."""
import argparse
import json
import re
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROTOCOL = 1
REVISION = 3
MAX_BODY = 262144
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


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
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS rooms(code TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self.db.commit()
        # Ephemeral map presence must not touch trade receipts or survive restarts.
        self.presence = {}

    def map_action(self, request):
        now = time.monotonic()
        self.presence = {key: row for key, row in self.presence.items() if now - row["seen"] < 15}
        action = request["action"]
        if action == "map_join":
            require(len(self.presence) < 500, "Canal de mapa cheio.")
            profile = request.get("profile")
            require(isinstance(profile, dict), "Perfil invalido.")
            name = profile.get("name")
            require(isinstance(name, str) and 1 <= len(name.strip()) <= 24 and not re.search(r"[\\<>\x00-\x1f]", name), "Nick invalido.")
            build = request.get("build")
            require(isinstance(build, str) and 1 <= len(build) <= 100, "Build invalida.")
            token = secrets.token_urlsafe(32)
            self.presence[token] = {"id": secrets.token_hex(8), "name": name.strip(), "build": build,
                                    "seen": now, "map": None, "emote": None, "last_emote": -10.0, "sequence": 0}
            return {"token": token, "id": self.presence[token]["id"], "cooldown": 3}
        token = request.get("token")
        require(isinstance(token, str) and token in self.presence, "Canal de mapa expirou. Entre novamente.")
        if action == "map_leave":
            del self.presence[token]
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
                 if peer["id"] != row["id"] and peer["build"] == row["build"] and peer["map"] == row["map"]]
        return {"peers": peers[:40], "cooldown": 3}

    def save(self, room):
        self.db.execute("INSERT OR REPLACE INTO rooms VALUES(?,?)",
                        (room["code"], json.dumps(room, ensure_ascii=False, separators=(",", ":"))))

    def load(self, code):
        row = self.db.execute("SELECT data FROM rooms WHERE code=?", (code,)).fetchone()
        require(row is not None, "Sala nao encontrada.")
        return json.loads(row[0])

    def player(self, request):
        profile, payload = request.get("profile"), request.get("payload")
        require(isinstance(profile, dict) and isinstance(profile.get("name"), str), "Treinador invalido.")
        require(1 <= len(profile["name"]) <= 24 and not re.search(r"[\\<>\x00-\x1f]", profile["name"]), "Nome invalido.")
        require(isinstance(profile.get("type"), str) and len(profile["type"]) <= 64, "Tipo invalido.")
        require(type(profile.get("id")) is int and 0 <= profile["id"] < 2**32, "ID invalido.")
        require(isinstance(payload, list) and 1 <= len(payload) <= 6 and all(isinstance(x, dict) for x in payload), "Equipe invalida.")
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
            return {"protocol": PROTOCOL, "revision": REVISION, "service": "Nordeluna Online"}
        with self.lock, self.db:
            if isinstance(action, str) and action.startswith("map_"):
                return self.map_action(request)
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
        if self.path == "/health":
            self.reply(200, {"ok": True, "service": "Nordeluna Online", "protocol": PROTOCOL, "revision": REVISION})
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
