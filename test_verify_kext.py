import struct
import unittest
from verify_kext import check_macho


def header(cpu=0x01000007, filetype=11, ncmds=0, size=0):
    return struct.pack('<8I', 0xfeedfacf, cpu, 3, filetype, ncmds, size, 0, 0)


class MachoTests(unittest.TestCase):
    def test_expected_header(self):
        check_macho(header())
        check_macho(header(ncmds=1, size=8) + struct.pack('<2I', 1, 8))

    def test_wrong_architecture_or_type(self):
        for raw in (header(cpu=0x0100000c), header(filetype=2), b'short'):
            with self.assertRaises(ValueError):
                check_macho(raw)

    def test_truncated_and_inconsistent_commands(self):
        for raw in (header(ncmds=1, size=8), header(ncmds=1, size=8) + struct.pack('<2I', 1, 16),
                    header(ncmds=0, size=8) + bytes(8)):
            with self.assertRaises(ValueError):
                check_macho(raw)
