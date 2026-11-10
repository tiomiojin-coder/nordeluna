"""Durable gift claims. Administration is local/Discloud console only, never /api."""
import json
import re
import secrets
import time


class GiftError(ValueError):
    pass


def check(value, message):
    if not value:
        raise GiftError(message)


def code_text(value):
    check(isinstance(value, str), "Codigo de presente invalido.")
    code = value.strip().upper()
    check(re.fullmatch(r"[A-Z0-9-]{4,32}", code), "Codigo: use 4 a 32 letras, numeros ou hifen.")
    return code


def rewards_data(value):
    check(isinstance(value, list) and 1 <= len(value) <= 10, "Inclua de 1 a 10 recompensas.")
    result = []
    def number(n, low, high):
        check(type(n) is int and low <= n <= high, "Quantidade, nivel ou forma invalida.")
        return n
    def identifier(v):
        check(isinstance(v, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", v), "ID de especie, item ou golpe invalido.")
        return v
    for row in value:
        check(isinstance(row, dict), "Recompensa invalida.")
        kind = row.get("kind")
        if kind == "item":
            result.append(dict(kind=kind, id=identifier(row.get("id")), quantity=number(row.get("quantity"), 1, 999)))
        elif kind == "money":
            result.append(dict(kind=kind, amount=number(row.get("amount"), 1, 9999999)))
        elif kind == "outfit":
            result.append(dict(kind=kind, id=identifier(row.get("id"))))
        elif kind == "pokemon":
            check(type(row.get("shiny", False)) is bool, "Shiny deve ser verdadeiro ou falso.")
            gift = dict(kind=kind, species=identifier(row.get("species")), level=number(row.get("level"), 1, 100),
                        form=number(row.get("form", 0), 0, 999), shiny=row.get("shiny", False))
            check(type(row.get('egg',False)) is bool,'Ovo deve ser verdadeiro ou falso.')
            if row.get('egg'):
                gift['egg']=True
                gift['level']=1
            if row.get("item"):
                gift["item"] = identifier(row["item"])
            if row.get("moves") is not None:
                check(isinstance(row["moves"], list) and 1 <= len(row["moves"]) <= 4, "Escolha de 1 a 4 golpes.")
                gift["moves"] = [identifier(move) for move in row["moves"]]
                check(len(set(gift["moves"])) == len(gift["moves"]), "Golpes repetidos.")
            result.append(gift)
        else:
            raise GiftError("Tipo de recompensa desconhecido.")
    check(sum(row["kind"] == "pokemon" for row in result) <= 6, "Limite de seis Pokemon por presente.")
    return result


class GiftService:
    def setup_gifts(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS gifts(
            code TEXT PRIMARY KEY,id TEXT NOT NULL UNIQUE,title TEXT NOT NULL,rewards TEXT NOT NULL,
            created INTEGER NOT NULL,expires INTEGER,max_claims INTEGER,enabled INTEGER NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS gift_claims(
            id TEXT PRIMARY KEY,account TEXT NOT NULL,gift TEXT NOT NULL,data TEXT NOT NULL,
            state TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(account,gift))""")
        self.db.execute("CREATE INDEX IF NOT EXISTS gift_claims_gift ON gift_claims(gift)")
        self.db.execute("CREATE INDEX IF NOT EXISTS gift_claims_account ON gift_claims(account,created DESC)")
        self.gift_rates = {}

    def gift_admin(self, request):
        """Call through an authenticated hosting console, not a public route."""
        check(isinstance(request, dict), "Operacao administrativa invalida.")
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            action = request.get("action")
            if action == "list":
                return {"gifts": [dict(code=row[0], title=row[1], expires=row[2], limit=row[3], enabled=bool(row[4]), claims=row[5])
                    for row in self.db.execute("SELECT g.code,g.title,g.expires,g.max_claims,g.enabled,(SELECT COUNT(*) FROM gift_claims c WHERE c.gift=g.id) FROM gifts g ORDER BY g.created DESC LIMIT 200")]}
            code = code_text(request.get("code"))
            if action == "disable":
                check(self.db.execute("UPDATE gifts SET enabled=0 WHERE code=?", (code,)).rowcount == 1, "Codigo nao encontrado.")
                return {"disabled": code}
            check(action == "create", "Operacao administrativa desconhecida.")
            title = request.get("title")
            check(isinstance(title, str) and 1 <= len(title.strip()) <= 70 and not re.search(r"[\x00-\x1f]", title), "Titulo invalido.")
            expires, limit = request.get("expires"), request.get("limit")
            check(expires is None or (type(expires) is int and time.time() < expires <= 4102444800), "Validade precisa estar no futuro.")
            check(limit is None or (type(limit) is int and 1 <= limit <= 1000000), "Limite de resgates invalido.")
            check(self.db.execute("SELECT 1 FROM gifts WHERE code=?", (code,)).fetchone() is None, "Este codigo ja existe. Crie outro; presentes publicados sao imutaveis.")
            rewards = rewards_data(request.get("rewards"))
            self.db.execute("INSERT INTO gifts VALUES(?,?,?,?,?,?,?,1)",
                (code, secrets.token_hex(16), title.strip(), json.dumps(rewards, separators=(",", ":")), int(time.time()), expires, limit))
            return {"published": code, "title": title.strip()}

    def gift_ticket(self, row):
        return dict(json.loads(row[3]), id=row[0], state=row[4], created=row[5])

    def gift_action(self, request):
        account = self.account(request)["id"]
        now = int(time.time())
        rate = self.gift_rates.get(account, (now, 0))
        if now - rate[0] >= 60:
            rate = (now, 0)
        check(rate[1] < 30, "Muitos pedidos de presente. Aguarde um minuto.")
        if len(self.gift_rates) > 2048:
            self.gift_rates = {k: v for k, v in self.gift_rates.items() if now-v[0] < 60}
        self.gift_rates[account] = (rate[0], rate[1]+1)
        action = request["action"]
        if action == "gift_history":
            return {"claims": [self.gift_ticket(row) for row in self.db.execute(
                "SELECT * FROM gift_claims WHERE account=? ORDER BY created DESC,rowid DESC LIMIT 100", (account,))]}
        if action in ("gift_begin", "gift_ack", "gift_status"):
            claim = request.get("claim")
            check(isinstance(claim, str) and re.fullmatch(r"[0-9a-f]{32}", claim), "Recibo invalido.")
            if action != "gift_status":
                self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT * FROM gift_claims WHERE id=? AND account=?", (claim, account)).fetchone()
            check(row is not None, "Este presente nao pertence a esta conta.")
            state = row[4]
            if action == "gift_begin" and state == "reserved":
                self.db.execute("UPDATE gift_claims SET state='issued',updated=? WHERE id=?", (now, claim))
                state = "issued"
            elif action == "gift_ack":
                check(state in ("issued", "delivered"), "Prepare e grave a entrega antes de confirmar.")
                if state != "delivered":
                    self.db.execute("UPDATE gift_claims SET state='delivered',updated=? WHERE id=?", (now, claim))
                state = "delivered"
            return dict(self.gift_ticket(row), state=state)
        check(action in ("gift_preview", "gift_reserve"), "Acao de presente desconhecida.")
        code = code_text(request.get("code"))
        if action == "gift_reserve":
            self.db.execute("BEGIN IMMEDIATE")
        gift = self.db.execute("SELECT * FROM gifts WHERE code=?", (code,)).fetchone()
        check(gift is not None, "Codigo de presente nao encontrado.")
        old = self.db.execute("SELECT * FROM gift_claims WHERE account=? AND gift=?", (account, gift[1])).fetchone()
        if old:
            return {"claim": self.gift_ticket(old)}
        check(gift[7] == 1, "Este codigo foi encerrado.")
        check(gift[5] is None or gift[5] > now, "Este codigo expirou.")
        total = self.db.execute("SELECT COUNT(*) FROM gift_claims WHERE gift=?", (gift[1],)).fetchone()[0]
        check(gift[6] is None or total < gift[6], "O limite deste presente foi atingido.")
        data = dict(code=gift[0], gift=gift[1], title=gift[2], rewards=json.loads(gift[3]))
        if action == "gift_preview":
            return {"preview": data}
        identity = secrets.token_hex(16)
        self.db.execute("INSERT INTO gift_claims VALUES(?,?,?,?,?,?,?)", (identity, account, gift[1], json.dumps(data), "reserved", now, now))
        return {"claim": dict(data, id=identity, state="reserved", created=now)}
