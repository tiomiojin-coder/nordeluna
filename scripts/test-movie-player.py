"""Exercise real Android player state/layout methods with media/view doubles."""
import importlib.util
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("touch_method", ROOT / "scripts/test-touch-controls.py")
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


def main():
    source = (ROOT / "android/AndroidMovieBridge.java").read_text(encoding="utf-8")
    harness = (ROOT / "scripts/fixtures/MoviePlayerLogicTest.java").read_text(encoding="utf-8")
    names = ["private boolean canPlay()", "private void fitVideo()", "private void resetHold()",
             "private void updatePlaybackState()", "private void updatePlayer()", "private void finish("]
    harness = harness.replace("// ACTUAL_METHODS", "\n".join(extract.method(source, name) for name in names))
    with tempfile.TemporaryDirectory(prefix="nordeluna-player-") as folder:
        java = Path(folder) / "MoviePlayerLogicTest.java"
        java.write_text(harness, encoding="utf-8")
        subprocess.run(["javac", "--release", "11", "-encoding", "UTF-8", "-d", folder, str(java)], check=True, timeout=30)
        subprocess.run(["java", "-cp", folder, "MoviePlayerLogicTest"], check=True, timeout=15)


if __name__ == "__main__":
    main()
