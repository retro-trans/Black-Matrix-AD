"""Localize the Magic panel using already-retired main-menu text storage.

No additional executable arena, texture budget, combat data or stat values.
Requires mainmenu.ensure first; the old field-menu record is then unreferenced.
"""
import struct
import cooking
import field_battle_ui
import mainmenu
import patchline

ROOT = mainmenu.ROOT
UI = ROOT/'script/ui/magic_menu.tsv'
STORAGE = 0x88B28
STORAGE_END = 0x88B60
TITLE_POINTER = 0x6D140
RANGE_POINTER = 0x6D14C
COLUMNS = 0x6CF7A
INSET = 0x6D040
UNAVAILABLE = 0x89ECE
BASE = 0x8C010000


def encoded(text):
    return struct.pack('<%dH' % (len(text)+1), len(text),
                       *(patchline.to_sjis(c) for c in text))


def strings():
    text = cooking.strings(UI)
    if len(text['heading']) > 10 or len(text['unavailable']) != 8:
        raise ValueError('Magic title or empty-list record exceeds its slots')
    if any(len(text[k]) > 5 for k in ('range', 'area')):
        raise ValueError('Magic range label exceeds five columns')
    return text


def patch(data):
    if struct.unpack_from('<I',data,mainmenu.MENUS[0][1])[0] != mainmenu.STORAGE:
        raise ValueError('install expanded main menus before reusing their old storage')
    mainmenu.ensure(data)  # Also verifies both relocated menu pointers/grids.
    original = (ROOT/'extracted/1ST_READ.BIN').read_bytes()
    text = strings()
    title = encoded(text['heading'])
    ranges = encoded(text['range'].ljust(5) + ' '*5 + text['area'].ljust(5))
    storage = title+ranges
    if STORAGE+len(storage) > STORAGE_END:
        raise ValueError('Magic labels exceed retired menu storage')
    old_field = bytearray(original)
    field_battle_ui.patch_executable(old_field)
    if data[STORAGE:STORAGE_END] not in (original[STORAGE:STORAGE_END],
                                       old_field[STORAGE:STORAGE_END]):
        raise ValueError('retired field-menu storage is not a known source')
    sites = ((TITLE_POINTER, struct.pack('<I', BASE+0x89E88), struct.pack('<I', BASE+STORAGE)),
             (RANGE_POINTER, struct.pack('<I', BASE+0x89F10), struct.pack('<I', BASE+STORAGE+len(title))),
             (COLUMNS, bytes.fromhex('3360'), bytes.fromhex('05e0')),
             (INSET, struct.pack('<f', 24), struct.pack('<f', 6)))
    for offset, expected, replacement in sites:
        if data[offset:offset+len(expected)] != expected:
            raise ValueError('unknown Magic menu site at %X' % offset)
    count = 2+8*2
    if data[UNAVAILABLE:UNAVAILABLE+count] != original[UNAVAILABLE:UNAVAILABLE+count]:
        raise ValueError('unknown no-magic record')
    # Every check precedes mutation. Retain the old menu's count word so the
    # shared mainmenu verifier can still validate its relocation independently.
    data[STORAGE:STORAGE+len(storage)] = storage
    data[UNAVAILABLE:UNAVAILABLE+count] = encoded(text['unavailable'])
    for offset, _, replacement in sites:
        data[offset:offset+len(replacement)] = replacement
    return dict(labels=text, storage=BASE+STORAGE, bytes=len(storage),
                range_columns=5, range_rows=3, range_left_inset=6,
                scope='Magic text only; numbers, border, combat and memory limits unchanged')
