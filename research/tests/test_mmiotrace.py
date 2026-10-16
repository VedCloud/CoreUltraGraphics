import unittest
from mmiotrace_guc import analyze


class TraceTests(unittest.TestCase):
    def test_observed_self_configuration_and_success_response(self):
        lines = ['PCIDEV 0010 80867d45 a0 0x1000000c\n',
                 'W 4 1.0 1 0x10190240 0x508\n',
                 'W 4 1.1 1 0x10190244 0x09060002\n',
                 'W 4 1.2 1 0x10190248 0xa0f800\n',
                 'W 4 1.3 1 0x1019024c 0\n',
                 'W 4 1.4 1 0x101901f0 1\n',
                 'R 4 1.5 1 0x10190240 0x508\n',
                 'R 4 1.6 1 0x10190240 0xf0000001\n']
        result = analyze(lines)
        tx = result['transactions'][0]
        self.assertTrue(tx['complete_observed_request'])
        self.assertEqual(tx['self_config']['name'], 'g2h-descriptor-address')
        self.assertEqual(tx['self_config']['value'], 0xa0f800)
        self.assertEqual(tx['response_header']['type_name'], 'success')

    def test_missing_write_does_not_invent_complete_request(self):
        lines = ['PCIDEV 0010 80867d45 a0 0x1000000c\n',
                 'W 4 1.0 1 0x10190240 0x508\n',
                 'W 4 1.1 1 0x101901f0 1\n']
        tx = analyze(lines)['transactions'][0]
        self.assertFalse(tx['complete_observed_request'])
        self.assertNotIn('self_config', tx)

    def test_media_channel_and_no_duplicate_on_ct_notify(self):
        lines = ['PCIDEV 0010 80867d45 a0 0x1000000c\n',
                 'W 4 1.0 1 0x10190310 0x4509\n',
                 'W 4 1.1 1 0x10190314 1\n',
                 'W 4 1.2 1 0x10190304 1\n',
                 'R 4 1.3 1 0x10190310 0xf0000000\n',
                 'W 4 1.4 1 0x10190304 1\n']
        tx = analyze(lines)['transactions']
        self.assertEqual(len(tx), 1)
        self.assertEqual(tx[0]['channel'], 'media')
        self.assertEqual(tx[0]['control'], 1)

    def test_missing_device_does_not_claim_trace_association(self):
        result = analyze(['W 4 1.0 1 0x10190240 0x508\n'])
        self.assertFalse(result['matching_device_header_found'])
        self.assertEqual(result['transactions'], [])
