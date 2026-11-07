import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("android_movies", ROOT / "scripts/prepare-android-movies.py")
movies = importlib.util.module_from_spec(spec)
spec.loader.exec_module(movies)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class AndroidMoviesTest(unittest.TestCase):
    def test_real_1932px_movie_and_no_audio_movie(self):
        with tempfile.TemporaryDirectory(prefix="nordeluna-media-") as folder:
            game = Path(folder)
            (game / "Movies").mkdir()
            widescreen = game / "Movies/cena a\u00e7\u00e3o.mp4"
            silent = game / "Movies/silent.MP4"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "color=blue:size=1932x1080:rate=60", "-f", "lavfi", "-i", "sine=frequency=440",
                            "-t", "0.3", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(widescreen)], check=True, timeout=30)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "color=red:size=320x240:rate=30", "-t", "0.2", "-c:v", "libx264", str(silent)], check=True, timeout=30)
            self.assertEqual(movies.prepare_movies(game), 2)
            for path in [widescreen, silent]:
                result = subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)])
                streams = json.loads(result)["streams"]
                video = next(s for s in streams if s["codec_type"] == "video")
                self.assertEqual(video["codec_name"], "h264")
                self.assertEqual(video["pix_fmt"], "yuv420p")
                self.assertLessEqual(video["width"], 1280)
                self.assertLessEqual(video["height"], 720)
                self.assertLessEqual(video["level"], 31)
                self.assertEqual(video["avg_frame_rate"], "30/1")
                if path == widescreen:
                    self.assertEqual(next(s for s in streams if s["codec_type"] == "audio")["codec_name"], "aac")
                else:
                    self.assertEqual((video["width"], video["height"]), (320, 240))
            self.assertFalse(list((game / "Movies").glob("*.android-tmp.mp4")))
