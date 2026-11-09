import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('repair_index',ROOT/'scripts/repair-index-tools.py');repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)


class RepairIndexTests(unittest.TestCase):
    def test_ranges_extract_exact_files_with_unicode_and_stored_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'game.zip'
            values={'Game.exe':b'engine'*200,'Graphics/Tilesets/Árvore.png':bytes(range(256))*30,'mkxp.json':b'{}','Saves/Save_1.rxdata':b'private'}
            with zipfile.ZipFile(path,'w') as archive:
                for i,(name,body) in enumerate(values.items()):archive.writestr(name,body,compress_type=zipfile.ZIP_DEFLATED if i%2 else zipfile.ZIP_STORED)
            data=repair.build_index(path);raw=path.read_bytes()
            self.assertEqual(len(data['files']),3)
            for row in data['files']:
                chunk=raw[row['offset']:row['offset']+row['packed_size']]
                body=zlib.decompress(chunk,-15) if row['method']==8 else chunk
                self.assertEqual(body,values[row['path']]);self.assertEqual(hashlib.sha256(body).hexdigest(),row['sha256'])
            self.assertTrue(next(r for r in data['files'] if r['path']=='mkxp.json')['mutable'])
    def test_saves_and_traversal_are_never_repair_targets(self):
        for path in ['../Game.exe','Data/../Save_1.rxdata','Saves/Save_1.rxdata','Plugins/Saves/Save_1.rxdata','Game.rxdata','Data/Save_1.rxdata','C:/secret','.env']:
            self.assertFalse(repair.repair_path(path),path)
