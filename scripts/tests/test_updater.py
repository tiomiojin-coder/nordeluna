import hashlib
import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import updater_core as core


def fixture(folder):
    files = {"Game.ini": b"[Game]\nTitle=Old\n", "Data/Scripts.rxdata": b"scripts",
             "mkxp.json": b"{}", "soundfont.sf2": b"font", "Graphics/Laboratório.png": b"image",
             "Audio/BGM/música.ogg": b"music", "Plugins/.venv/private.txt": b"exclude",
             "Game.rxdata": b"personal save"}
    for name, data in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return files


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "game"
        self.files = fixture(self.source)
        self.stop = threading.Event()
        self.notify = lambda *args: None

    def tearDown(self):
        self.temp.cleanup()

    def test_package_unicode_exclusions_and_source_untouched(self):
        output = self.root / "game.zip"
        digest = core.package_game(self.source, output, self.stop, self.notify)
        self.assertEqual(digest, hashlib.sha256(output.read_bytes()).hexdigest())
        with zipfile.ZipFile(output) as archive:
            self.assertNotIn("Game.rxdata", archive.namelist())
            self.assertFalse(any(".venv" in name for name in archive.namelist()))
            self.assertIn(b"Title=Pokemon Nordeluna", archive.read("Game.ini"))
            self.assertTrue(archive.getinfo("Graphics/Laboratório.png").flag_bits & 0x800)
            self.assertIsNone(archive.testzip())
        for name, data in self.files.items():
            self.assertEqual((self.source / name).read_bytes(), data)

    def test_source_changed_during_package_rejected(self):
        original = core.inventory(self.source)
        changed = dict(original, **{"new-file": (1, 1)})
        with patch.object(core, "inventory", side_effect=[original, changed]):
            with self.assertRaisesRegex(core.UpdateError, "alterados"):
                core.package_game(self.source, self.root / "game.zip", self.stop, self.notify)

    def test_cancellation(self):
        self.stop.set()
        with self.assertRaises(core.Cancelled):
            core.package_game(self.source, self.root / "game.zip", self.stop, self.notify)

    def test_missing_required_file(self):
        (self.source / "Data/Scripts.rxdata").unlink()
        with self.assertRaisesRegex(core.UpdateError, "Scripts.rxdata"):
            core.inventory(self.source)

    def test_revision_and_hash(self):
        workflow = "env:\n  GAME_ARCHIVE_SHA256: " + "a" * 64 + "\nnext: value\n"
        result, workflow, revision = core.new_release_text("+        versionCode 12\n+        versionName \"1.8.0\"\n", workflow, "b" * 64)
        self.assertEqual(revision, 13)
        self.assertIn("versionCode 13\n", result)
        self.assertIn('versionName "1.8.0"', result)
        self.assertIn("b" * 64, workflow)
        self.assertIn("next: value", workflow)
        with self.assertRaises(core.UpdateError):
            core.new_release_text("+versionCode 1\n+versionCode 2\n", workflow, "c" * 64)

    def test_split_and_reassemble(self):
        archive = self.root / "data.zip"
        archive.write_bytes(b"0123456789")
        parts_dir = self.root / "parts"
        parts_dir.mkdir()
        parts = core.install_package(archive, "a" * 64, parts_dir, chunk_size=4)
        self.assertEqual([p.stat().st_size for p in parts], [4, 4, 2])
        self.assertEqual(b"".join(p.read_bytes() for p in parts), archive.read_bytes())

    def artifact(self, digest):
        archive = self.root / "artifact.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("../../Nordeluna.apk", b"apk bytes")
            output.writestr("../../Nordeluna.apk.sha256", digest + "  build-android/Nordeluna.apk\n")
        return archive

    def test_apk_verified_and_path_confined(self):
        archive = self.artifact(hashlib.sha256(b"apk bytes").hexdigest())
        destination = self.root / "download"
        result = core.extract_apk(archive, destination)
        self.assertEqual(result, destination / "Nordeluna.apk")
        self.assertEqual(result.read_bytes(), b"apk bytes")

    def test_bad_apk_preserves_existing_file(self):
        destination = self.root / "download"
        destination.mkdir()
        existing = destination / "Nordeluna.apk"
        existing.write_bytes(b"previous apk")
        with self.assertRaisesRegex(core.UpdateError, "SHA-256"):
            core.extract_apk(self.artifact("0" * 64), destination)
        self.assertEqual(existing.read_bytes(), b"previous apk")
        self.assertFalse(list(destination.glob("*.part")))

    def test_redirect_does_not_leak_auth(self):
        redirect = core.SafeRedirect()
        request = urllib.request.Request("https://api.github.com/file", headers={"Authorization": "Bearer SECRET"})
        other = redirect.redirect_request(request, None, 302, "Found", {}, "https://blob.example/file")
        same = redirect.redirect_request(request, None, 302, "Found", {}, "https://api.github.com/other")
        self.assertIsNone(other.get_header("Authorization"))
        self.assertEqual(same.get_header("Authorization"), "Bearer SECRET")

    def test_repository_api_has_no_trailing_slash(self):
        from unittest.mock import Mock
        client = core.GitHub.__new__(core.GitHub)
        client.token = "test-token"
        client.opener = Mock()
        client.open("")
        request = client.opener.open.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://api.github.com/repos/" + core.REPOSITORY + "?"))

    def test_monitor_downloads_matching_build(self):
        from unittest.mock import Mock
        payload = self.artifact(hashlib.sha256(b"apk bytes").hexdigest()).read_bytes()
        client = Mock()
        run = {"id": 123, "head_sha": "abc", "html_url": "https://github.com/example/run/123",
               "status": "completed", "conclusion": "success"}
        client.get.side_effect = [{"workflow_runs": [dict(run, head_sha="other"), run]},
                                 {"artifacts": [{"id": 7, "name": "Nordeluna-Android-arm64-v1.8", "expired": False}]}]
        client.open.return_value = io.BytesIO(payload)
        settings = {"last_commit": "abc", "downloads": str(self.root / "apks")}
        events = []
        with patch.object(core, "STATE", self.root / "state"), patch.object(core, "SETTINGS", self.root / "state/settings.json"):
            core.monitor(client, settings, self.stop, lambda *args: events.append(args))
        self.assertEqual(Path(settings["last_apk"]).read_bytes(), b"apk bytes")
        self.assertEqual(settings["last_run_id"], 123)
        self.assertTrue(any(kind == "apk" for kind, _ in events))

    def test_monitor_reports_failed_step(self):
        from unittest.mock import Mock
        client = Mock()
        client.get.side_effect = [{"workflow_runs": [{"id": 123, "head_sha": "abc", "html_url": "https://example.com/run",
                                  "status": "completed", "conclusion": "failure"}]},
                                 {"jobs": [{"steps": [{"name": "Compile Android", "conclusion": "failure"}]}]}]
        with patch.object(core, "save_settings"):
            with self.assertRaisesRegex(core.UpdateError, "Compile Android"):
                core.monitor(client, {"last_commit": "abc"}, self.stop, self.notify)

    @unittest.skipUnless(sys.platform == "win32", "Windows file locking")
    def test_lock_blocks_second_publisher(self):
        with patch.object(core, "STATE", self.root / "state"):
            with core.exclusive_lock():
                with self.assertRaises(core.UpdateError):
                    with core.exclusive_lock():
                        pass

    @unittest.skipUnless(sys.platform == "win32", "Windows publisher")
    def test_push_failure_can_resume_and_commit_failure_restores(self):
        repo = self.root / "repo"
        assets = repo / "game-assets"
        assets.mkdir(parents=True)
        patch_path = repo / "android/nordeluna.patch"
        patch_path.parent.mkdir()
        patch_path.write_text("+        versionCode 12\n", encoding="utf-8")
        workflow = repo / ".github/workflows" / core.WORKFLOW
        workflow.parent.mkdir(parents=True)
        workflow.write_text("env:\n  GAME_ARCHIVE_SHA256: " + "a" * 64 + "\n", encoding="utf-8")
        (assets / "sha256.txt").write_text("previous hash", encoding="utf-8")
        (assets / "game-assets.zip.part001").write_bytes(b"previous package")
        settings = {"source": str(self.source), "downloads": str(self.root / "apk")}
        state = repo / ".cache/state"
        calls = []
        failure = ["commit"]

        def fake_git(*args):
            calls.append(args)
            if args[0] == failure[0]:
                raise core.UpdateError("simulated failure")
            if args[0] == "branch":
                return "main"
            if args[0] == "remote":
                return "https://github.com/" + core.REPOSITORY + ".git"
            if args[0] == "rev-list":
                return "0"
            if args[0] == "rev-parse":
                return "commit123"
            return ""

        with patch.object(core, "ROOT", repo), patch.object(core, "STATE", state), \
             patch.object(core, "SETTINGS", state / "settings.json"), patch.object(core, "git", side_effect=fake_git), \
             patch.object(core, "GitHub") as github, patch.object(core, "monitor") as monitor:
            github.return_value.get.return_value = {"workflow_runs": []}
            with self.assertRaisesRegex(core.UpdateError, "simulated"):
                core.update(settings, self.stop, self.notify)
            self.assertEqual((assets / "game-assets.zip.part001").read_bytes(), b"previous package")
            self.assertIn("versionCode 12", patch_path.read_text())
            self.assertTrue(any(c[0] == "reset" for c in calls))
            failure[0] = "push"
            with self.assertRaisesRegex(core.UpdateError, "simulated"):
                core.update(settings, self.stop, self.notify)
            saved = json.loads(core.SETTINGS.read_text(encoding="utf-8"))
            self.assertTrue(saved["pending_push"])
            self.assertEqual(saved["last_commit"], "commit123")
            self.assertIn("versionCode 13", patch_path.read_text())
            with self.assertRaisesRegex(core.UpdateError, "envio interrompido"):
                core.update(saved, self.stop, self.notify)
            failure[0] = "nothing"
            core.update(saved, self.stop, self.notify, resume=True)
            self.assertFalse(saved["pending_push"])
            monitor.assert_called_once()
            self.assertIn("versionCode 13", patch_path.read_text())


if __name__ == "__main__":
    unittest.main()
