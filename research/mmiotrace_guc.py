"""Observe known GuC MMIO setup messages in an offline mmiotrace stream.

Offsets and keys follow the pinned public Xe ABI. The trace itself may come
from i915. Observed request/response association is temporal, not proof that
an incomplete trace includes every operation. No trace replay is implemented.
"""
from collections import Counter
from guc_transport import decode_hxg

CHANNELS = {'render': (0x190240, 0x1901F0), 'media': (0x190310, 0x190304)}
KEYS = {0x902: 'h2g-buffer-address', 0x903: 'h2g-descriptor-address',
        0x904: 'h2g-buffer-size', 0x905: 'g2h-buffer-address',
        0x906: 'g2h-descriptor-address', 0x907: 'g2h-buffer-size'}


def analyze(lines):
    bar0 = None
    transactions = []
    counts = Counter()
    stage = {name: {} for name in CHANNELS}
    waiting = {name: None for name in CHANNELS}
    total = 0
    for total, line in enumerate(lines, 1):
        parts = line.split()
        if parts[:1] == ['PCIDEV'] and len(parts) >= 5 and parts[2].lower() == '80867d45':
            bar0 = int(parts[4], 16) & ~0xF
            continue
        if bar0 is None or len(parts) < 6 or parts[0] not in ('R', 'W'):
            continue
        op, width, stamp, mapping, addr, value = parts[:6]
        if width != '4':
            continue
        offset, word = int(addr, 16) - bar0, int(value, 16)
        for channel, (scratch, trigger) in CHANNELS.items():
            if scratch <= offset < scratch + 16 and (offset - scratch) % 4 == 0:
                index = (offset - scratch) // 4
                counts[(channel, op, f'scratch-{index}')]+=1
                if op == 'W':
                    if index == 0:
                        stage[channel] = {}
                        waiting[channel] = None
                    stage[channel][index] = {'word': word, 'line': total}
                elif index == 0 and word & (1 << 31) and waiting[channel] is not None:
                    record = transactions[waiting[channel]]
                    if 'response_header' not in record:
                        record['response_header'] = decode_hxg([word])
                        record['response_line'] = total
                        record['response_timestamp'] = stamp
            elif offset == trigger and op == 'W':
                counts[(channel, op, 'notify')]+=1
                staged = stage[channel]
                if 0 not in staged:
                    continue
                first = staged[0]['word']
                action = first & 0xFFFF
                # Decode only explicitly supported setup actions with known lengths.
                required = {0x0508: 4, 0x4509: 2}.get(action)
                if required is None or first >> 28 != 0:
                    stage[channel] = {}
                    continue
                words = [staged[i]['word'] for i in range(required) if i in staged]
                record = {'channel': channel, 'action': f'0x{action:04x}',
                          'first_write_line': staged[0]['line'], 'notify_line': total,
                          'notify_timestamp': stamp, 'observed_words': words,
                          'required_dwords': required, 'complete_observed_request': len(words) == required}
                if len(words) == required:
                    record['request'] = decode_hxg(words)
                    if action == 0x0508:
                        key, length = words[1] >> 16, words[1] & 0xFFFF
                        record['self_config'] = {'key': f'0x{key:04x}',
                            'name': KEYS.get(key, 'other-self-configuration'), 'length_dwords': length}
                        if length in (1, 2):
                            record['self_config']['value'] = words[2] | (words[3] << 32 if length == 2 else 0)
                    else:
                        record['control'] = words[1]
                transactions.append(record)
                waiting[channel] = len(transactions) - 1
                stage[channel] = {}
    return {'lines_examined': total, 'matching_device_header_found': bar0 is not None,
            'transactions': transactions,
            'register_counts': [{'channel': ch, 'op': op, 'register': reg, 'count': n}
                                for (ch, op, reg), n in sorted(counts.items())],
            'limitations': ['No shared-memory CTB contents are recorded by this MMIO decoder',
                            'Response association follows observed channel ordering; lost events can break it',
                            'Only SELF_CFG (4 dwords) and CONTROL_CTB (2 dwords) are decoded',
                            'No physical addresses or sequences are suitable for direct replay']}
