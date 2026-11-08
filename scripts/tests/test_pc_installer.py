import importlib.util
from pathlib import Path
import unittest
import sys

PATH = Path(__file__).resolve().parents[1] / 'build-pc-installer.py'
sys.path.insert(0, str(PATH.parent))
spec = importlib.util.spec_from_file_location('pc_installer', PATH)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


class PCInstallerTests(unittest.TestCase):
    def test_excludes_private_and_development_files(self):
        for name in ['Plugins/.backups/private.json', 'Saves/Save_1.rxdata',
                     'Screenshots/private.png', 'Plugins/Online/server/.env',
                     'Plugins/tool/helper.py', 'Plugins/transport.log', 'Plugins/data.sqlite']:
            self.assertFalse(pc.distributable(name), name)

    def test_keeps_runtime_and_online_bridge(self):
        for name in ['Game.exe', 'Plugins/Nordeluna Online/bridge/WindowsHttpBridge-2.exe',
                     'Data/PluginScripts.rxdata', 'Graphics/UI/VPM/menu_save.png', 'Fonts/power green.ttf']:
            self.assertTrue(pc.distributable(name), name)

    def test_patch_refuses_unknown_updater(self):
        with self.assertRaises(ValueError):
            pc.pc_update_source('unknown version')

    def test_factory_fallback_preserves_previous_update_priority(self):
        source="    class << self\nold[target] || row['base_sha256']"
        result=pc.pc_update_source(source)
        self.assertIn("old[target] || pc_factory_hash(target) || row['base_sha256']",result)
        self.assertIn("@pc_factory['base']==BASE",result)


if __name__ == '__main__':
    unittest.main()
