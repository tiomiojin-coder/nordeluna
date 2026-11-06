import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("package_discloud", ROOT / "scripts/package-discloud.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class DiscloudPackageTest(unittest.TestCase):
    def test_zip_boots_without_game_or_private_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = builder.package("nordeluna-online", root / "server.zip")
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(set(archive.namelist()), {"main.py", "relay.py", "discloud.config", "requirements.txt"})
                self.assertIn("ID=nordeluna-online", archive.read("discloud.config").decode())
                archive.extractall(root / "app")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            environment = dict(os.environ, HOST="127.0.0.1", PORT=str(port))
            for attempt in range(2):
                process = subprocess.Popen([sys.executable, str(root / "app/main.py")], env=environment,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                try:
                    deadline = time.monotonic() + 10
                    while True:
                        try:
                            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                                health = json.load(response)
                            break
                        except (urllib.error.URLError, TimeoutError):
                            if time.monotonic() >= deadline or process.poll() is not None:
                                self.fail("Packaged server failed to start")
                            time.sleep(0.05)
                    self.assertEqual(health["protocol"], 1)
                    self.assertEqual(health["revision"], 2)
                    self.assertTrue(health["ok"])
                    self.assertTrue((root / "app/data/relay.sqlite3").is_file())
                finally:
                    process.terminate()
                    process.communicate(timeout=10)

    def test_full_url_is_not_accepted_as_subdomain(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                builder.package("https://example.discloud.app", Path(directory) / "bad.zip")


if __name__ == "__main__":
    unittest.main()
