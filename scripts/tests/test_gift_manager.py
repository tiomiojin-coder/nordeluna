import base64
import importlib.util
import json
from pathlib import Path
import re
import shlex
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('gift_manager',Path(__file__).resolve().parents[1]/'gift-manager.py')
manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(manager)


class GiftManagerTests(unittest.TestCase):
    def test_console_command_encodes_text_instead_of_executing_it(self):
        data=dict(action='create',code='BEMVINDO',title='"; $(whoami) `echo teste`',rewards=[dict(kind='money',amount=100)])
        command=shlex.split(manager.console_command(data))
        self.assertEqual(command[:2],['python','-c'])
        self.assertEqual(len(command),3)
        compile(command[2],'<admin>','exec')
        encoded=re.search(r"b64decode\('([A-Za-z0-9+/=]+)'\)",command[2])[1]
        self.assertEqual(json.loads(base64.b64decode(encoded)),data)
        self.assertNotIn('whoami',command[2])
    def test_local_pbs_catalog_includes_fakemon_and_forms(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory);(game/'PBS').mkdir()
            for file,body in [('pokemon','[NOCTGEIST]\nName = Noctgeist\n'),('items','[POKEBALL]\nName = Poké Ball\n'),('moves','[TACKLE]\nName = Tackle\n'),('pokemon_forms','[NOCTGEIST,1]\n')]:
                (game/'PBS'/f'{file}.txt').write_text(body,encoding='utf-8')
            data=manager.catalog(game)
            self.assertEqual(data['pokemon']['NOCTGEIST'],'Noctgeist')
            self.assertEqual(data['forms']['NOCTGEIST'],{0,1})
            self.assertEqual(data['items']['POKEBALL'],'Poké Ball')
