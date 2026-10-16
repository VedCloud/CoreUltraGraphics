"""Offline GuC CTB/HXG codec from public Linux Xe ABI definitions.

No MMIO, shared-buffer mutation, firmware calls or hardware submission.
"""
import struct

TYPE_NAMES = {0: 'request', 1: 'event', 2: 'fast-request', 3: 'busy',
              5: 'retry', 6: 'failure', 7: 'success'}


def uint(value, bits, name):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError(f'{name} must be unsigned {bits}-bit integer')
    return value


def request(action, parameters=(), data0=0):
    """Construct HXG host request words, without CTB framing."""
    head = uint(action, 16, 'action') | (uint(data0, 12, 'data0') << 16)
    words = [head, *(uint(p, 32, 'parameter') for p in parameters)]
    if len(words) > 255:
        raise ValueError('CTB HXG request exceeds 255 dwords')
    return words


def frame(fence, hxg_words):
    words = [uint(w, 32, 'HXG dword') for w in hxg_words]
    if not 1 <= len(words) <= 255:
        raise ValueError('CTB HXG payload must contain 1..255 dwords')
    header = (uint(fence, 16, 'fence') << 16) | len(words)
    return struct.pack('<' + 'I' * (len(words) + 1), header, *words)


def decode(packet):
    if len(packet) < 8 or len(packet) % 4:
        raise ValueError('Truncated or unaligned CTB HXG message')
    words = struct.unpack('<' + 'I' * (len(packet) // 4), packet)
    header, hxg = words[:2]
    if header & 0xFF00:
        raise ValueError('Unsupported CTB format or nonzero reserved bits')
    if header & 255 != len(words) - 1:
        raise ValueError('CTB declared dword count does not match packet')
    return {'fence': header >> 16, 'hxg_dwords': header & 255, **decode_hxg(words[1:])}


def decode_hxg(words):
    if not words:
        raise ValueError('Empty HXG message')
    words = [uint(w, 32, 'HXG dword') for w in words]
    hxg = words[0]
    kind = (hxg >> 28) & 7
    result = {'origin': 'guc' if hxg >> 31 else 'host',
              'type': kind, 'type_name': TYPE_NAMES.get(kind, 'unknown'),
              'aux': hxg & 0x0FFFFFFF, 'payload': list(words[1:])}
    if kind in (0, 1, 2):
        result.update(action=hxg & 0xFFFF, data0=(hxg >> 16) & 0xFFF)
    return result
