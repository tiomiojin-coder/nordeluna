import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "JDK required")
class OnlineBridgeTest(unittest.TestCase):
    def test_real_http_transport_and_lifecycle(self):
        with tempfile.TemporaryDirectory(prefix="nordeluna-bridge-") as directory:
            classes = Path(directory) / "classes"
            game = Path(directory) / "game"
            classes.mkdir()
            game.mkdir()
            subprocess.run(["javac", "--release", "11", "-encoding", "UTF-8", "-d", str(classes),
                            str(ROOT / "android/OnlineBridge.java"),
                            str(ROOT / "scripts/fixtures/OnlineBridgeTest.java")], check=True, timeout=30)
            result = subprocess.run(["java", "-cp", str(classes), "OnlineBridgeTest", str(game)],
                                    capture_output=True, text=True, timeout=35)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("reconnection passed", result.stdout)
