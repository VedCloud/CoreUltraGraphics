"""Validate raw ACPI table lengths/checksums without executing AML."""
import struct


def check_table(data):
    if len(data) < 8:
        raise ValueError('truncated ACPI header')
    signature = data[:4].decode('ascii')
    if not all(32 <= ord(c) < 127 for c in signature):
        raise ValueError('invalid ACPI signature')
    declared = struct.unpack_from('<I', data, 4)[0]
    if signature == 'FACS':
        return {'signature': signature, 'length_valid': declared == len(data) and len(data) >= 64,
                'checksum_valid': None}
    return {'signature': signature, 'length_valid': declared == len(data) and len(data) >= 36,
            'checksum_valid': sum(data) % 256 == 0 if len(data) >= 36 else False}
