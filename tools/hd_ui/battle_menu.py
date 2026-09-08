"""Expand only the eight-row battle command menu, preserving combat logic."""
import struct
import reusable_atlas as atlas
import cooking
import patchline

UI=atlas.ROOT/'script/ui/battle_menu.tsv'
COLS=9
ROWS=8
ORIGINAL=0x87FA4
POINTER=0x1D654
WIDTH=0x1D436
KEYS=('move','attack','magic','items','status','refill','stance','summon')


def patch(data):
    code=atlas.build_code();blob=code.assemble()
    storage=(atlas.CODE+len(blob)+3)&~3
    text=cooking.strings(UI)
    labels=[text[k] for k in KEYS]
    if any(len(label)>COLS for label in labels):raise ValueError('battle label exceeds nine cells')
    words=[patchline.to_sjis(ch) for label in labels for ch in label.ljust(COLS)]
    encoded=struct.pack('<%dH'%(1+len(words)),len(words),*words)
    if ROWS*COLS>100 or storage+len(encoded)>atlas.COSTS:
        raise ValueError('battle menu exceeds reserved storage or transition capacity')
    if data[atlas.CODE-atlas.BASE:atlas.CODE-atlas.BASE+len(blob)]!=blob:
        raise ValueError('unexpected HD renderer revision')
    if struct.unpack_from('<H',data,ORIGINAL)[0]!=24:
        raise ValueError('unexpected original battle record')
    if struct.unpack_from('<I',data,POINTER)[0]!=atlas.BASE+ORIGINAL:
        raise ValueError('battle record pointer changed')
    if struct.unpack_from('<H',data,WIDTH)[0]!=0xE403:
        raise ValueError('battle constructor changed')
    offset=storage-atlas.BASE
    if any(data[offset:offset+len(encoded)]):raise ValueError('battle storage occupied')
    # R4 initializes BOTH logical and allocated column counts; row count is
    # loaded independently as eight immediately after this constructor block.
    struct.pack_into('<H',data,WIDTH,0xE400|COLS)
    struct.pack_into('<I',data,POINTER,storage)
    data[offset:offset+len(encoded)]=encoded
    return dict(storage=storage,bytes=len(encoded),columns=COLS,rows=ROWS,labels=labels)
