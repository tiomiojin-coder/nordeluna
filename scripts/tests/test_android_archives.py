"""Regression checks for renamed game assets and Android archive validation."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_archive", SCRIPTS / "prepare-android-archive.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class AndroidArchivesTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.game = self.root / "game"
        self.game.mkdir()
        for name, content in {
            "Game.ini": b"[Game]\nScripts=Data/Scripts.rxdata\n",
            "Data/Scripts.rxdata": b"compiled scripts fixture",
            "mkxp.json": b"{}",
            "Graphics/Pictures/Laborato (Intro).png": b"updated intro",
            "Graphics/Tilesets/Nova regi\u00e3o.png": b"new tileset",
            "Audio/BGM/Novo tema.ogg": b"new music",
        }.items():
            path = self.game / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.config = self.root / "android.json"
        self.config.write_text(json.dumps({"fullscreen": True}), encoding="utf-8")

    def pack(self):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "pack-android-directory.py"), str(self.game), str(self.root / "packed.zip")],
            capture_output=True, text=True,
        )

    def original(self):
        archive = self.root / "original.zip"
        with zipfile.ZipFile(archive, "w") as zip:
            for path in self.game.rglob("*"):
                if path.is_file():
                    zip.write(path, "./" + path.relative_to(self.game).as_posix())
        return archive

    def test_pack_accepts_new_graphics_and_music(self):
        result = self.pack()
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(self.root / "packed.zip") as zip:
            self.assertEqual(zip.read("Graphics/Pictures/Laborato (Intro).png"), b"updated intro")
            self.assertTrue(zip.getinfo("Graphics/Tilesets/Nova regi\u00e3o.png").flag_bits & 0x800)

    def test_prepare_accepts_renamed_assets_and_replaces_config(self):
        output = self.root / "prepared.zip"
        prepare.prepare_archive(self.original(), output, self.config)
        with zipfile.ZipFile(output) as zip:
            self.assertEqual(json.loads(zip.read("mkxp.json")), {"fullscreen": True})
            self.assertEqual(zip.read("Graphics/Pictures/Laborato (Intro).png"), b"updated intro")
            self.assertTrue(zip.getinfo("Graphics/Tilesets/Nova regi\u00e3o.png").flag_bits & 0x800)

    def test_pack_rejects_unconverted_midi(self):
        (self.game / "Audio/BGM/New.mid").write_bytes(b"midi fixture")
        self.assertIn("unconverted MIDI", self.pack().stderr)

    def test_pack_rejects_missing_scripts(self):
        (self.game / "Data/Scripts.rxdata").unlink()
        self.assertIn("Data/Scripts.rxdata", self.pack().stderr)

    def test_prepare_rejects_missing_scripts(self):
        (self.game / "Data/Scripts.rxdata").unlink()
        with self.assertRaisesRegex(ValueError, "Data/Scripts.rxdata"):
            prepare.prepare_archive(self.original(), self.root / "bad.zip", self.config)

    def test_prepare_rejects_unsafe_paths(self):
        archive = self.original()
        with zipfile.ZipFile(archive, "a") as zip:
            zip.writestr("../outside.png", b"unsafe")
        with self.assertRaisesRegex(ValueError, "unsafe path"):
            prepare.prepare_archive(archive, self.root / "bad.zip", self.config)


if __name__ == "__main__":
    unittest.main()
