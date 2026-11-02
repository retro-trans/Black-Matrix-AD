"""Native counterpart of the exact Units-list record translated by the HD pack.

Only the verified 60-cell list is aliased. Preserve custom names, other layouts,
all persistent/save data, and the existing r35 single-name alias handler.
"""
import hashlib
import struct
import reusable_atlas as atlas
import units_list_redraw as units
import sh4asm

CODE=0x8C0F2C00
SOURCE_TABLE=CODE+128
TARGET_TABLE=SOURCE_TABLE+120
END=CODE+0x400
EXE_SHA='fe6f4c774d7080fb77d496e222f17abb0661f4e585797a9b200a1f848023bfe2'


def tables():
    source=''.join(units.NATIVE_ROWS)
    target=''.join(units.ALIASES.get(i,row).ljust(6) for i,row in enumerate(units.NATIVE_ROWS))
    assert len(source)==len(target)==60
    return tuple(struct.pack('<60H',*(units.index(ch) for ch in text)) for text in (source,target))


def hook():
    a=sh4asm.Asm(CODE)
    a.long_('source',SOURCE_TABLE);a.long_('target',TARGET_TABLE);a.long_('existing',atlas.NAME_CODE)
    a.label('entry');a.mov_i(60,0);a.cmp_eq(4,0);a.bf('done')
    a.mov_w_at(14,1);a.cmp_eq(1,0);a.bf('done')
    a.mov_l_pc('source',1);a.mov(14,2);a.add_i(4,2);a.mov_i(60,6)
    a.label('compare');a.mov_w_at(1,0);a.mov_w_at(2,3);a.cmp_eq(3,0);a.bf('done')
    a.add_i(2,1);a.add_i(2,2);a.add_i(-1,6);a.tst(6,6);a.bf('compare')
    a.mov_l_pc('target',1);a.mov(14,2);a.add_i(4,2);a.mov_i(60,6)
    a.label('copy');a.mov_w_at(1,0);a.mov_w_store(0,2)
    a.add_i(2,1);a.add_i(2,2);a.add_i(-1,6);a.tst(6,6);a.bf('copy')
    a.label('done');a.mov_l_pc('existing',3);a.jmp(3);a.nop()
    return a


def patch(source):
    if hashlib.sha256(source).hexdigest()!=EXE_SHA:raise ValueError('unknown r35 executable')
    original=(atlas.ROOT/'extracted/1ST_READ.BIN').read_bytes()
    if any(source[CODE-atlas.BASE:END-atlas.BASE]) or any(original[CODE-atlas.BASE:END-atlas.BASE]):
        raise ValueError('native alias reservation occupied')
    old=atlas.build_code(True).assemble();signature=struct.pack('<I',atlas.NAME_CODE)
    if old.count(signature)!=1 or source[atlas.CODE-atlas.BASE:atlas.CODE-atlas.BASE+len(old)]!=old:
        raise ValueError('unknown existing alias call')
    blob=hook().assemble();src,dst=tables()
    if CODE+len(blob)>SOURCE_TABLE or TARGET_TABLE+len(dst)>END:raise ValueError('alias exceeds reservation')
    result=bytearray(source)
    offset=atlas.CODE-atlas.BASE+old.index(signature)
    result[offset:offset+4]=struct.pack('<I',CODE)
    for address,data in ((CODE,blob),(SOURCE_TABLE,src),(TARGET_TABLE,dst)):
        result[address-atlas.BASE:address-atlas.BASE+len(data)]=data
    return bytes(result)
