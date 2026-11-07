"""Local masked-token UI: backup and update the existing Nordeluna Discloud app."""
import argparse
import ast
from contextlib import closing
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import queue
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
import zipfile

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.discloud.app/v2"
EXPECTED_APP = "nordeluna-online.discloud.dev"
PUBLIC_HEALTH = "https://nordeluna-online.discloud.dev/health"


class DeployError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, token):
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, route, method="GET", body=None, content_type=None, timeout=120):
        headers = {"api-token": self.token, "Accept": "application/json", "User-Agent": "Nordeluna-Local-Updater/1"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(API + route, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            raise DeployError(f"Discloud respondeu HTTP {error.code} em {method} {route}.") from None
        if len(raw) > 2 * 1024 * 1024:
            raise DeployError("Resposta do Discloud maior que o esperado.")
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get("status") not in ("ok", "success"):
            message = str(result.get("message", "Operacao recusada pelo Discloud.")) if isinstance(result, dict) else "Resposta invalida."
            raise DeployError(message.replace(self.token, "[token oculto]"))
        return result

    def commit(self, app_id, package):
        boundary = "Nordeluna" + uuid.uuid4().hex
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="nordeluna-update.zip"\r\n'
                   'Content-Type: application/zip\r\n\r\n').encode() + package.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        return self.request(f"/app/{urllib.parse.quote(app_id, safe='')}/commit", "PUT", payload,
                            "multipart/form-data; boundary=" + boundary, timeout=240)


def expected_package(package):
    with zipfile.ZipFile(package) as archive:
        if set(archive.namelist()) != {"main.py", "relay.py", "requirements.txt", "discloud.config"} or archive.testzip():
            raise DeployError("O ZIP do servidor esta incompleto ou inclui arquivos inesperados.")
        tree = ast.parse(archive.read("relay.py").decode("utf-8"))
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"REVISION", "VERSION", "DEFAULT_AREAS"}:
                        values[target.id] = ast.literal_eval(node.value)
        if set(values) != {"REVISION", "VERSION", "DEFAULT_AREAS"}:
            raise DeployError("O pacote nao informa versao e areas esperadas.")
        return values


def backup_stats(archive_path, destination):
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip():
            raise DeployError("O backup baixado esta corrompido. Nenhum deploy foi realizado.")
        matches = [i for i in archive.infolist() if i.filename.replace("\\", "/").endswith("data/relay.sqlite3")]
        if len(matches) != 1 or matches[0].file_size > 128 * 1024 * 1024:
            raise DeployError("O backup nao contem um unico data/relay.sqlite3 verificavel. Nenhum deploy foi realizado.")
        destination.write_bytes(archive.read(matches[0]))
        for suffix in ("-wal", "-shm"):
            name = matches[0].filename + suffix
            if name in archive.namelist():
                destination.with_name(destination.name + suffix).write_bytes(archive.read(name))
    # This is a local copy. Opening it normally recovers any uncheckpointed WAL
    # included in the stopped application's backup, without touching the server.
    with closing(sqlite3.connect(destination)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise DeployError("O banco do backup nao passou na verificacao de integridade.")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require_rooms = "rooms" in tables
        if not require_rooms:
            raise DeployError("Tabela de salas ausente no backup. Atualizacao cancelada.")
        return {"rooms": db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0],
                "accounts": db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] if "accounts" in tables else 0}


def download_backup(url, output):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise DeployError("O Discloud retornou um endereco de backup invalido.")
    # Signed backup URLs never receive the API token header.
    with urllib.request.urlopen(url, timeout=120) as response, output.open("wb") as stream:
        total = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > 256 * 1024 * 1024:
                raise DeployError("Backup maior que 256 MB. Atualizacao cancelada.")
            stream.write(chunk)


def deploy(token, package, notify):
    expected = expected_package(package)
    client = Client(token)
    notify("Verificando acesso ao Discloud...", "authenticating")
    client.request("/user")
    result = client.request("/app/all")
    apps = result.get("apps", [])
    apps = apps if isinstance(apps, list) else [apps]
    matches = [a for a in apps if isinstance(a, dict) and a.get("id") in
               {"nordeluna-online", "nordeluna-online.discloud.dev", "nordeluna-online.discloud.app"}]
    if not matches:
        matches = [a for a in apps if isinstance(a, dict) and str(a.get("name", "")).casefold() == "nordeluna online"]
    if len(matches) != 1:
        raise DeployError("Nao foi possivel identificar unicamente a aplicacao nordeluna-online nesta conta.")
    app = matches[0]
    app_id = app["id"]
    route = "/app/" + urllib.parse.quote(app_id, safe="")
    was_online = bool(app.get("online"))
    stopped, submitted = False, False
    cache = ROOT / ".cache/discloud-deploy" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    cache.mkdir(parents=True)
    try:
        if was_online:
            notify("Pausando o servidor para obter um backup consistente do banco...", "backing_up")
            client.request(route + "/stop", "PUT")
            stopped = True
            time.sleep(2)
        notify("Baixando backup da aplicacao existente...", "backing_up")
        data = client.request(route + "/backup").get("backups")
        if not isinstance(data, dict) or not isinstance(data.get("url"), str):
            raise DeployError("O Discloud nao disponibilizou o backup. Nenhum deploy foi realizado.")
        backup = cache / "before-update.zip"
        download_backup(data["url"], backup)
        before = backup_stats(backup, cache / "before-relay.sqlite3")
        notify(f'Backup verificado: {before["rooms"]} salas, {before["accounts"]} contas. Enviando atualizacao...', "deploying")
        submitted = True
        client.commit(app_id, package)
        notify("Codigo enviado. Aguardando o servidor atualizado...", "verifying")
        try:
            client.request(route + "/start", "PUT")
        except DeployError as error:
            # Commit can already start the container. A conflicting redundant
            # start is not a failed publication; the health check is authoritative.
            if "HTTP 409" not in str(error):
                raise
            notify("Discloud ja esta iniciando a aplicacao. Verificando a versao publicada...", "verifying")
        deadline = time.monotonic() + 180
        health = None
        while time.monotonic() < deadline:
            try:
                probe = urllib.request.Request(PUBLIC_HEALTH, headers={"User-Agent":"Nordeluna-Local-Updater/1","Accept":"application/json"})
                with urllib.request.urlopen(probe, timeout=10) as response:
                    candidate = json.load(response)
                if candidate.get("revision") == expected["REVISION"] and candidate.get("version") == expected["VERSION"]:
                    if candidate.get("areas") != expected["DEFAULT_AREAS"]:
                        raise DeployError("O servidor atualizou, mas NORDELUNA_ONLINE_AREAS no painel esta diferente da configuracao do pacote.")
                    health = candidate
                    break
            except (urllib.error.URLError, ValueError, TimeoutError):
                pass
            time.sleep(3)
        if health is None:
            raise DeployError("Codigo enviado, mas a verificacao publica nao confirmou a nova versao. Consulte os logs do Discloud.")
        # Read only numerical counts; no nick, Pokemon, account secret or room token is exported.
        command = 'python -c "import sqlite3,json;d=sqlite3.connect(\'file:data/relay.sqlite3?mode=ro\',uri=True);print(json.dumps({\'rooms\':d.execute(\'SELECT COUNT(*) FROM rooms\').fetchone()[0],\'accounts\':d.execute(\'SELECT COUNT(*) FROM accounts\').fetchone()[0]}))"'
        check = client.request(route + "/console", "PUT", json.dumps({"command": command}).encode(), "application/json")
        shell = check.get("apps", {}).get("shell", {})
        output = str(shell.get("stdout", ""))
        counts = next((json.loads(line) for line in reversed(output.splitlines()) if line.strip().startswith('{"rooms"')), None)
        if not isinstance(counts, dict) or any(counts.get(key, -1) < value for key, value in before.items()):
            raise DeployError("Servidor atualizado, mas a preservacao do banco precisa de verificacao. O backup local foi mantido; nenhum banco foi sobrescrito pelo atualizador.")
        return {"app_id": app_id, "health": health, "database": counts, "backup": str(backup)}
    except Exception:
        if was_online and not submitted:
            try:
                client.request(route + "/start", "PUT")
            except Exception:
                pass
        raise
    finally:
        client.token = ""


def main():
    # The deploy/backup functions also run in headless CI, without Tk installed.
    import tkinter as tk
    from tkinter import ttk

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--status", type=Path, default=ROOT / ".cache/discloud-deploy/status.json")
    args = parser.parse_args()
    package = args.package.resolve()
    expected = expected_package(package)
    events = queue.Queue()
    args.status.parent.mkdir(parents=True, exist_ok=True)

    def report(message, state, **extra):
        data = {"state": state, "message": message, **extra}
        temporary = args.status.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(args.status)
        events.put(message)

    root = tk.Tk()
    root.title("Atualizar Nordeluna no Discloud")
    root.geometry("650x420")
    root.minsize(590, 390)
    frame = ttk.Frame(root, padding=20); frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Atualizar o servidor Nordeluna", font=("Segoe UI", 17, "bold")).pack(anchor="w")
    ttk.Label(frame, text=f'Aplicacao: {EXPECTED_APP}\nVersao: {expected["VERSION"]} / revisao {expected["REVISION"]}\nPraca: mapa 39. Atualiza a aplicacao existente e faz backup antes.\nO online exige cliente 0.6; APKs antigos precisam de atualizacao.',
              wraplength=600).pack(anchor="w", pady=(10, 15))
    ttk.Label(frame, text="Token da API Discloud (somente nesta janela; nao sera salvo):").pack(anchor="w")
    entry = ttk.Entry(frame, show="*", width=70); entry.pack(fill="x", pady=8); entry.focus_set()
    ttk.Button(frame, text="Abrir painel Discloud / API Key", command=lambda:webbrowser.open("https://discloud.com/dashboard")).pack(anchor="w")
    progress = tk.StringVar(value="Aguardando o token local.")
    ttk.Label(frame, textvariable=progress, wraplength=590).pack(anchor="w", pady=18)
    busy = False

    def start():
        nonlocal busy
        token = entry.get().strip()
        if not token:
            progress.set("Cole seu token no campo acima."); return
        entry.delete(0, "end"); entry.configure(state="disabled")
        button.configure(state="disabled"); busy = True
        def work():
            nonlocal busy
            try:
                result = deploy(token, package, report)
                report("Atualizacao concluida e verificada. Praca 39 configurada; banco preservado.", "complete", result=result)
            except Exception as error:
                message = str(error).replace(token, "[token oculto]")
                report("Atualizacao nao concluida: " + message, "error")
            finally:
                busy = False
        threading.Thread(target=work, daemon=False).start()

    button = ttk.Button(frame, text="Fazer backup e atualizar servidor", command=start)
    button.pack(anchor="w")
    def poll():
        while not events.empty():
            progress.set(events.get())
        if not busy:
            entry.configure(state="normal"); button.configure(state="normal")
        root.after(150, poll)
    def close():
        if busy:
            progress.set("A atualizacao esta em andamento. Aguarde a conclusao antes de fechar.")
        else:
            root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    report("Aguardando o token na janela local.", "waiting_for_token")
    poll()
    root.mainloop()


if __name__ == "__main__":
    main()
