"""Local Windows publisher for Nordeluna; no AI services or API keys required."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = Path(r"C:\Users\tiomi\Downloads\Pokémon Nordeluna\Pokemon Essentials v21.1 2023-07-30\Pokemon Essentials v21.1 2023-07-30")
REPOSITORY = "tiomiojin-coder/nordeluna"
WORKFLOW = "nordeluna-android.yml"
RUNTIME_DIRS = ("Audio", "Data", "Fonts", "Graphics", "Movies", "Plugins")
RUNTIME_FILES = ("mkxp.json", "soundfont.sf2", "achievements.dat")
DEVELOPMENT_DIRS = {".venv", ".backups", "__pycache__", ".git", ".pytest_cache"}
STATE = ROOT / ".cache/nordeluna-updater"
SETTINGS = STATE / "settings.json"


class UpdateError(Exception):
    pass


class Cancelled(UpdateError):
    pass


def checkpoint(stop):
    if stop.is_set():
        raise Cancelled("Operação interrompida. Uma build já enviada continua no GitHub.")


def load_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"source": str(DEFAULT_GAME), "downloads": str(ROOT / "build-android/APKs")}


def save_settings(settings):
    STATE.mkdir(parents=True, exist_ok=True)
    temporary = SETTINGS.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(SETTINGS)


@contextlib.contextmanager
def exclusive_lock():
    STATE.mkdir(parents=True, exist_ok=True)
    handle = (STATE / "update.lock").open("a+b")
    handle.seek(0, 2)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        import msvcrt
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise UpdateError("Outro atualizador já está aberto e executando uma operação.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        # Never expose embedded credentials in remote URLs.
        message = re.sub(r"https://[^\s/@]+:[^\s/@]+@", "https://", message)
        raise UpdateError(message or "O Git não conseguiu concluir a operação.")
    return result.stdout.decode("utf-8", errors="replace").strip()


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if urllib.parse.urlparse(req.full_url).netloc != urllib.parse.urlparse(newurl).netloc:
            redirected.remove_header("Authorization")
        return redirected


class GitHub:
    def __init__(self):
        result = subprocess.run(["git", "credential", "fill"], cwd=ROOT,
                                input=b"protocol=https\nhost=github.com\n\n",
                                capture_output=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        fields = dict(line.split("=", 1) for line in result.stdout.decode("utf-8", errors="replace").splitlines() if "=" in line)
        if result.returncode or not fields.get("password"):
            raise UpdateError("Faça login no GitHub pelo Git/Git Credential Manager e tente novamente.")
        self.token = fields["password"]
        self.opener = urllib.request.build_opener(SafeRedirect())

    def open(self, route):
        url = "https://api.github.com/repos/" + REPOSITORY + ("/" + route if route else "")
        url += ("&" if "?" in url else "?") + "_=" + str(time.time_ns())
        request = urllib.request.Request(url,
            headers={"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
                     "User-Agent": "Nordeluna-Updater", "Cache-Control": "no-cache"})
        try:
            return self.opener.open(request, timeout=60)
        except urllib.error.HTTPError as exc:
            raise UpdateError(f"GitHub respondeu HTTP {exc.code}. Confira login, acesso ao repositório e conexão.") from None
        except urllib.error.URLError:
            raise UpdateError("Não foi possível conectar ao GitHub. Confira a internet e tente acompanhar novamente.") from None

    def get(self, route):
        with self.open(route) as response:
            return json.load(response)


def inventory(source):
    source = source.resolve(strict=True)
    for name in ("Game.ini", "Data/Scripts.rxdata", "mkxp.json", "soundfont.sf2"):
        if not (source / name).is_file():
            raise UpdateError(f"Arquivo obrigatório ausente: {name}. Selecione a pasta que contém Game.ini.")
    files = {}
    for folder in RUNTIME_DIRS:
        for base, dirs, names in os.walk(source / folder, followlinks=False):
            parent = Path(base).relative_to(source).as_posix()
            def include_directory(name):
                if parent == "Plugins" and name == "New Animation Editor BETA":
                    return False  # Authoring tool; not present in the runtime plugin bundle.
                if name in DEVELOPMENT_DIRS or (Path(base) / name).is_symlink():
                    return False
                if parent == "Plugins" and (name == "output" or name.startswith("_") and
                        (name.endswith("_tests") or name.endswith("_reference"))):
                    return False
                if parent == "Plugins/Nordeluna Online" and name == "server":
                    return False
                return True
            dirs[:] = [d for d in dirs if include_directory(d)]
            for name in names:
                path = Path(base) / name
                if path.is_symlink():
                    raise UpdateError(f"Arquivo vinculado não permitido no pacote: {path.name}")
                stat = path.stat()
                files[path.relative_to(source).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    for name in ("Game.ini", *RUNTIME_FILES):
        path = source / name
        if path.is_file():
            stat = path.stat()
            files[name] = (stat.st_size, stat.st_mtime_ns)
    return files


def package_game(source, output, stop, notify):
    """Read source only; exclude saves and Python environments; keep ZIP Unicode flags."""
    source = Path(source).resolve(strict=True)
    manifest = inventory(source)
    last_log = time.monotonic()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for index, (name, original_stat) in enumerate(sorted(manifest.items()), 1):
            checkpoint(stop)
            path = source / name
            if name == "Game.ini":
                raw = path.read_bytes()
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = raw.decode("cp1252")
                text = re.sub(r"(?m)^Title=[^\r\n]*", "Title=Pokemon Nordeluna", text)
                archive.writestr(name, text.encode("utf-8"))
            else:
                archive.write(path, name)
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != original_stat:
                raise UpdateError("O jogo mudou durante a preparação. Salve e feche o editor antes de tentar novamente.")
            if time.monotonic() - last_log > 2:
                notify("status", f"Preparando arquivos: {index}/{len(manifest)}")
                last_log = time.monotonic()
    if inventory(source) != manifest:
        raise UpdateError("Foram adicionados ou alterados arquivos durante a preparação. Tente novamente.")
    notify("status", "Conferindo integridade do pacote…")
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise UpdateError(f"Pacote corrompido: {bad}")
        for entry in archive.infolist():
            if any(ord(c) > 127 for c in entry.filename) and not entry.flag_bits & 0x800:
                raise UpdateError(f"Nome de arquivo sem UTF-8: {entry.filename}")
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    # Keep future map patches tied to the exact files included in this APK.
    # This writes only local authoring metadata; source game/saves stay read-only.
    if "Plugins/Nordeluna Online/028_ContentUpdates.rb" in manifest:
        import importlib.util
        spec = importlib.util.spec_from_file_location("apk_content_base", ROOT / "scripts/content-update-tools.py")
        content = importlib.util.module_from_spec(spec); spec.loader.exec_module(content)
        content.capture_apk_base(output)
    notify("log", f"Pacote conferido: {len(manifest)} arquivos do jogo.")
    return digest


def new_release_text(patch, workflow, digest):
    pattern = r"(?m)^(\+\s*versionCode\s+)(\d+)(\s*)$"
    matches = list(re.finditer(pattern, patch))
    if len(matches) != 1:
        raise UpdateError("Não foi possível identificar uma única revisão do APK em android/nordeluna.patch.")
    revision = int(matches[0].group(2)) + 1
    patch = re.sub(pattern, lambda m: m.group(1) + str(revision) + m.group(3), patch)
    workflow, count = re.subn(r"(?m)^(\s*GAME_ARCHIVE_SHA256:\s*)[a-fA-F0-9]{64}(\s*)$",
                             lambda m: m.group(1) + digest + m.group(2), workflow)
    if count != 1:
        raise UpdateError("Não foi possível atualizar o hash da build.")
    return patch, workflow, revision


def install_package(archive, digest, directory, chunk_size=90 * 1024 * 1024):
    parts = []
    with archive.open("rb") as stream:
        index = 1
        while data := stream.read(chunk_size):
            path = directory / f"game-assets.zip.part{index:03d}"
            path.write_bytes(data)
            parts.append(path)
            index += 1
    (directory / "sha256.txt").write_text(digest + "  game-assets.zip\n", encoding="utf-8")
    return parts


def extract_apk(archive_path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        apks = [name for name in archive.namelist() if name.endswith(".apk")]
        if len(apks) != 1:
            raise UpdateError("O artifact não contém exatamente um APK.")
        name = apks[0]
        expected = archive.read(name + ".sha256").decode("utf-8").split()[0].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise UpdateError("Arquivo de verificação do APK inválido.")
        # Ignore directory components supplied by the ZIP; extract only the APK.
        apk = destination / Path(name.replace("\\", "/")).name
        temporary = apk.with_suffix(".apk.part")
        digest = hashlib.sha256()
        try:
            with archive.open(name) as source, temporary.open("wb") as output:
                while data := source.read(1024 * 1024):
                    output.write(data)
                    digest.update(data)
            if digest.hexdigest() != expected:
                raise UpdateError("A verificação SHA-256 do APK falhou. Baixe novamente.")
            temporary.replace(apk)
            apk.with_suffix(".apk.sha256").write_text(expected + "  " + apk.name + "\n", encoding="utf-8")
        finally:
            temporary.unlink(missing_ok=True)
        return apk


def monitor(client, settings, stop, notify):
    sha = settings.get("last_commit")
    if not sha:
        raise UpdateError("Nenhum envio registrado. Primeiro clique em Gerar novo APK.")
    start = time.monotonic()
    run = None
    failures = 0
    while time.monotonic() - start < 3600:
        checkpoint(stop)
        try:
            if run is None:
                runs = client.get(f"actions/workflows/{WORKFLOW}/runs?head_sha={sha}&per_page=10")["workflow_runs"]
                run = next((r for r in runs if r["head_sha"] == sha), None)
            else:
                run = client.get(f"actions/runs/{run['id']}")
            failures = 0
        except UpdateError as exc:
            failures += 1
            if failures >= 5:
                raise
            notify("log", f"Consulta temporariamente indisponível ({failures}/5): {exc}")
            stop.wait(15)
            continue
        if run:
            settings["last_run_url"] = run["html_url"]
            settings["last_run_id"] = run["id"]
            save_settings(settings)
            notify("url", run["html_url"])
            notify("status", "Build no GitHub: " + run["status"])
            if run["status"] == "completed":
                if run["conclusion"] != "success":
                    jobs = client.get(f"actions/runs/{run['id']}/jobs")["jobs"]
                    failed = [step["name"] for job in jobs for step in job.get("steps", []) if step.get("conclusion") == "failure"]
                    raise UpdateError("Build falhou" + (": " + ", ".join(failed) if failed else "") + ". Abra o GitHub para consultar o log.")
                artifacts = client.get(f"actions/runs/{run['id']}/artifacts")["artifacts"]
                artifact = next((a for a in artifacts if a["name"].startswith("Nordeluna-Android") and 'testers' not in a['name'] and not a["expired"]), None)
                if not artifact:
                    raise UpdateError("Build concluída, mas o APK não foi encontrado nos artifacts.")
                folder = Path(settings["downloads"]).expanduser().resolve() / (artifact["name"] + "-" + str(run["id"]))
                folder.mkdir(parents=True, exist_ok=True)
                temporary = folder / "download.zip.part"
                notify("status", "Baixando APK…")
                with client.open(f"actions/artifacts/{artifact['id']}/zip") as response, temporary.open("wb") as output:
                    while data := response.read(1024 * 1024):
                        checkpoint(stop)
                        output.write(data)
                archive = folder / "artifact.zip"
                temporary.replace(archive)
                notify("status", "Conferindo APK baixado…")
                apk = extract_apk(archive, folder)
                settings["last_apk"] = str(apk)
                save_settings(settings)
                notify("apk", str(apk))
                notify("log", "Build concluída. APK baixado e SHA-256 conferido.")
                return
        else:
            notify("status", "Aguardando o GitHub iniciar a build…")
            if time.monotonic() - start > 180:
                raise UpdateError("O envio foi concluído, mas não apareceu uma build. Abra o GitHub Actions e execute o workflow manualmente.")
        stop.wait(15)
    raise UpdateError("O acompanhamento atingiu 1 hora. Clique em Acompanhar último envio para continuar.")


def update(settings, stop, notify, resume=False):
    with exclusive_lock():
        save_settings(settings)
        if shutil.which("git") is None:
            raise UpdateError("Git não encontrado. Instale o Git for Windows e faça login no GitHub.")
        if git("branch", "--show-current") != "main":
            raise UpdateError("Abra o repositório na branch main antes de atualizar.")
        remote = git("remote", "get-url", "origin")
        if remote not in (f"https://github.com/{REPOSITORY}.git", f"https://github.com/{REPOSITORY}", f"git@github.com:{REPOSITORY}.git"):
            raise UpdateError("O origin não aponta para o repositório Nordeluna esperado.")
        if git("status", "--porcelain"):
            raise UpdateError("Há alterações locais não salvas em commit. Finalize essas alterações antes de gerar o APK; o atualizador não as sobrescreve.")
        client = GitHub()
        client.get("")
        if resume:
            if settings.get("pending_push"):
                if git("rev-parse", "HEAD") != settings.get("last_commit"):
                    raise UpdateError("O repositório mudou após o envio interrompido. Revise os commits antes de continuar.")
                notify("status", "Retomando envio ao GitHub…")
                git("push", "origin", "main")
                settings["pending_push"] = False
                save_settings(settings)
            return monitor(client, settings, stop, notify)
        if settings.get("pending_push"):
            raise UpdateError("Há um envio interrompido. Clique em Acompanhar / retomar envio antes de criar outra atualização.")
        notify("status", "Conferindo repositório e acesso ao GitHub…")
        git("fetch", "origin", "main")
        behind = int(git("rev-list", "--count", "HEAD..origin/main"))
        ahead = int(git("rev-list", "--count", "origin/main..HEAD"))
        if behind and ahead:
            raise UpdateError("Os commits locais e os do GitHub divergiram. Resolva isso antes de atualizar.")
        if behind:
            git("merge", "--ff-only", "origin/main")
        active = client.get(f"actions/workflows/{WORKFLOW}/runs?per_page=20")["workflow_runs"]
        if any(r["status"] != "completed" for r in active):
            raise UpdateError("Já existe uma build em andamento. Aguarde a conclusão antes de enviar outra.")
        source = Path(settings["source"])
        inventory(source)
        STATE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="package-", dir=STATE) as task:
            task = Path(task)
            archive = task / "game.zip"
            notify("log", "Lendo os arquivos atuais do jogo. Mantenha o editor fechado até terminar esta etapa.")
            digest = package_game(source, archive, stop, notify)
            patch_path = ROOT / "android/nordeluna.patch"
            workflow_path = ROOT / ".github/workflows" / WORKFLOW
            patch, workflow, revision = new_release_text(patch_path.read_text(encoding="utf-8"), workflow_path.read_text(encoding="utf-8"), digest)
            staged = task / "parts"
            staged.mkdir()
            parts = install_package(archive, digest, staged)
            checkpoint(stop)
            backup = STATE / "backups" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + "-" + str(revision))
            backup.mkdir(parents=True)
            assets = ROOT / "game-assets"
            assets.resolve().relative_to(ROOT.resolve())
            targets = [patch_path, workflow_path, assets / "sha256.txt", *sorted(assets.glob("game-assets.zip.part[0-9][0-9][0-9]"))]
            for path in targets:
                shutil.copy2(path, backup / path.name)
            generated = [assets / p.name for p in parts]
            committed = False
            try:
                for path in targets[3:]:
                    path.unlink()
                for part in parts:
                    shutil.copy2(part, assets / part.name)
                shutil.copy2(staged / "sha256.txt", assets / "sha256.txt")
                patch_path.write_text(patch, encoding="utf-8", newline="\n")
                workflow_path.write_text(workflow, encoding="utf-8", newline="\n")
                notify("status", "Registrando atualização…")
                git("add", "--", "android/nordeluna.patch", ".github/workflows/" + WORKFLOW, "game-assets")
                git("commit", "-m", f"Update Nordeluna game content (Android revision {revision})")
                committed = True
                settings["last_commit"] = git("rev-parse", "HEAD")
                settings["pending_push"] = True
                save_settings(settings)
            except Exception:
                if not committed:
                    for path in generated:
                        path.unlink(missing_ok=True)
                    for path in targets:
                        shutil.copy2(backup / path.name, path)
                    git("reset", "--", "android/nordeluna.patch", ".github/workflows/" + WORKFLOW, "game-assets")
                raise
            notify("log", f"Revisão {revision} criada. Backup local: {backup}")
            checkpoint(stop)
            notify("status", "Enviando atualização ao GitHub…")
            git("push", "origin", "main")
            settings["pending_push"] = False
            save_settings(settings)
        notify("log", "Envio concluído. A build foi solicitada pelo envio à main.")
        monitor(client, settings, stop, notify)
