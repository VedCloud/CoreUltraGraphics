from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import firmware_format as fw
import guc_transport as ct


class FirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = ROOT / 'firmware/38c1a7096dfb'
        cls.guc = (cls.folder / 'mtl_guc_70.bin').read_bytes()
        cls.huc = (cls.folder / 'mtl_huc_gsc.bin').read_bytes()
        cls.gsc = (cls.folder / 'mtl_gsc_1.bin').read_bytes()

    def test_real_guc_header_and_payload_ranges(self):
        result = fw.css(self.guc)
        self.assertEqual(result['release_version'], '70.53.0')
        self.assertEqual(result['submission_version_raw'], '1.26.0')
        self.assertEqual([(r['offset'], r['size']) for r in result['regions']],
                         [(0, 128), (128, 319808), (319936, 384)])
        self.assertEqual(result['required_size'], len(self.guc))

    def test_guc_truncated_optional_modulus_is_accepted(self):
        result = fw.css(self.guc)
        self.assertLess(len(self.guc), result['declared_full_size'])
        self.assertEqual(result['bytes_after_required'], 0)

    def test_guc_required_rsa_truncation_is_rejected(self):
        with self.assertRaises(fw.FormatError):
            fw.css(self.guc[:-1])

    def test_css_size_underflow_and_short_header_rejected(self):
        for offset, value in [(4, 1), (24, 0)]:
            data = bytearray(self.guc)
            struct.pack_into('<I', data, offset, value)
            with self.assertRaises(fw.FormatError):
                fw.css(data)
        with self.assertRaises(fw.FormatError):
            fw.css(b'\0' * 127)

    def test_real_huc_manifest_and_separate_signature_entry(self):
        result = fw.huc(self.huc)
        by_name = {e['name']: e for e in result['entries']}
        self.assertEqual(by_name['HUCP.man']['manifest']['version'], '8.5.4.1555')
        self.assertTrue(result['embedded_css']['rsa_matches_guc_sig_entry'])
        self.assertEqual(result['embedded_css']['release_version'], '8.5.4')

    def test_directory_count_and_entry_offset_rejected(self):
        for offset, value in [(4, 0xFFFFFFFF), (20 + 12, 0x1FFFFFF)]:
            data = bytearray(self.huc)
            struct.pack_into('<I', data, offset, value)
            with self.assertRaises(fw.FormatError):
                fw.huc(data)

    def test_real_gsc_manifest(self):
        result = fw.gsc(self.gsc)
        cpd = next(e['cpd'] for e in result['entries'] if 'cpd' in e)
        manifest = next(e['manifest'] for e in cpd['entries'] if e['name'] == 'RBEP.man')
        self.assertEqual(manifest['version'], '102.1.15.1926')
        self.assertEqual(manifest['security_version'], 1)

    def test_gsc_out_of_bounds_boot_partition_rejected(self):
        data = bytearray(self.gsc)
        struct.pack_into('<I', data, 32, 0xFFFFFFF0)
        with self.assertRaises(fw.FormatError):
            fw.gsc(data)


class TransportTests(unittest.TestCase):
    def test_known_ctb_request_bytes(self):
        packet = ct.frame(0x1234, ct.request(0x4502, [0xDEADBEEF]))
        self.assertEqual(packet.hex(), '0200341202450000efbeadde')
        self.assertEqual(ct.decode(packet), {'fence': 0x1234, 'hxg_dwords': 2,
            'origin': 'host', 'type': 0, 'type_name': 'request', 'aux': 0x4502,
            'payload': [0xDEADBEEF], 'action': 0x4502, 'data0': 0})

    def test_response_does_not_invent_action(self):
        result = ct.decode(ct.frame(1, [0xF0000010]))
        self.assertEqual(result['origin'], 'guc')
        self.assertEqual(result['type_name'], 'success')
        self.assertNotIn('action', result)

    def test_malformed_packet_lengths_format_and_reserved(self):
        for words in [(0x00001001, 0), (0x00000101, 0), (2, 0), (0, 0)]:
            with self.assertRaises(ValueError):
                ct.decode(struct.pack('<2I', *words))
        for data in [b'', b'\0' * 4, b'\0' * 9]:
            with self.assertRaises(ValueError):
                ct.decode(data)

    def test_field_overflow_and_maximum_packet(self):
        for make in [lambda: ct.frame(1 << 16, [0]), lambda: ct.frame(0, []),
                     lambda: ct.frame(0, [0] * 256), lambda: ct.request(1 << 16),
                     lambda: ct.request(1, data0=1 << 12), lambda: ct.request(1, [-1])]:
            with self.assertRaises(ValueError):
                make()
        self.assertEqual(len(ct.frame(65535, [0] * 255)), 1024)
