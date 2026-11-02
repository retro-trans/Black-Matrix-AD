"""Localize three fixed party names without touching adjacent unit stats."""
import struct

import cooking
import battle_system_ui

ROOT = battle_system_ui.ROOT
UI = ROOT/'script/ui/party_names.tsv'
SLOTS = 6
NAMES = ((0x203086,'leburobs','レブロブス'),
         (0x2030F2,'piripo','ピリポ'),
         (0x20315E,'gaius','ガイウス'))
VARIANTS = (0,0x1800,0x3000)


def strings():
    text = cooking.strings(UI)
    if any(not 1<=len(s)<=SLOTS for s in text.values()):
        raise ValueError('party status name exceeds six reserved character slots')
    return text


def records():
    return [form for name in strings().values() for form in (name,name.ljust(SLOTS),name.ljust(8))]


def display_alias_table():
    """Exact glyph-record aliases, not replacements in persistent party/save data."""
    import latin
    chars = latin.charmap()
    result = bytearray()
    for _, key, japanese in NAMES:
        source = [latin.sjis_to_index(int.from_bytes(c.encode('cp932'),'big'))
                  for c in japanese]
        target = [chars[c] for c in strings()[key]]
        result += struct.pack('<14H', len(source), *(source+[0]*(SLOTS-len(source))),
                              len(target), *(target+[0]*(SLOTS-len(target))))
    return bytes(result)


def patch_parameters(data):
    original=(ROOT/'extracted/PARAMETA.DAT').read_bytes()
    text=strings();pending=[]
    for offset,key,japanese in NAMES:
        source=struct.pack('<7H',len(japanese),*(int.from_bytes(c.encode('cp932'),'big')
            for c in japanese.ljust(SLOTS,'\u3000')))
        target=struct.pack('<H',len(text[key]))+battle_system_ui.encode(text[key].ljust(SLOTS))
        for delta in VARIANTS:
            o=offset+delta
            if original[o:o+14]!=source or data[o:o+14] not in (source,target):
                raise ValueError('unknown party name or padding at %X' % o)
            pending.append((o,target))
    for o,target in pending:data[o:o+14]=target
    return dict(names=text,slots=SLOTS,records=[o for o,_ in pending],
                scope='nine fixed name records only; adjacent stats and save files unchanged')
