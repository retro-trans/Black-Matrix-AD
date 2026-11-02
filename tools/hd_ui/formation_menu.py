"""Formation/BP headings, finish confirmation and three requested help pages.

Assign BP uses the unused tail of the already-relocated battle menu, directly
after Abilities. Counts, title grid, party selection and BP arithmetic stay.
"""
import struct

import cooking
import inventory_menu
import field_battle_ui
import magic_menu

ROOT = inventory_menu.ROOT
UI = ROOT/'script/ui/formation_menu.tsv'
ARRANGE, BP, FINISH = 0x89E8E, 0x89E9E, 0x89F1E
ARRANGE_POINTERS = (0x638B0,0x6BA78,0x6D5F4,0x6EBBC)
BP_POINTERS = (0x638B4,0x6EBC0)
FINISH_POINTER = 0x641B4
STORAGE, END = 0x87FBA, 0x87FCE
HELP = {0x79AF0:'choose_units',0x79DA8:'assign_overview',0x79E90:'manual_bp'}


def strings():
    text = cooking.strings(UI)
    if not 1<=len(text['arrange'])<=7 or len(text['assign_bp'])!=9 or not 1<=len(text['finish'])<=9:
        raise ValueError('formation text exceeds its record capacity')
    return text


def help_records():
    text = strings();result=[]
    for key in HELP.values():
        rows=text[key].split('\\n')
        if len(rows)!=3 or any(len(row)>19 for row in rows):
            raise ValueError('formation help must fit three 19-cell rows')
        result.append(''.join(row.ljust(19) for row in rows))
    return result


def records():
    text=strings()
    return [text['arrange'].ljust(7),text['assign_bp'],text['finish'].ljust(9)] + help_records()


def patch_executable(data,battle):
    candidate=bytearray(data)
    inventory_menu.patch_executable(candidate,battle)
    if candidate!=data:
        raise ValueError('install verified Abilities relocation before formation text')
    if STORAGE!=inventory_menu.END or END>inventory_menu.battle_menu.ORIGINAL+50:
        raise ValueError('formation storage overlaps another record')
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    previous=bytearray(original);field_battle_ui.patch_executable(previous)
    arrange,bp,finish=map(magic_menu.encoded,records()[:3])
    checks=[(ARRANGE,[original[ARRANGE:ARRANGE+16],arrange]),
            (BP,[original[BP:BP+10]]),
            (FINISH,[original[FINISH:FINISH+20],finish]),
            (STORAGE,[original[STORAGE:END],previous[STORAGE:END],bp])]
    for pointer in ARRANGE_POINTERS:
        checks.append((pointer,[struct.pack('<I',magic_menu.BASE+ARRANGE)]))
    checks.append((FINISH_POINTER,[struct.pack('<I',magic_menu.BASE+FINISH)]))
    for pointer in BP_POINTERS:
        checks.append((pointer,[struct.pack('<I',magic_menu.BASE+o) for o in (BP,STORAGE)]))
    for offset,accepted in checks:
        if data[offset:offset+len(accepted[0])] not in accepted:
            raise ValueError('unknown formation text site at %X' % offset)
    for offset,payload in ((ARRANGE,arrange),(FINISH,finish),(STORAGE,bp)):
        data[offset:offset+len(payload)]=payload
    for pointer in BP_POINTERS:struct.pack_into('<I',data,pointer,magic_menu.BASE+STORAGE)
    return dict(headings=records()[:2],confirmation=strings()['finish'],storage=STORAGE,
                scope='text records and two title pointers only; selection and BP logic unchanged')


def patch_parameters(data):
    original=(ROOT/'extracted/PARAMETA.DAT').read_bytes();pending=[]
    for offset,text in zip(HELP,help_records()):
        source=original[offset:offset+116];target=magic_menu.encoded(text)
        if len(source)!=116 or struct.unpack_from('<H',source)[0]!=57:
            raise ValueError('formation help source count changed')
        if data[offset:offset+116] not in (source,target):
            raise ValueError('unknown formation help at %X' % offset)
        pending.append((offset,target))
    for offset,target in pending:data[offset:offset+116]=target
    return dict(pages=list(HELP.values()),columns=19,rows=3,
                scope='three help text records only; party and BP data unchanged')
