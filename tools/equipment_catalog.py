"""Source-bound localization of every identified weapon and armor record.

No table expansion: names consume only eight verified text slots; descriptions
retain their 38-cell, two-row allocation. Unknown data is rejected atomically.
"""
import csv
import struct
from pathlib import Path

import patchline
import terms
import uistr

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT/'script/ui/equipment_catalog.tsv'
WEAPONS = tuple(range(0x64852, 0x6EB73, 0x120))
ARMOR = (*range(0x713F2, 0x72943, 0x7C), 0x749B6)


def entries():
    with UI.open(encoding='utf-8-sig') as f:
        rows = list(csv.DictReader((s for s in f if not s.startswith('#')), delimiter='\t'))
    expected = {**{o:('weapon',22) for o in WEAPONS},
                **{o:('armor',44) for o in ARMOR}}
    seen = set(); glossary = terms.load_glossary()
    for row in rows:
        offset = int(row['name_offset'],0)
        description = int(row['description_offset'],0)
        if offset in seen or expected.get(offset)!=(row['kind'],description-offset):
            raise ValueError('unknown or duplicate equipment catalog record')
        seen.add(offset)
        row['name_offset'],row['description_offset'] = offset,description
        row['name_english'] = terms.expand_text(row['name_english'],glossary)
        row['description_english'] = terms.expand_text(row['description_english'],glossary)
        name = row['name_english']; lines = row['description_english'].split('\\n')
        if not 1<=len(name)<=8 or len(lines)!=2 or any(len(s)>19 for s in lines):
            raise ValueError('equipment text exceeds reserved slots: '+row['name_japanese'])
        for ch in name+''.join(lines):patchline.to_sjis(ch)
    if seen!=set(expected):raise ValueError('equipment catalog coverage is incomplete')
    return rows


def payloads(row):
    name = row['name_english']
    description = ''.join(s.ljust(19) for s in row['description_english'].split('\\n'))
    encode = lambda count,text: struct.pack('<%dH'%(len(text)+1),count,
                                           *(patchline.to_sjis(c) for c in text))
    return ((row['name_offset']-2,encode(len(name),name.ljust(8))),
            (row['description_offset']-2,encode(38,description)))


def patch(data):
    original = (ROOT/'extracted/PARAMETA.DAT').read_bytes()
    if len(data)!=len(original):raise ValueError('unexpected parameter archive size')
    rows = entries(); pending = []
    for row in rows:
        o,d = row['name_offset'],row['description_offset']
        name = next(uistr.walk(original,o-2,1),None)
        desc = next(uistr.walk(original,d-2,1),None)
        if not name or not desc or name[2]!=row['name_japanese'] or not 1<=name[1]<=8:
            raise ValueError('equipment source name mismatch at %X'%o)
        if desc[1]!=38 or desc[2].replace('\u3000','')!=row['description_japanese']:
            raise ValueError('equipment source description mismatch at %X'%d)
        tail = struct.unpack_from('<%dH'%(8-name[1]),original,o+name[1]*2)
        # The final mystery sword has a stale ド after its five-cell count:
        # source slot text is ？？？ソード, then two spaces. It is still inside
        # the same eight-word name array, before both category/attack flags.
        expected_tail = (0x8368,patchline.SPACE,patchline.SPACE) if o==0x6EB72 else (patchline.SPACE,)*(8-name[1])
        if tail!=expected_tail:
            raise ValueError('equipment name padding is not free')
        for offset,target in payloads(row):
            if data[offset:offset+len(target)] not in (original[offset:offset+len(target)],target):
                raise ValueError('unknown existing equipment text at %X'%offset)
            pending.append((offset,target))
    for offset,target in pending:data[offset:offset+len(target)] = target
    return dict(weapon_records=len(WEAPONS),armor_records=len(ARMOR),
                name_slots=8,description_rows=2,description_columns=19,
                scope='192 source-bound names/descriptions only; all non-text item fields unchanged')


def names():
    return sorted({r['name_english'] for r in entries()})


def records():
    result = []
    for row in entries():
        name = row['name_english']
        result.extend((name,name.ljust(8),''.join(
            s.ljust(19) for s in row['description_english'].split('\\n'))))
    return sorted(set(result))
