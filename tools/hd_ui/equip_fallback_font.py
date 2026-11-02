"""Guarded draw-time canonical font borrowing for the low-budget Equip list.

Never changes allocation/admission, text records, handles or persistent nodes.
The footer's existing transient-node renderer is shared; its historical defaults
remain byte-identical. No live emulator writes or input.
"""
import hashlib
import struct
from pathlib import Path

import sh4asm
import skies_vga_sharp_footer as footer
import skies_size_match as metrics
import footer_remaining_font as captions
import reusable_atlas as atlas
import vwf

ROOT=Path(__file__).resolve().parents[2]
BASE=atlas.BASE
GATE,GATE_END=0x8c0f2b6c,0x8c0f2c00
OWNER,OWNER_END=0x8c0f2398,0x8c0f23fc  # Keep live Status flag23fc untouched.
PEN,PEN_END=0x8c0f24a4,0x8c0f2500  # After v3 Status driver, before close hook.
CONTEXT=0x8c1e7a3c
CAPTURE=ROOT/'build/choice-selector-inspection-2026-11-02/ram-25308-1793599209154132400.bin'
CAPTURE_SHA='e212dd6cdb97ac4f8ac5eae40ee97d6147cf6ce79b12f02df7f0a9960c712756'
EXE_HASHES={1:'387fd76fa34314d041ed426d46e272e1a1bbe411bb412e37ff5d73e4aa612fc3',
            2:'86f44f12658c94d1a9b20de1aa97052faa46e619d7e49bc3e3a085cb5265ad33'}


def owner():
    # Entry R8=node; return R0=record or0, R10=cell. Only caller-saved regs.
    a=sh4asm.Asm(OWNER)
    for k,v in dict(records=vwf.LINE_RECORDS,states=atlas.STATES,stride=400,
                    flags=0x184,handle=0x188,live=0x800).items():a.long_(k,v)
    a.mov_w_atd_r0(8,8);a.extu_w(0,10);a.mov_i(40,1);a.cmp_hs(1,10);a.bt('no')
    a.mov_l_atd(4,8,7);a.mov_l_pc('records',1);a.mov_l_pc('states',2);a.mov_i(32,3)
    a.label('scan');a.mov_l_pc('handle',0);a.mov_l_r0(1,4);a.cmp_eq(7,4);a.bf('next')
    a.mov_l_pc('flags',0);a.mov_w_r0(1,4);a.mov_l_pc('live',0);a.tst(0,4);a.bt('next')
    a.mov_b_at(2,0);a._w(0xc880);a.bf('no')  # Already canonical: keep normal path.
    # Dedicated star slot96 has28x16 icon geometry, not Latin16x12.
    a.mov(10,0);a.shll(0);a.add_i(4,0);a.mov_w_r0(1,0);a.cmp_eq_i(90);a.bt('no')
    a.rts();a.mov(1,0)
    a.label('next');a.mov_l_pc('stride',0);a.add(0,1);a.add_i(1,2);a.add_i(-1,3)
    a.tst(3,3);a.bf('scan');a.label('no');a.rts();a.mov_i(0,0)
    return a.assemble()


def pen():
    # R12=eligible record, R10=cell. R13=old-small horizontal advance sum;
    # R10=glyph id; R12=0 is the transient renderer's Equip discriminator.
    a=sh4asm.Asm(PEN)
    a.long_('old',vwf.ADV_TAB);a.long_('small',metrics.SMALL_ADV)
    a.mov(10,0);a._w(0xc9f8);a.mov(0,2);a.shll(2);a.add(12,2);a.add_i(4,2)
    a.mov(10,3);a.mov_i(7,0);a._w(0x2309);a.mov_i(0,13)
    a.mov_l_pc('old',4);a.mov_l_pc('small',5)
    a.label('loop');a.tst(3,3);a.bt('glyph');a.mov_w_at(2,0);a.extu_w(0,0)
    a.mov_b_r0(4,6);a.extu_b(6,6);a.mov_b_r0(5,7);a.extu_b(7,7)
    a.add(6,13);a.sub(7,13);a.add_i(2,2);a.add_i(-1,3);a.bra('loop');a.nop()
    a.label('glyph');a.mov_w_at(2,10);a.extu_w(10,10);a.mov_i(0,12);a.rts();a.nop()
    return a.assemble()


def gate():
    # Called ONLY from footer fallback, inside its saved-register/stack frame.
    # Every draw revalidates shape, window, owner, glyphs and live donor.
    code=atlas.build_code(True);code.assemble()
    a=sh4asm.Asm(GATE)
    for k,v in dict(context=CONTEXT,windows=vwf.WIN_TAB,owner=OWNER,
                    eligible=code.labels['eligible'],find=footer.FIND,pen=PEN).items():a.long_(k,v)
    a.sts_l_pr(15);a.mov_l_pc('context',1)
    for off,value in ((8,8),(10,5),(14,1)):
        a.mov_w_atd_r0(off,1);a.cmp_eq_i(value);a.bf('no')
    a.mov_l_at(1,0);a.mov_i(-64,2);a.extu_b(2,2);a.cmp_hs(2,0);a.bt('no')
    a.mov_i(28,2);a.mul_l(0,2);a.sts_macl(2);a.mov_l_pc('windows',1);a.add(2,1)
    a.cmp_eq(9,1);a.bf('no');a.mov_l_atd(4,9,0);a.cmp_eq_i(40);a.bf('no')
    a.mov_l_pc('owner',2);a.jsr(2);a.nop();a.tst(0,0);a.bt('no');a.mov(0,12)
    a.mov_w_at(12,0);a.cmp_eq_i(40);a.bf('no')
    a.mov_l_pc('eligible',2);a.jsr(2);a.mov(12,4);a.tst(0,0);a.bt('no')
    a.mov_l_pc('find',2);a.jsr(2);a.nop();a.cmp_pz(0);a.bf('no');a.mov(0,11)
    a.mov_l_pc('pen',2);a.jsr(2);a.nop();a.mov_i(1,0);a.bra('done');a.nop()
    a.label('no');a.mov_i(0,0);a.label('done');a.lds_l_pr(15);a.rts();a.nop()
    return a.assemble()


def blocks():
    result={GATE:gate(),OWNER:owner(),PEN:pen(),
        footer.MAIN:footer.main(extra_table=0x8c0f30c0,extra_count=4,equip_gate=GATE),
        footer.GEOMETRY:footer.geometry(vertical_texel_center=True,equip_fallback=True)}
    for start,end in ((GATE,GATE_END),(OWNER,OWNER_END),(PEN,PEN_END),
                      (footer.MAIN,footer.MAIN_END),(footer.GEOMETRY,footer.GEOMETRY_END)):
        if start+len(result[start])>end:raise ValueError(f'Equip helper overflow {start:x}: {len(result[start])}/{end-start}')
    return result


def patch_exe(before,disc):
    if disc not in EXE_HASHES or hashlib.sha256(before).hexdigest()!=EXE_HASHES[disc]:
        raise ValueError('Unknown per-disc0.1.9 executable')
    ram=CAPTURE.read_bytes();original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    if hashlib.sha256(ram).hexdigest()!=CAPTURE_SHA:raise ValueError('Unknown Equip capture')
    expected={footer.MAIN:footer.main(extra_table=0x8c0f30c0,extra_count=4),
              footer.GEOMETRY:footer.geometry(vertical_texel_center=True)}
    result=bytearray(before);allowed=set()
    for address,payload in blocks().items():
        old=expected.get(address,b'');size=max(len(old),len(payload));lo=address-BASE;hi=lo+size
        if before[lo:hi]!=old+bytes(size-len(old)) or any(original[lo:hi]):
            raise ValueError(f'Unknown/occupied Equip reservation {address:x}')
        # Capture predates the Remove caption, whose only MAIN differences
        # are the authenticated secondary table pointer and its row count.
        captured=footer.main(extra_table=captions.EXTRA) if address==footer.MAIN else old
        if ram[address-0x8c000000:address-0x8c000000+size]!=captured+bytes(size-len(captured)):
            raise ValueError(f'Captured reservation differs {address:x}')
        result[lo:hi]=payload+bytes(size-len(payload));allowed.update(range(lo,hi))
    delta=[i for i,(a,b) in enumerate(zip(before,result)) if a!=b]
    if not delta or not set(delta)<=allowed or len(result)!=len(before):raise ValueError('Unexpected Equip edit')
    return bytes(result),delta


if __name__=='__main__':print({hex(a):len(b) for a,b in blocks().items()})
