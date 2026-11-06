"""Downloaded release metadata must match before tests or local mutations."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA'] = tempfile.mkdtemp(prefix='jv_package_')
from core import updater


class UpdatePackageTests(unittest.TestCase):
    def archive(self, metadata):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('repo/run.py', '')
            z.writestr('repo/core/config.py', '')
            if metadata is not None:
                z.writestr('repo/version.json', metadata)
        return buf.getvalue()

    def test_invalid_metadata_never_reaches_tests_or_backup(self):
        for metadata in (None, '{', '[]', '{}', '{"version":"0.0.1"}'):
            with self.subTest(metadata=metadata), \
                 patch.object(updater, 'check', return_value={'yeni_var': True, 'uzak': '99.0.0'}), \
                 patch.object(updater, '_get', return_value=self.archive(metadata)), \
                 patch.object(updater, '_tests') as tests, \
                 patch.object(updater, 'backup') as backup:
                result = updater.apply(restart=False)
                self.assertEqual(result['durum'], 'hata')
                self.assertIn('sürüm', result['hata'])
                tests.assert_not_called()
                backup.assert_not_called()

    def test_matching_metadata_reaches_preflight(self):
        with patch.object(updater, 'check', return_value={'yeni_var': True, 'uzak': '99.0.0'}), \
             patch.object(updater, '_get', return_value=self.archive(json.dumps({'version': '99.0.0'}))), \
             patch.object(updater, '_tests', return_value=(False, 'preflight marker')) as tests, \
             patch.object(updater, 'backup') as backup:
            result = updater.apply(restart=False)
            self.assertIn('preflight marker', result['hata'])
            tests.assert_called_once()
            backup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
