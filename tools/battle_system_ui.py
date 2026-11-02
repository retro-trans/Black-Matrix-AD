"""Translate battle-system menus and a six-slot generic unit name safely.

Keep menu counts, constructors, pointers and selection IDs unchanged.
The name occupies six reserved words, NOT the following level/stat fields.
"""
import struct
from pathlib import Path

import cooking
import patchline

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT/'script/ui/battle_system.tsv'
COLS = 6
MENUS = ((0x87FFC, ('turn','units','items','abilities','config')),
         (0x8803A, ('turn','units','items','abilities','retreat','config')))
UNIT_HEADING = 0x8A044
NAME_RECORDS = (0x88A,0x2188A,0x4288A)
NAME_SLOTS = 6


def strings():
    text = cooking.strings(UI)
    if any(not value or len(value) > COLS for value in text.values()):
        raise ValueError('battle-system translation exceeds its six-cell field')
    return text


def encode(text):
    return struct.pack('<%dH' % len(text), *(patchline.to_sjis(c) for c in text))


def records():
    """Exact padded text records, also used to seed native-fallback HD sheets."""
    text = strings()
    return [''.join(text[k].ljust(COLS) for k in keys) for _,keys in MENUS] + [
        text['units'].ljust(COLS),text['muscular_man'],text['muscular_man'].ljust(8)]


def patch_executable(data):
    original = (ROOT/'extracted/1ST_READ.BIN').read_bytes()
    text = strings(); pending = []
    for offset, keys in (*MENUS,(UNIT_HEADING,('units',))):
        count = len(keys)*COLS
        payload = encode(''.join(text[k].ljust(COLS) for k in keys))
        expected = struct.pack('<H',count)+payload
        source = original[offset:offset+len(expected)]
        if struct.unpack_from('<H',source)[0] != count:
            raise ValueError('original battle menu count changed')
        if data[offset:offset+len(expected)] not in (source,expected):
            raise ValueError('unknown battle-system record at %X' % offset)
        pending.append((offset+2,payload))
    # All validation precedes writes; counts and all executable instructions stay intact.
    for offset,payload in pending:
        data[offset:offset+len(payload)] = payload
    return dict(menus=[dict(offset=o,labels=[text[k] for k in keys]) for o,keys in MENUS],
                columns=COLS,unit_heading=text['units'])


def patch_parameters(data):
    original = (ROOT/'extracted/PARAMETA.DAT').read_bytes()
    name = strings()['muscular_man']
    payload = struct.pack('<H',len(name))+encode(name.ljust(NAME_SLOTS))
    if len(payload) != 14:
        raise ValueError('unit name exceeds the reserved six words')
    for offset in NAME_RECORDS:
        source = original[offset:offset+14]
        japanese = '筋肉質の男'
        expected = struct.pack('<7H',5,*[int.from_bytes(c.encode('cp932'),'big')
                                        for c in japanese+'\u3000'])
        if source != expected or data[offset:offset+14] not in (source,payload):
            raise ValueError('unknown generic unit-name record at %X' % offset)
    for offset in NAME_RECORDS:
        data[offset:offset+14] = payload
    return dict(source='筋肉質の男',name=name,slots=NAME_SLOTS,records=list(NAME_RECORDS))


def install():
    files = [(ROOT/'build/1ST_READ.vwf.bin',patch_executable),
             (ROOT/'build/PARAMETA.vwf.dat',patch_parameters)]
    pending = []
    for path,patch in files:
        data = bytearray(path.read_bytes()); patch(data); pending.append((path,data))
    for path,data in pending:
        path.write_bytes(data)
    print('localized both battle-system menus, Units heading, and three generic unit-name records')


if __name__ == '__main__':
    install()
