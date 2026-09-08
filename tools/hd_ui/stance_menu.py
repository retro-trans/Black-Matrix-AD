"""Expand the three stance rows without changing stance IDs or combat logic."""
import struct
import cooking
import patchline
import reusable_atlas as atlas
from sh4asm import Asm

UI = atlas.ROOT/'script/ui/stance_menu.tsv'
COLS, ROWS = 7, 3
ORIGINAL, POINTER = 0x87FD6, 0x20024
CONSTRUCTOR = 0x1FEE0
SIGNATURE = bytes.fromhex('03eb b360 4fd3 e281 e381 012e e181')


def constructor(address, record):
    a = Asm(address)
    # Caller retains R11=3 for the selection count and stance IDs. R0=3.
    a.mov_w_stored_r0(6, 14); a.mov_w_stored_r0(2, 14)
    a.mov_i(COLS, 0)
    a.mov_w_stored_r0(4, 14); a.mov_w_store(0, 14)
    a.mov_l_pc('record', 3); a.rts(); a.nop()
    a.long_('record', record)
    return a.assemble()


def patch(data, battle):
    storage = (battle['storage']+battle['bytes']+3)&~3
    text = cooking.strings(UI)
    labels = [text[key] for key in ('guard','evade','counter')]
    if any(len(s)>COLS for s in labels):
        raise ValueError('stance label exceeds seven cells')
    words = [patchline.to_sjis(c) for s in labels for c in s.ljust(COLS)]
    record = struct.pack('<22H', len(words), *words)
    helper = (storage+len(record)+3)&~3
    code = constructor(helper, storage)
    if helper+len(code)>atlas.COSTS:
        raise ValueError('stance menu exceeds reserved arena')
    if data[CONSTRUCTOR:CONSTRUCTOR+len(SIGNATURE)] != SIGNATURE:
        raise ValueError('unknown stance constructor')
    if struct.unpack_from('<I',data,POINTER)[0] != atlas.BASE+ORIGINAL:
        raise ValueError('unknown stance pointer')
    if struct.unpack_from('<H',data,ORIGINAL)[0] != 9:
        raise ValueError('unknown stance record')
    start, end = storage-atlas.BASE, helper+len(code)-atlas.BASE
    if any(data[start:end]):
        raise ValueError('stance storage occupied')
    # All validation precedes mutation. Reuse the existing literal load to
    # call a leaf constructor; R3 returns the relocated text pointer.
    struct.pack_into('<I', data, POINTER, helper)
    struct.pack_into('<4H', data, CONSTRUCTOR+6, 0x430B, 0x0009, 0x0009, 0x0009)
    data[start:start+len(record)] = record
    data[helper-atlas.BASE:end] = code
    return dict(storage=storage, bytes=len(record), helper=helper,
                helper_bytes=len(code), labels=labels, columns=COLS, rows=ROWS)
