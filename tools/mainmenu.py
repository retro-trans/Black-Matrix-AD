"""Full labels for the two seven-row main menus, without global grid changes.

Shared by the normal and HD builds. Both menus are validated atomically;
the fixed-atlas arena immediately after their records remains reserved.
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
STORAGE_END = 0x8C0F6900  # Fixed-atlas LUT starts here: never cross it.
RECORD_BYTES = 2 + COLS * ROWS * 2
MENUS = (
    (0x88B26, 0x3DC4C, ((0x3DBD4, 0xE004), (0x3DBDA, 0xE304)), 'exit'),
    (0x89818, 0x5D6D8, ((0x5D666, 0xE004), (0x5D670, 0xE304)), 'deploy'),
)


def patch(data):
    """Validate all sites before changing anything. Return the patched buffer."""
    text = cooking.strings(UI)
    if STORAGE < vwf.FLOAT_TAB + vwf.NTAB * 4:
        raise ValueError('main-menu storage overlaps VWF float table')
    if STORAGE + len(MENUS) * RECORD_BYTES > STORAGE_END or COLS * ROWS > 100:
        raise ValueError('main-menu storage or transition capacity exceeded')
    writes = []
    for i, (original, pointer, instructions, last) in enumerate(MENUS):
        if struct.unpack_from('<H', data, original)[0] != 28:
            raise ValueError('main-menu original record changed')
        if struct.unpack_from('<I', data, pointer)[0] != vwf.LOAD_BASE + original:
            raise ValueError('main-menu record pointer changed')
        labels = [text[k] for k in ('status','ritual','items','shop','abilities','system',last)]
        if any(len(label) > COLS for label in labels):
            raise ValueError('main-menu label exceeds nine cells')
        words = [patchline.to_sjis(ch) for label in labels for ch in label.ljust(COLS)]
        encoded = struct.pack('<%dH' % (len(words)+1), len(words), *words)
        address = STORAGE + i * RECORD_BYTES
        offset = address - vwf.LOAD_BASE
        if len(data[offset:offset+len(encoded)]) != len(encoded) or any(data[offset:offset+len(encoded)]):
            raise ValueError('main-menu storage is no longer unused')
        writes.extend(((offset, encoded), (pointer, struct.pack('<I', address))))
        for off, expected in instructions:
            if struct.unpack_from('<H', data, off)[0] != expected:
                raise ValueError('main-menu width instruction changed')
            writes.append((off, struct.pack('<H', (expected & 0xFF00) | COLS)))
    for off, payload in writes:
        data[off:off+len(payload)] = payload
    return data



def ensure(data):
    """Accept only our exact existing installation, otherwise patch vanilla.

    The normal build now installs these menus before the HD build runs.
    Validate by reconstructing the original sites in a copy and reapplying.
    """
    first_original,first_pointer,_,_=MENUS[0]
    if struct.unpack_from('<I',data,first_pointer)[0]==vwf.LOAD_BASE+first_original:
        return patch(data)
    candidate=bytearray(data)
    start=STORAGE-vwf.LOAD_BASE
    candidate[start:start+len(MENUS)*RECORD_BYTES]=bytes(len(MENUS)*RECORD_BYTES)
    for original,pointer,instructions,_ in MENUS:
        struct.pack_into('<I',candidate,pointer,vwf.LOAD_BASE+original)
        for offset,word in instructions:struct.pack_into('<H',candidate,offset,word)
    expected=patch(candidate)
    if expected!=data:raise ValueError('existing main-menu patch does not match current sources')
    return data


def install():
    path = ROOT / 'build/1ST_READ.vwf.bin'
    path.write_bytes(patch(bytearray(path.read_bytes())))
    print('localized both main menus (seven nine-cell rows)')


if __name__ == '__main__':
    install()
