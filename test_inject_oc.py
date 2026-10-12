import plistlib
import tempfile
import unittest
from pathlib import Path
from inject_oc import prepare, write_candidate

class Tests(unittest.TestCase):
    def test_input_and_acpi_preserved(self):
        original = {'ACPI': {'Add': [{'Path': 'keep.aml'}]}, 'Kernel': {'Add': []}}
        result = prepare(original)
        self.assertEqual(result['ACPI'], original['ACPI'])
        self.assertEqual(original['Kernel']['Add'], [])
        self.assertFalse(result['Kernel']['Add'][0]['Enabled'])

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder)/'input', Path(folder)/'output'
            raw = plistlib.dumps({}, fmt=plistlib.FMT_BINARY)
            source.write_bytes(raw)
            write_candidate(source, out)
            self.assertEqual(source.read_bytes(), raw)
            with self.assertRaises(FileExistsError):
                write_candidate(source, out)
            with self.assertRaises(ValueError):
                write_candidate(source, source)

    def test_existing_disabled_and_order_preserved(self):
        data = {'Kernel': {'Add': [{'BundlePath': 'CoreUltraGraphics.kext', 'Enabled': True},
                                  {'BundlePath': 'Other.kext', 'Enabled': True}]}}
        result = prepare(data)
        self.assertFalse(result['Kernel']['Add'][0]['Enabled'])
        self.assertEqual(result['Kernel']['Add'][1], data['Kernel']['Add'][1])
        self.assertTrue(data['Kernel']['Add'][0]['Enabled'])

    def test_malformed_rejected(self):
        for value in ([], {'Kernel': []}, {'Kernel': {'Add': {}}}):
            with self.assertRaises(ValueError):
                prepare(value)
