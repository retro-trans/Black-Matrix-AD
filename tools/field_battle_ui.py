"""Patch fixed-stride field/battle menus and the deployment help record.

Keep counts, row strides, pointers, and archive sizes unchanged. Sources and
glossary-aware English are in script/ui/field_battle.tsv. Speaker: System.
"""
import struct
from pathlib import Path

import cooking
import patchline
import uistr

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'script/ui/field_battle.tsv'
BATTLE_HELP_UI = ROOT / 'script/ui/battle_help.tsv'
STANCE_HELP = {
    0x7AC2A: 'stance_overview', 0x7AC9E: 'stance_enemy_turn',
    0x7AD12: 'stance_guard', 0x7AD86: 'stance_counter',
    0x7ADFA: 'stance_evade', 0x7AE6E: 'stance_evade_fail',
    0x7AEE2: 'stance_confirm',
}
BATTLE_HELP = {
    **STANCE_HELP,
    0x7A2A6: 'attack_types', 0x7A31A: 'normal_attack',
    0x7A38E: 'latent_attack', 0x7A402: 'attack_range',
    0x7A476: 'attack_target', 0x7A72E: 'item_actions',
    0x7A7A2: 'item_limit', 0x7A816: 'item_details',
    0x7A88A: 'item_use_range', 0x7A8FE: 'item_use_target',
    0x7A972: 'item_discard_limit', 0x7A9E6: 'item_discard_confirm',
    0x7C01A: 'status_overview', 0x7C08E: 'status_unlimited',
    0x7C102: 'status_after_attack', 0x7C176: 'status_equipment',
    0x7C1EA: 'status_unarmed', 0x7C25E: 'status_magic',
    0x7AA5A: 'bp_refill_cost', 0x7AACE: 'bp_refill_before',
    0x7AB42: 'bp_refill_cap', 0x7ABB6: 'bp_refill_amount',
}
ITEM_UI = ROOT / 'script/ui/status_items.tsv'
ITEM_NAMES = {
    0x65392: ('stick_name', '木の棒'),
    0x654B2: ('stick_name', '木の棒'),
    0x713F2: ('prison_clothes', '囚人服'),
}
ITEM_DESCRIPTIONS = {0x653A8: 'stick_description',
                     0x654C8: 'stick_description',
                     0x7141E: 'clothes_description'}
FIELD = ('status', 'ritual', 'items', 'shop', 'abilities', 'system', 'exit')
BATTLE = ('move', 'attack', 'magic', 'item_battle', 'status_battle',
          'refill', 'stance', 'armor')
STANCES = ('guard', 'evade', 'counter')
HELP_OFFSET = 0x7A062


def record(data, offset, rows, width):
    """Replace only a known fixed-size record's character words."""
    count = struct.unpack_from('<H', data, offset - 2)[0]
    if count != len(rows) * width:
        raise ValueError('unexpected UI record size at 0x%X' % offset)
    if any(len(row) > width for row in rows):
        raise ValueError('translated UI row exceeds its fixed slot')
    text = ''.join(row.ljust(width) for row in rows)
    words = [patchline.to_sjis(c) for c in text]
    data[offset:offset + count * 2] = struct.pack('<%dH' % count, *words)


def patch_executable(data):
    text = cooking.strings(UI)
    record(data, 0x88B28, [text[k] for k in FIELD], 4)
    record(data, 0x8981A, [text[k] for k in FIELD[:-1]] + [text['deploy']], 4)
    record(data, 0x87FA6, [text[k] for k in BATTLE], 3)
    record(data, 0x87FD8, [text[k] for k in STANCES], 3)
    record(data, 0x8A054, [text['refill_heading']], 2)
    # The same commands also appear as independent three-cell records.
    for i, key in enumerate(BATTLE):
        record(data, 0x8823A + 8*i, [text[key]], 3)


def patch_parameters(data):
    text = cooking.strings(UI)
    record(data, HELP_OFFSET, text['position_help'].split('\\n'), 19)
    help_text = cooking.strings(BATTLE_HELP_UI)
    for offset, key in BATTLE_HELP.items():
        record(data, offset, help_text[key].split('\\n'), 19)
    item_text = cooking.strings(ITEM_UI)
    for offset, (key, japanese) in ITEM_NAMES.items():
        name = item_text[key]
        current = next(uistr.walk(data, offset-2, 1), None)
        if current is None or current[2] != japanese or current[1] > 8:
            raise ValueError('unexpected original item name at 0x%X' % offset)
        tail = struct.unpack_from('<%dH' % (8-current[1]), data, offset+2*current[1])
        if any(w != patchline.SPACE for w in tail) or len(name) > 8:
            raise ValueError('item name exceeds its reserved eight slots')
        # The count is independent of the fixed struct stride. Only consume
        # its verified padding; the following item flags/stats stay in place.
        struct.pack_into('<H', data, offset-2, len(name))
        struct.pack_into('<8H', data, offset,
                         *(patchline.to_sjis(c) for c in name.ljust(8)))
    for offset, key in ITEM_DESCRIPTIONS.items():
        record(data, offset, item_text[key].split('\\n'), 19)


def install():
    exe = ROOT / 'build/1ST_READ.vwf.bin'
    data = bytearray(exe.read_bytes())
    patch_executable(data)
    exe.write_bytes(data)
    data = bytearray((ROOT / 'extracted/PARAMETA.DAT').read_bytes())
    patch_parameters(data)
    (ROOT / 'build/PARAMETA.vwf.dat').write_bytes(data)
    print('localized field/battle menus, equipment names, and %d battle help pages'
          % len(BATTLE_HELP))


if __name__ == '__main__':
    install()
