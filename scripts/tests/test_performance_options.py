from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'JDK required')
class PerformanceOptionsTests(unittest.TestCase):
    def test_shared_preferences_file(self):
        with tempfile.TemporaryDirectory(prefix='nordeluna-performance-') as temporary:
            directory=Path(temporary);classes=directory/'classes';classes.mkdir()
            game=directory/'game';game.mkdir()
            subprocess.run(['javac','--release','8','-encoding','UTF-8','-d',str(classes),
                            str(ROOT/'android/PerformanceOptions.java'),str(ROOT/'scripts/fixtures/PerformanceOptionsTest.java')],check=True,timeout=30)
            subprocess.run(['java','-cp',str(classes),'PerformanceOptionsTest',str(game)],check=True,timeout=15)
