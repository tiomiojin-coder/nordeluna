import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('client_releases',ROOT/'scripts/client-release-tools.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)


class ClientReleaseTests(unittest.TestCase):
    def row(self):return dict(url='https://example.com/nordeluna.apk',version='1.14.0',code=21,size=123,sha256='a'*64,notes='Novidades',compatibility='same-build')
    def test_valid_cross_platform_catalog(self):
        data=dict(schema=1,channels=dict(stable=dict(android=self.row(),windows=self.row())))
        self.assertEqual(release.validate(data),data)
    def test_rejects_insecure_url_embedded_credentials_and_invalid_size(self):
        for fields in [dict(url='http://example.com/a'),dict(url='https://user:pass@example.com/a'),dict(code=True),dict(size=-1),dict(sha256='z'*64)]:
            row=self.row();row.update(fields)
            with self.assertRaises(ValueError):release.validate(dict(schema=1,channels=dict(stable=dict(android=row))))
    def test_channels_are_explicit(self):
        with self.assertRaises(ValueError):release.validate(dict(schema=1,channels={'staff':dict(android=self.row())}))
