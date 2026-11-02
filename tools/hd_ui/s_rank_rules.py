"""Read-only extraction of battle rank rules from the original PSI2 scripts.

VM banks/operations verified against 8C08BC96 and handlers at 8C08FF6C.
Offsets refer to the unmodified scenario; runtime uses the group number, not
text offsets, so translated/repacked scripts remain compatible.
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import psi2


def expression(p, pos):
    tokens = []
    while True:
        tag = struct.unpack_from('<H', p, pos)[0]; pos += 2
        if not tag:
            return tokens, pos
        if tag == 1:
            pos = (pos + 3) & ~3
            tokens.append(('int', struct.unpack_from('<i', p, pos)[0])); pos += 4
        elif tag in (2, 3, 4):
            tokens.append((f'v{tag}', struct.unpack_from('<H', p, pos)[0])); pos += 2
        elif tag >= 0x80:
            tokens.append(('op', tag))
        else:
            raise ValueError(f'Unknown expression tag {tag:x}')


def statements(p):
    result = []
    for off in sorted(psi2.walk(p).boundaries):
        op = struct.unpack_from('<H', p, off)[0]; pos = off + 2
        mode = 0
        if op in psi2.MODE_TABLES:
            mode = op; op = struct.unpack_from('<H', p, pos)[0]; pos += 2
            sig = psi2.ST_SIGS[op + 0x30] if mode == 8 else psi2.MODE_TABLES[mode][op]
        else:
            sig = psi2.ST_SIGS[op]
        args = []
        for atom in sig:
            if atom == 'e':
                arg, pos = expression(p, pos); args.append(arg)
            elif atom == 'w':
                args.append(struct.unpack_from('<H', p, pos)[0]); pos += 2
            elif atom in ('T', 'U'):
                pos = (pos + 3) & ~3
                args.append(struct.unpack_from('<I', p, pos)[0]); pos += 4
            elif atom == 't':
                count = struct.unpack_from('<H', p, pos)[0]
                args.append(f'text[{count}]'); pos += 2 + count * 2
        result.append(dict(offset=off, mode=mode, op=op, args=args))
    return result


def catalog(data=None):
    rows = []
    if data is None:
        data = (ROOT / 'extracted/SCENARIO.DAT').read_bytes()
    for group, _, p in psi2.groups(data):
        ss = statements(p)
        if not any(s['mode'] == 11 and s['op'] == 16 for s in ss):
            continue
        row = dict(group=group, limits={}, special_writes=[], rank_writes=[])
        for i, s in enumerate(ss):
            if s['mode'] == 11 and s['op'] == 16 and s['args'] in ([[('int', 1)]], [[('int', 2)]]):
                following = ss[i + 1]
                args = following['args']
                if following['mode'] == 0 and following['op'] == 2 and len(args[1]) == 3:
                    lhs, rhs, op = args[1]
                    if lhs == ('v2', 0x146) and rhs[0] == 'int' and op == ('op', 0x93):
                        row['limits']['turn' if s['args'][0][0][1] == 1 else 'ct'] = rhs[1]
            if s['mode'] == 0 and s['op'] == 1 and s['args'][0] == 3 and 0x32 <= s['args'][1] <= 0x3C:
                row['rank_writes'].append(s)
                if s['args'][1] in (0x35, 0x3B, 0x3C) and s['args'][2] != [('int', 0)]:
                    row['special_writes'].append(s)
        rows.append(row)
    return rows


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'dump':
        wanted = int(sys.argv[2])
        p = next(p for i, _, p in psi2.groups((ROOT / 'extracted/SCENARIO.DAT').read_bytes()) if i == wanted)
        for s in statements(p):
            print(f"{s['offset']:04x} {s['mode']:x}:{s['op']:02x}", s['args'])
    else:
        print(json.dumps(catalog(), indent=2))
