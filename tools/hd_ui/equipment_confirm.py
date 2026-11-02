"""Translate dynamic equipment confirmations without changing Yes/No actions."""
import struct

import cooking
import equipment_menu
import field_battle_ui
import mainmenu
import patchline

ROOT=mainmenu.ROOT
UI=ROOT/'script/ui/equipment_confirm.tsv'
TOKEN='{ITEM}'
ITEM_WORD=0xB003
STORAGE,END=0x89826,0x89852
# Original record, pointer literal, width argument in the call's delay slot.
PROMPTS=((0x83CDE,0x6BE30,0x6BD2E,'unequip'),
         (0x83CC0,0x6BF74,0x6BF3A,'discard'))
COLS=18


def strings():
    text=cooking.strings(UI)
    for key in ('unequip','discard'):
        if text[key].count(TOKEN)!=1:
            raise ValueError('equipment prompt must preserve exactly one item control')
        if len(text[key].replace(TOKEN,'X'))!=10:
            raise ValueError('equipment prompt exceeds its ten-word record')
    return text


def encode(text):
    before,after=text.split(TOKEN)
    words=[*(patchline.to_sjis(c) for c in before),ITEM_WORD,
           *(patchline.to_sjis(c) for c in after)]
    return struct.pack('<%dH'%(len(words)+1),len(words),*words)


def patch(data):
    # Do not mutate prerequisites. Both main menus must already be relocated;
    # verify the adjacent equipment heading on a copy before consuming the rest.
    candidate=bytearray(data);equipment_menu.patch_executable(candidate)
    if candidate!=data:
        raise ValueError('install equipment heading before confirmation records')
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    old_field=bytearray(original);field_battle_ui.patch_executable(old_field)
    text=strings();payload=b''.join(encode(text[k]) for _,_,_,k in PROMPTS)
    if len(payload)!=END-STORAGE or STORAGE!=equipment_menu.STORAGE_END:
        raise ValueError('equipment confirmation storage bounds changed')
    if data[STORAGE:END] not in (original[STORAGE:END],old_field[STORAGE:END],payload):
        raise ValueError('unknown retired confirmation storage')
    writes=[(STORAGE,payload)]
    for i,(source,pointer,width,key) in enumerate(PROMPTS):
        if data[source:source+14]!=original[source:source+14]:
            raise ValueError('original equipment confirmation record changed')
        old=struct.pack('<I',mainmenu.vwf.LOAD_BASE+source)
        new=struct.pack('<I',mainmenu.vwf.LOAD_BASE+STORAGE+i*22)
        if data[pointer:pointer+4] not in (old,new):
            raise ValueError('unknown equipment confirmation pointer')
        # Fixed 18 avoids the dialogue-specific 17/19 column expansion hooks.
        # Existing item fields hold <=8 chars: 7-letter verb + space + name + ?
        # needs at most 17 cells. Stock table[18]=16 => a centered 512px box.
        replacement=struct.pack('<H',0xE400|COLS)  # MOV #18,R4
        if data[width:width+2] not in (bytes.fromhex('0674'),replacement):
            raise ValueError('unknown equipment confirmation width argument')
        writes.extend(((pointer,new),(width,replacement)))
    for offset,value in writes:data[offset:offset+len(value)]=value
    return dict(labels=text,control=ITEM_WORD,columns=COLS,storage=STORAGE,
                bytes=len(payload),scope='two prompt pointers/width arguments; item selection and Yes/No logic unchanged')


def records():
    """Known English expansions; unknown/Japanese item names are not guessed."""
    names=cooking.strings(field_battle_ui.ITEM_UI)
    names=sorted({names[key] for key,_ in field_battle_ui.ITEM_NAMES.values()}
                 | set(field_battle_ui.equipment_catalog.names()))
    if any(not 1<=len(name)<=8 for name in names):
        raise ValueError('equipment name exceeds its eight-word field')
    return [template.replace(TOKEN,name) for template in strings().values()
            for name in names]+['YesNo ']
