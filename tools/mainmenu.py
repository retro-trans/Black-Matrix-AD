"""Localize both seven-row main menus, with nine cells per English label.

The original four-cell records cannot hold English labels. Relocate only
these two records into the verified zero arena after the VWF float table,
and patch their own constructors' logical and allocated widths. No global
four-column rule: that would change unrelated menus and selectors.
"""
import struct
from pathlib import Path

import cooking
import patchline
import vwf

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'script/ui/main_menu.tsv'
COLS = 9
ROWS = 7
STORAGE = 0x8C0F6800
RECORD_BYTES = 2 + COLS * ROWS * 2
MENUS = (
    (0x88B26, 0x3DC4C, ((0x3DBD4, 0xE004), (0x3DBDA, 0xE304)), 'exit'),
    (0x89818, 0x5D6D8, ((0x5D666, 0xE004), (0x5D670, 0xE304)), 'deploy'),
)


def patch(data):
    text = cooking.strings(UI)
    assert STORAGE >= vwf.FLOAT_TAB + vwf.NTAB * 4
    assert STORAGE + len(MENUS) * RECORD_BYTES <= vwf.ARENA_END
    assert COLS * ROWS <= 100
    for i, (original, pointer, instructions, last) in enumerate(MENUS):
        if struct.unpack_from('<H', data, original)[0] != 28:
            raise ValueError('main-menu original record changed')
        if struct.unpack_from('<I', data, pointer)[0] != vwf.LOAD_BASE + original:
            raise ValueError('main-menu record pointer changed')
        labels = [text[k] for k in ('status','ritual','items','shop','abilities','system',last)]
        if any(len(label) > COLS for label in labels):
            raise ValueError('main-menu glossary label exceeds nine cells')
        words = [patchline.to_sjis(ch) for label in labels for ch in label.ljust(COLS)]
        encoded = struct.pack('<%dH' % (len(words)+1), len(words), *words)
        address = STORAGE + i * RECORD_BYTES
        offset = address - vwf.LOAD_BASE
        if any(data[offset:offset+len(encoded)]):
            raise ValueError('main-menu storage is no longer unused')
        data[offset:offset+len(encoded)] = encoded
        struct.pack_into('<I', data, pointer, address)
        for off, expected in instructions:
            if struct.unpack_from('<H', data, off)[0] != expected:
                raise ValueError('main-menu width instruction changed')
            struct.pack_into('<H', data, off, (expected & 0xFF00) | COLS)
    return data


def install():
    path = ROOT / 'build/1ST_READ.vwf.bin'
    path.write_bytes(patch(bytearray(path.read_bytes())))
    print('localized both main menus (seven nine-cell rows)')


if __name__ == '__main__':
    install()
