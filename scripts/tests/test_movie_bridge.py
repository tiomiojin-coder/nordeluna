import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "JDK required")
class MovieBridgeTest(unittest.TestCase):
    def test_player_layout_audio_and_lifecycle(self):
        subprocess.run([sys.executable, str(ROOT / "scripts/test-movie-player.py")], check=True, timeout=40)

    def test_movie_protocol_and_lifecycle(self):
        with tempfile.TemporaryDirectory(prefix="nordeluna-movie-") as folder:
            base = Path(folder)
            classes = base / "classes"
            game = base / "game"
            classes.mkdir(); game.mkdir()
            subprocess.run(["javac", "--release", "11", "-encoding", "UTF-8", "-d", str(classes),
                            str(ROOT / "android/MovieMailbox.java"),
                            str(ROOT / "scripts/fixtures/MovieMailboxTest.java")], check=True, timeout=30)
            result = subprocess.run(["java", "-cp", str(classes), "MovieMailboxTest", str(game)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("late callbacks", result.stdout)
