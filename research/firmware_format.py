"""Offline MTL CSS/CPD/BPDT parsing from Linux xe_uc_fw_abi.h.

This describes file structure, not instruction decoding, RSA verification,
firmware execution, or a hardware-loadable macOS driver.
"""
import hashlib
import struct


class FormatError(ValueError):
    pass


def checked(data, offset, size):
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise FormatError(f'Out-of-bounds range offset={offset} size={size} file={len(data)}')
    return data[offset:offset + size]


def region(data, name, offset, size):
    payload = checked(data, offset, size)
    return {'name': name, 'offset': offset, 'size': size,
            'sha256': hashlib.sha256(payload).hexdigest()}


def css(data, offset=0):
    fields = struct.unpack('<32I', checked(data, offset, 128))
    total, header, key, modulus, exponent = fields[6], fields[1], fields[7], fields[8], fields[9]
    if header < key + modulus + exponent or header - key - modulus - exponent != 32:
        raise FormatError('CSS non-payload header does not resolve to 128 bytes')
    if total < header:
        raise FormatError('CSS total size smaller than header')
    code_size = (total - header) * 4
    rsa_size = key * 4
    checked(data, offset, 128 + code_size + rsa_size)
    version = lambda v: f'{(v >> 16) & 255}.{(v >> 8) & 255}.{v & 255}'
    regions = [region(data, 'css-header', offset, 128),
               region(data, 'ucode', offset + 128, code_size),
               region(data, 'rsa', offset + 128 + code_size, rsa_size)]
    required = 128 + code_size + rsa_size
    return {'format': 'CSS', 'offset': offset, 'module_type': fields[0],
            'module_vendor': f'0x{fields[4]:08x}', 'header_version': fields[2],
            'release_version': version(fields[16]), 'submission_version_raw': version(fields[17]),
            'private_data_size_raw': fields[30], 'declared_full_size': total * 4,
            'declared_modulus_bytes': modulus * 4, 'declared_exponent_bytes': exponent * 4,
            'required_size': required, 'bytes_after_required': len(data) - offset - required,
            'regions': regions,
            'signature_status': 'RSA bytes located; cryptographic validity not checked',
            'instruction_architecture': 'not established by CSS layout'}


def manifest(data, offset, available_size):
    header = checked(data, offset, 128)
    words = struct.unpack_from('<9I', header)
    if words[0] != 4:
        raise FormatError(f'Unexpected manifest type {words[0]}')
    header_bytes, full_bytes = words[1] * 4, words[6] * 4
    if not 128 <= header_bytes <= full_bytes <= available_size:
        raise FormatError('Invalid manifest size relationship')
    checked(data, offset, full_bytes)
    return {'offset': offset, 'header_size': header_bytes, 'manifest_size': full_bytes,
            'version': '.'.join(map(str, struct.unpack_from('<4H', header, 36))),
            'security_version': struct.unpack_from('<I', header, 44)[0],
            'vendor': f'0x{words[4]:08x}', 'header_id_raw': words[7]}


def cpd(data, offset=0, limit=None):
    limit = len(data) - offset if limit is None else limit
    checked(data, offset, limit)
    marker, count, header_ver, entry_ver, hlen, flags, part, crc = struct.unpack(
        '<IIBBBBII', checked(data, offset, 20))
    if marker != 0x44504324 or hlen < 20 or hlen > limit or count > (limit - hlen) // 24:
        raise FormatError('Invalid CPD marker/header/directory length')
    entries = []
    for index in range(count):
        rawname, encoded_offset, length, reserved = struct.unpack(
            '<12sII4s', checked(data, offset + hlen + index * 24, 24))
        name = rawname.split(b'\0', 1)[0].decode('ascii', errors='strict')
        rel = encoded_offset & 0x1FFFFFF
        compressed = bool(encoded_offset & (1 << 25))
        if rel >= limit or (not compressed and length > limit - rel):
            raise FormatError(f'CPD entry outside partition: {name}')
        entry = {'name': name, 'offset': offset + rel, 'partition_offset': rel,
                 'declared_length': length, 'huffman_compressed': compressed,
                 'offset_reserved_bits': encoded_offset >> 26}
        if not compressed:
            entry['region'] = region(data, name, offset + rel, length)
        else:
            entry['range_note'] = 'Length describes uncompressed size; stored range not established'
        if name.endswith('.man'):
            if compressed:
                raise FormatError('Compressed manifest cannot be parsed by this tool')
            entry['manifest'] = manifest(data, offset + rel, length)
        entries.append(entry)
    return {'format': 'CPD', 'offset': offset, 'partition_size': limit,
            'header_version': header_ver, 'entry_version': entry_ver, 'header_size': hlen,
            'partition_name': struct.pack('<I', part).decode('ascii', errors='replace'),
            'crc32_raw': crc, 'crc32_status': 'not checked', 'entries': entries}


def huc(data):
    result = cpd(data)
    by_name = {e['name']: e for e in result['entries']}
    if 'HUCP.man' not in by_name or 'huc_fw' not in by_name:
        raise FormatError('Missing HuC manifest or firmware entry')
    entry = by_name['huc_fw']
    if entry['huffman_compressed']:
        raise FormatError('HuC CSS is compressed; unsupported')
    # The CSS RSA can occupy the separate adjacent guc_sig directory entry.
    # Match Xe's parser: bound to remaining partition, not huc_fw's code length.
    parsed = css(data, entry['offset'])
    parsed['directory_code_length'] = entry['declared_length']
    signature = by_name.get('guc_sig')
    if signature:
        rsa = next(r for r in parsed['regions'] if r['name'] == 'rsa')
        parsed['rsa_matches_guc_sig_entry'] = (rsa['offset'] == signature['offset'] and
                                               rsa['size'] == signature['declared_length'])
    result['embedded_css'] = parsed
    return result


def gsc(data):
    checked(data, 0, 80)
    boot_offset, boot_size = struct.unpack_from('<II', data, 32)
    checked(data, boot_offset, boot_size)
    header = checked(data, boot_offset, 24)
    signature, count, version, configuration, crc, build, *tool_version = struct.unpack('<IHBBII4H', header)
    if signature != 0x55AA or boot_size < 24 or count > (boot_size - 24) // 12:
        raise FormatError('Invalid GSC BPDT header')
    entries = []
    for index in range(count):
        kind, rel, size = struct.unpack('<III', checked(data, boot_offset + 24 + index * 12, 12))
        if rel > boot_size or size > boot_size - rel:
            raise FormatError('BPDT entry outside boot partition')
        entry = {'type': kind, 'offset': boot_offset + rel, 'size': size}
        if kind & 0xFFFF == 1:
            entry['cpd'] = cpd(data, boot_offset + rel, size)
        entries.append(entry)
    if not any('cpd' in e for e in entries):
        raise FormatError('GSC RBE partition not found')
    return {'format': 'GSC-layout/BPDT/CPD', 'boot1_offset': boot_offset,
            'boot1_size': boot_size, 'bpdt_version': version, 'entries': entries,
            'crc32_status': 'not checked', 'signature_status': 'not checked'}
