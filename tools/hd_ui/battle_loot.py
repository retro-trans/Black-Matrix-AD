"""Localize the shared loot message and the shown Potion name in place."""
import struct

import cooking
import equipment_catalog
import patchline
import uistr

ROOT=cooking.ROOT
UI=ROOT/'script/ui/battle_loot.tsv'
MESSAGE=0x880C6
POINTER=0x212DC
POTION=0x729BC
TOKEN='{ITEM}'
ITEM_WORD=0xB003


def strings():
    text=cooking.strings(UI)
    template=text['obtained']
    if template.count(TOKEN)!=1 or len(template.replace(TOKEN,'X'))!=7:
        raise ValueError('loot message must keep seven words and one item control')
    if not 1<=len(text['potion'])<=8:raise ValueError('Potion name exceeds eight slots')
    return text


def encoded_message():
    before,after=strings()['obtained'].split(TOKEN)
    words=[*(patchline.to_sjis(c) for c in before),ITEM_WORD,
           *(patchline.to_sjis(c) for c in after)]
    return struct.pack('<8H',7,*words)


def patch_executable(data):
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    source=struct.pack('<8H',7,0x8177,ITEM_WORD,0x8178,0x82F0,0x93FC,0x8EE8,0x8142)
    pointer=struct.pack('<I',0x8C010000+MESSAGE)
    if original[MESSAGE:MESSAGE+16]!=source or data[POINTER:POINTER+4]!=pointer:
        raise ValueError('unknown loot message source or pointer')
    target=encoded_message()
    if data[MESSAGE:MESSAGE+16] not in (source,target):
        raise ValueError('unknown installed loot message')
    data[MESSAGE:MESSAGE+16]=target
    return dict(template=strings()['obtained'],words=7,item_control=ITEM_WORD,
                scope='one fixed-size message; rewards, item lookup and window geometry unchanged')


def patch_parameters(data):
    original=(ROOT/'extracted/PARAMETA.DAT').read_bytes()
    source=original[POTION:POTION+18]
    record=next(uistr.walk(original,POTION,1),None)
    if not record or record[1:]!=(5,'ポーション') or source[12:]!=struct.pack('<3H',*(patchline.SPACE,)*3):
        raise ValueError('unknown Potion source or padding')
    name=strings()['potion']
    target=struct.pack('<9H',len(name),*(patchline.to_sjis(c) for c in name.ljust(8)))
    if data[POTION:POTION+18] not in (source,target):raise ValueError('unknown installed Potion name')
    data[POTION:POTION+18]=target
    return dict(name=name,scope='Potion name only; description, healing values and flags unchanged')


def records():
    text=strings();names=equipment_catalog.names()+[text['potion']]
    result={text['potion'],text['potion'].ljust(8),'Discard '+text['potion']+'?'}
    for name in names:
        for form in (name,name.ljust(8)):
            message=text['obtained'].replace(TOKEN,form)
            result.update((message,message.rstrip(),message.ljust(19)))
    return sorted(result)
