import struct
import unittest
from acpi_table_check import check_table


class TableTests(unittest.TestCase):
    def test_checksum_corruption_and_length(self):
        raw = bytearray(40)
        raw[:4] = b'DSDT'
        struct.pack_into('<I', raw, 4, len(raw))
        raw[9] = (-sum(raw)) & 255
        self.assertTrue(check_table(raw)['checksum_valid'])
        raw[-1] ^= 1
        self.assertFalse(check_table(raw)['checksum_valid'])
        self.assertFalse(check_table(raw[:-1])['length_valid'])

    def test_facs_has_no_standard_checksum(self):
        raw = bytearray(64)
        raw[:4] = b'FACS'
        struct.pack_into('<I', raw, 4, 64)
        self.assertIsNone(check_table(raw)['checksum_valid'])

    def test_short_header_rejected(self):
        with self.assertRaises(ValueError):
            check_table(b'DSDT')
