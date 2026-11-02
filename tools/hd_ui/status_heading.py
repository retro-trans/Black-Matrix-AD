"""Relocate the Status title into the original, now-retired Magic range record.

The Magic patch must already redirect that record. No new memory, title-grid
geometry or combat code is needed; five title pointers share one English record.
"""
import struct

import cooking
import magic_menu
import mainmenu

ROOT = mainmenu.ROOT
UI = ROOT/'script/ui/action_headings.tsv'
TITLE = 0x89E7C
POINTERS = (0x638AC, 0x681A4, 0x6BA28, 0x6D5EC, 0x6EBB8)
STORAGE, END = 0x89F10, 0x89F1E


def text():
    value = cooking.strings(UI)['status']
    if len(value) != 6:
        raise ValueError('Status title must fit the six-cell retired range record')
    return value


def patch(data):
    # Validate prerequisites on a copy: ensure() may install unpatched menus.
    candidate = mainmenu.ensure(bytearray(data))
    if candidate != data:
        raise ValueError('install expanded main menus before Status heading')
    magic = magic_menu.strings()
    title = magic_menu.encoded(magic['heading'])
    ranges = magic_menu.encoded(magic['range'].ljust(5)+' '*5+magic['area'].ljust(5))
    base = magic_menu.BASE
    prerequisites = (
        (magic_menu.STORAGE, title+ranges),
        (magic_menu.TITLE_POINTER, struct.pack('<I', base+magic_menu.STORAGE)),
        (magic_menu.RANGE_POINTER, struct.pack('<I', base+magic_menu.STORAGE+len(title))),
        (magic_menu.COLUMNS, bytes.fromhex('05e0')),
        (magic_menu.INSET, struct.pack('<f', 6)),
    )
    for offset, expected in prerequisites:
        if data[offset:offset+len(expected)] != expected:
            raise ValueError('install verified Magic relocation before Status heading')
    original = (ROOT/'extracted/1ST_READ.BIN').read_bytes()
    if data[TITLE:TITLE+6] != struct.pack('<3H',2,0x8FF3,0x91D4):
        raise ValueError('original Status title record changed')
    if original[STORAGE:END] != bytes.fromhex('0600cb8ef69240814081cd94cd88'):
        raise ValueError('original retired range record changed')
    payload = magic_menu.encoded(text())
    if len(payload) != END-STORAGE:
        raise ValueError('Status storage bounds changed')
    if data[STORAGE:END] not in (original[STORAGE:END], payload):
        raise ValueError('unknown retired Magic range storage')
    old = struct.pack('<I', base+TITLE)
    new = struct.pack('<I', base+STORAGE)
    for offset in POINTERS:
        if data[offset:offset+4] not in (old, new):
            raise ValueError('unknown Status title pointer')
    # Every check precedes writes. Original title and shared heading layout stay.
    data[STORAGE:END] = payload
    for offset in POINTERS:
        data[offset:offset+4] = new
    return dict(heading=text(), storage=STORAGE, bytes=len(payload),
                pointers=list(POINTERS),
                scope='title record and pointers only; shared layout and stats unchanged')
