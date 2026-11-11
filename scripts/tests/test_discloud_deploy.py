import importlib.util
from contextlib import closing
import io
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("local_deploy", ROOT / "scripts/discloud-local-deploy.py")
deploy = importlib.util.module_from_spec(spec); spec.loader.exec_module(deploy)
spec = importlib.util.spec_from_file_location("deploy_package", ROOT / "scripts/package-discloud.py")
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
MODERATION_TABLES = ("moderation_owner", "moderators", "moderation_sanctions", "moderation_audit", "chat_history", "moderation_state")


class DiscloudDeployTests(unittest.TestCase):
    def test_deploy_core_imports_without_graphical_toolkit(self):
        real_import = __import__
        def headless_import(name, *args, **kwargs):
            if name == "tkinter" or name.startswith("tkinter."):
                raise ModuleNotFoundError("No module named 'tkinter'")
            return real_import(name, *args, **kwargs)
        spec = importlib.util.spec_from_file_location("headless_deploy", ROOT / "scripts/discloud-local-deploy.py")
        module = importlib.util.module_from_spec(spec)
        with patch("builtins.__import__", side_effect=headless_import):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.deploy))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = builder.package("nordeluna-online", self.root / "server.zip")
        db = self.root / "source.sqlite3"
        with closing(sqlite3.connect(db)) as connection:
            connection.execute("CREATE TABLE rooms(code TEXT PRIMARY KEY,data TEXT)")
            connection.execute("INSERT INTO rooms VALUES('receipt','committed')")
            for name in MODERATION_TABLES:
                connection.execute("CREATE TABLE " + name + "(id INTEGER PRIMARY KEY)")
                connection.execute("INSERT INTO " + name + " VALUES(1)")
            connection.commit()
        self.backup = self.root / "backup.zip"
        with zipfile.ZipFile(self.backup, "w") as archive:
            archive.write(db, "data/relay.sqlite3")

    def test_package_and_backup_inspection(self):
        expected = deploy.expected_package(self.package)
        self.assertEqual(expected["VERSION"], "0.10.8")
        self.assertEqual(expected["REVISION"], 20)
        self.assertEqual(expected["DEFAULT_AREAS"], dict(plaza=39, coliseum=40, market=41))
        self.assertEqual(deploy.backup_stats(self.backup, self.root / "inspect.sqlite3"),
                         dict(rooms=1, accounts=0, **{name: 1 for name in MODERATION_TABLES}))

    def test_revision_12_rollback_remains_supported_without_moderation(self):
        rollback = self.root / "rollback.zip"
        with zipfile.ZipFile(self.package) as original, zipfile.ZipFile(rollback, "w") as archive:
            for entry in original.infolist():
                if entry.filename == "moderation.py":
                    continue
                contents = original.read(entry)
                if entry.filename == "relay.py":
                    source = re.sub(r'(?m)^REVISION = [^\r\n]+', 'REVISION = 12', contents.decode("utf-8"))
                    contents = re.sub(r'(?m)^VERSION = [^\r\n]+', 'VERSION = "0.9.1"', source).encode("utf-8")
                archive.writestr(entry, contents)
        expected = deploy.expected_package(rollback)
        self.assertEqual((expected["VERSION"], expected["REVISION"]), ("0.9.1", 12))

    def test_revision_13_requires_moderation_module(self):
        incomplete = self.root / "incomplete.zip"
        with zipfile.ZipFile(self.package) as original, zipfile.ZipFile(incomplete, "w") as archive:
            for entry in original.infolist():
                if entry.filename != "moderation.py":
                    archive.writestr(entry, original.read(entry))
        with self.assertRaisesRegex(deploy.DeployError, "moderacao"):
            deploy.expected_package(incomplete)

    def test_backup_before_moderation_remains_supported(self):
        source = self.root / "legacy.sqlite3"
        with closing(sqlite3.connect(source)) as connection:
            connection.execute("CREATE TABLE rooms(code TEXT PRIMARY KEY,data TEXT)")
            connection.execute("INSERT INTO rooms VALUES('receipt','committed')")
            connection.commit()
        backup = self.root / "legacy.zip"
        with zipfile.ZipFile(backup, "w") as archive:
            archive.write(source, "data/relay.sqlite3")
        self.assertEqual(deploy.backup_stats(backup, self.root / "legacy-inspect.sqlite3"),
                         dict(rooms=1, accounts=0))

    def test_order_and_public_health_confirmation(self):
        calls = []
        console_commands = []
        counts = dict(rooms=1, accounts=0, **{name: 1 for name in MODERATION_TABLES})
        backup = self.backup
        class Client:
            def __init__(self, token): self.token=token
            def request(self, route, method="GET", *args, **kwargs):
                calls.append((method,route))
                if route=="/app/all":return {"apps":[{"id":"nordeluna-online.discloud.dev","online":True}]}
                if route.endswith("/backup"):return {"backups":{"url":"https://backup.example/one.zip"}}
                if route.endswith("/console"):
                    console_commands.append(json.loads(args[0])["command"])
                    return {"apps":{"shell":{"stdout":json.dumps(counts)}}}
                if route.endswith("/start"):raise deploy.DeployError("Discloud respondeu HTTP 409 em PUT start.")
                return {"status":"ok"}
            def commit(self, app_id, package): calls.append(("COMMIT",app_id))
        expected=deploy.expected_package(self.package)
        health = {"revision":expected['REVISION'],"version":expected['VERSION'],"areas":expected['DEFAULT_AREAS']}
        def download(url,destination):destination.write_bytes(backup.read_bytes())
        with patch.object(deploy,"ROOT",self.root),patch.object(deploy,"Client",Client), \
             patch.object(deploy,"download_backup",download),patch.object(deploy.time,"sleep"), \
             patch.object(deploy.urllib.request,"urlopen",return_value=io.BytesIO(json.dumps(health).encode())):
            result=deploy.deploy("private-test-token",self.package,lambda *args:None)
        steps=[route for _,route in calls]
        self.assertLess(next(i for i,s in enumerate(steps) if s.endswith('/stop')), next(i for i,s in enumerate(steps) if s.endswith('/backup')))
        self.assertLess(next(i for i,s in enumerate(steps) if s.endswith('/backup')), next(i for i,(method,_) in enumerate(calls) if method=='COMMIT'))
        self.assertEqual(result["database"], counts)
        self.assertTrue(all(name in console_commands[0] for name in MODERATION_TABLES))
        self.assertNotIn("private-test-token",json.dumps(result))

        counts["chat_history"] = 0
        with patch.object(deploy,"ROOT",self.root),patch.object(deploy,"Client",Client), \
             patch.object(deploy,"download_backup",download),patch.object(deploy.time,"sleep"), \
             patch.object(deploy.urllib.request,"urlopen",return_value=io.BytesIO(json.dumps(health).encode())):
            with self.assertRaisesRegex(deploy.DeployError, "preservacao do banco"):
                deploy.deploy("private-test-token",self.package,lambda *args:None)
