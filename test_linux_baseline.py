import json
import tempfile
import unittest
from pathlib import Path
from linux_baseline import collect


def fixture(root, name, vendor='0x8086', device='0x7d45', pci_class='0x030000'):
    folder = root / name
    folder.mkdir()
    for field, value in {'vendor': vendor, 'device': device,
                         'class': pci_class, 'revision': '0x08'}.items():
        (folder / field).write_text(value, encoding='ascii')
    # Sensitive/raw files must never be read or exported.
    (folder / 'config').write_text('SECRET')
    (folder / 'serial').write_text('SECRET')
    return folder


class BaselineTests(unittest.TestCase):
    def test_filters_identifies_and_omits_private_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root, 'private-name')
            fixture(root, 'storage', pci_class='0x010802')
            result = collect(root)
            self.assertEqual(len(result['display_devices']), 1)
            self.assertTrue(result['display_devices'][0]['configured_probe_match'])
            self.assertNotIn('SECRET', json.dumps(result))
            self.assertNotIn('private-name', json.dumps(result))

    def test_different_gpu_not_marked_matching(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root, 'gpu', device='0x7d55')
            self.assertFalse(collect(root)['display_devices'][0]['configured_probe_match'])

    def test_bad_metadata_explicit_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root, 'gpu', vendor='0x10000')
            result = collect(root)
            self.assertEqual(result['display_devices'], [])
            self.assertEqual(len(result['errors']), 1)

    def test_missing_root(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                collect(Path(temp) / 'absent')
