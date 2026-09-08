"""Stock-emulator experiment: budgeted canonical atlases for English text.

Does not change the normal build. Each eligible record retains its own texture
handle/lifetime but uses identical glyph-sheet contents. No runtime host hooks.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import latin
import sh4asm
import vwf

BASE = 0x8C010000
ARENA = 0x8C0F6900  # Leave 0xF6800..0xF6900 for the newer main-menu patch.
FORWARD = ARENA
REVERSE = FORWARD + 256
CODE = REVERSE + 256
END = 0x8C0F6F20
STATES = END - 32  # Per record: bit 7=fixed atlas, low 7 bits=extra size units.
COSTS = STATES - 196  # Original allocator units for counts 0..192.
MANAGER = 0x8C1D4D70
EXTRA_BUDGET = 128  # At most 64 KiB above original live texture allocations.
POOL_CEILING = 448  # Leave 32 KiB of the original 256 KiB pool uncommitted.
COUNTS = range(1, 193)
SLOTS = 128
SIZE_CALL = 0x8C05E0B0
FILL_START = 0x8C05E0CA
SIZE_STUB = 0x8C05E0DC
RESUME = 0x8C05E112


def native_units(count):
    """Mirror 0x8C05DAC0 using the verified [128,32,8,2,0] size table."""
    if not 0 <= count <= 192: raise ValueError('record count outside 0..192')
    capacities=(128,32,8,2,0); parts=[]; i=0
    while count:
        size=capacities[i]
        if count>size:
            parts.append(size);count-=size
        elif count>capacities[i+1]*(4-len(parts)):
            parts.append(size);break
        else:i+=1
    return sum(parts)//2


def tables():
    chars = {' ': 0, **latin.charmap()}
    glyphs = sorted(set(chars.values()))
    if len(glyphs) > SLOTS or max(glyphs) >= 256:
        raise ValueError('font no longer fits the prototype atlas')
    forward = bytearray([255] * 256)
    for slot, glyph in enumerate(glyphs):
        forward[glyph] = slot
    reverse = glyphs + [0] * (SLOTS - len(glyphs))
    return bytes(forward), struct.pack('<128H', *reverse), chars


def build_code():
    a = sh4asm.Asm(CODE)
    for key, val in dict(forward=FORWARD, reverse=REVERSE, nslots=SLOTS,
                         nglyph=4608, controls=0xC000, limit=256,
                         full_record=192, size=0x8C05D934, blit=0x8C05DC42,
                         records=vwf.LINE_RECORDS, stride=400,
                         flags=0x184, live=0x800, handle=0x188,
                         states=STATES, costs=COSTS, allocated=0x8000,
                         forecast_limit=POOL_CEILING+1,
                         manager=MANAGER, newline=0xA0FF,
                         extra_budget=EXTRA_BUDGET+1,
                         used_limit=POOL_CEILING-64+1).items():
        a.long_(key, val)

    # eligible(R4=record): R0=bool, destroys R0..R3,R6,R7 only.
    # Permit the structural line-break marker, but reject palette controls and
    # Japanese/symbol glyphs not represented in the canonical English sheet.
    a.label('eligible')
    a.mov_w_at(4, 0); a.extu_w(0, 2)
    a.tst(2, 2); a.bt('no')
    a.mov_l_pc('full_record', 3); a._w(0x3237); a.bt('no')  # count > 192
    a.mov(4, 1); a.add_i(4, 1)
    a.mov_l_pc('forward', 3); a.mov_l_pc('limit', 6)
    a.label('check')
    a.mov_w_at(1, 0); a.extu_w(0, 0)
    a.mov_l_pc('newline', 7); a.cmp_eq(7, 0); a.bt('check_next')
    a.cmp_hs(6, 0); a.bt('no')
    a.mov_b_r0(3, 0); a.cmp_eq_i(-1); a.bt('no')
    a.label('check_next')
    a.add_i(2, 1); a.add_i(-1, 2); a.tst(2, 2); a.bf('check')
    a.rts(); a.mov_i(1, 0)
    a.label('no'); a.rts(); a.mov_i(0, 0)

    # state_pointer(R4=record) -> R7=side-table byte or zero; clobbers R0..R3.
    a.label('state_pointer')
    a.mov_l_pc('records', 1); a.mov_l_pc('states', 7); a.mov_i(32, 2)
    a.mov_l_pc('stride', 3)
    a.label('state_scan'); a.cmp_eq(4, 1); a.bt('state_return')
    a.add(3, 1); a.add_i(1, 7); a.add_i(-1, 2); a.tst(2, 2); a.bf('state_scan')
    a.mov_i(0, 7)
    a.label('state_return'); a.rts(); a.nop()

    # Compute ORIGINAL size/descriptor first. Admission is recorded once per
    # allocation, so a later budget change can NEVER remap a fallback texture.
    # A released/reused record's stale marker is cleared before any decision.
    a.label('size_hook')
    for r in (4, 5, 6, 7, 8, 9, 10): a.mov_l_dec(r, 15)
    a.sts_l_pr(15)
    a.mov_l_pc('size', 3); a.jsr(3); a.nop(); a.mov(0, 8)
    a.mov(14, 4); a.bsr('state_pointer'); a.nop(); a.mov(7, 9)
    a.tst(9, 9); a.bt('size_done')
    a.mov_i(0, 0); a.mov_b_store(0, 9)
    a.bsr('eligible'); a.nop(); a.tst(0, 0); a.bt('size_done')
    a.mov_l_pc('manager', 1); a.mov_w_atd_r0(2, 1); a.extu_w(0, 0)
    a.mov_l_pc('used_limit', 3); a.cmp_hs(3, 0); a.bt('size_done')
    a.mov(0, 10); a.add_i(64, 10); a.sub(8, 10)
    a.mov_i(64, 6); a.sub(8, 6); a.cmp_pz(6); a.bt('delta_ready'); a.mov_i(0, 6)
    a.label('delta_ready'); a.mov(6, 5)
    a.mov_l_pc('states', 7); a.mov_l_pc('records', 1); a.mov_i(32, 2)
    a.label('budget_scan')
    a.mov_l_pc('flags', 0); a.mov_w_r0(1, 3)
    a.mov_l_pc('live', 0); a.tst(0, 3); a.bt('budget_pending')
    a.mov_b_at(7, 0); a.mov_i(127, 3); a._w(0x2039); a.add(0, 5)
    a.bra('budget_next'); a.nop()
    # Reserve native capacity for every allocated-but-not-yet-uploaded record.
    # Otherwise a large menu could consume its budget on the first few labels
    # and then stall while trying to upload the remaining native labels.
    a.label('budget_pending'); a.mov_l_pc('allocated', 0); a.tst(0, 3); a.bt('budget_next')
    a.mov_w_at(1, 0); a.extu_w(0, 0); a.mov_l_pc('full_record', 3)
    a._w(0x3037); a.bt('size_done')  # Unexpected pending count >192: fail closed.
    a.mov_l_pc('costs', 3); a.mov_b_r0(3, 0); a.extu_b(0, 0); a.add(0, 10)
    a.label('budget_next'); a.mov_l_pc('stride', 3); a.add(3, 1)
    a.add_i(1, 7); a.add_i(-1, 2); a.tst(2, 2); a.bf('budget_scan')
    a.mov_l_pc('extra_budget', 3); a.cmp_hs(3, 5); a.bt('size_done')
    a.mov_l_pc('forecast_limit', 3); a.cmp_hs(3, 10); a.bt('size_done')
    a.mov(6, 0); a.add_i(127, 0); a.add_i(1, 0); a.mov_b_store(0, 9)
    a.mov_l_pc('nslots', 4); a.mov_l_pc('size', 3); a.jsr(3); a.nop(); a.mov(0, 8)
    a.label('size_done'); a.mov(8, 0); a.lds_l_pr(15)
    for r in (10, 9, 8, 7, 6, 5, 4): a.mov_l_inc(15, r)
    a.rts(); a.nop()

    # Replaces only the blit loop. Allocation, submission and freeing remain
    # original. Every one of 128 slots is filled, including blank padding.
    # Stock count=128 splits into four 32-slot 128x128 texture segments.
    a.label('fill_hook')
    for r in (8, 9, 10, 11, 12, 13): a.mov_l_dec(r, 15)
    a.sts_l_pr(15); a.mov(14, 4); a.bsr('state_pointer'); a.nop()
    a.mov_i(0, 10); a.tst(7, 7); a.bt('fill_state_ready'); a.mov_b_at(7, 10)
    a.label('fill_state_ready'); a.mov_i(0, 8); a.mov_i(0, 9)
    a.mov_l_pc('blit', 12); a.mov_l_pc('reverse', 11)
    a.mov_w_at(14, 13); a.extu_w(13, 13)
    a.tst(10, 10); a.bt('fill_next'); a.mov_l_pc('nslots', 13)
    a.label('fill_next')
    a.cmp_hs(13, 8); a.bt('fill_done')
    a.mov(8, 0); a.shll(0)
    a.tst(10, 10); a.bt('original_glyph')
    a.mov_w_r0(11, 4); a.bra('blit_glyph'); a.mov_i(0, 6)
    a.label('original_glyph')
    a.add_i(4, 0); a.mov_w_r0(14, 4); a.extu_w(4, 4)
    a.mov_l_pc('nglyph', 3)
    a._w(0x3437)  # CMP/GT R3,R4, matching the original loop's >4608 test.
    a.bf('original_blit')
    a.mov(4, 0); a.mov_l_pc('controls', 3); a._w(0x2039)  # AND R3,R0
    a.cmp_eq(3, 0); a.bf('advance'); a.mov(4, 9); a.bra('advance'); a.nop()
    a.label('original_blit'); a.extu_b(9, 6)
    a.label('blit_glyph'); a.mov(8, 5); a.jsr(12); a.nop()
    a.label('advance'); a.add_i(1, 8); a.bra('fill_next'); a.nop()
    a.label('fill_done'); a.lds_l_pr(15)
    for r in (13, 12, 11, 10, 9, 8): a.mov_l_inc(15, r)
    a.rts(); a.nop()

    # slot_hook(R4=atlas handle,R5=original index) -> R0=texture slot.
    # Resolve a LIVE record by handle, never a cached pointer to a prior line.
    a.label('slot_hook')
    for r in (8, 9, 10): a.mov_l_dec(r, 15)
    a.sts_l_pr(15); a.mov(5, 8); a.mov(4, 9)
    a.mov_l_pc('records', 10); a.mov_i(32, 2)
    a.label('find')
    a.mov_l_pc('flags', 0); a.mov_w_r0(10, 1)
    a.mov_l_pc('live', 3); a.tst(3, 1); a.bt('next_record')
    a.mov_l_pc('handle', 0); a.mov_l_r0(10, 1); a.cmp_eq(9, 1); a.bt('found')
    a.label('next_record'); a.mov_l_pc('stride', 3); a.add(3, 10)
    a.add_i(-1, 2); a.tst(2, 2); a.bf('find'); a.bra('slot_original'); a.nop()
    a.label('found'); a.mov(10, 4); a.bsr('state_pointer'); a.nop()
    a.tst(7, 7); a.bt('slot_original'); a.mov_b_at(7, 0)
    a.tst(0, 0); a.bt('slot_original')
    a.mov_w_at(10, 3); a.extu_w(3, 3); a.cmp_hs(3, 8); a.bt('slot_original')
    a.mov(8, 0); a.shll(0); a.add_i(4, 0); a.mov_w_r0(10, 0)
    a.extu_w(0, 0); a.mov_l_pc('limit', 3); a.cmp_hs(3, 0); a.bt('slot_blank')
    a.mov_l_pc('forward', 3); a.mov_b_r0(3, 0)
    a.extu_b(0, 0); a.bra('slot_return'); a.nop()
    a.label('slot_blank'); a.mov_i(0, 0); a.bra('slot_return'); a.nop()
    a.label('slot_original'); a.mov(8, 0)
    a.label('slot_return'); a.lds_l_pr(15)
    for r in (10, 9, 8): a.mov_l_inc(15, r)
    a.rts(); a.nop()
    return a


def patch(source, original):
    exe = bytearray(source)
    forward, reverse, chars = tables()
    code = build_code(); blob = code.assemble()
    if CODE + len(blob) > COSTS:
        raise ValueError('prototype code exceeds reserved arena')
    if any(exe[ARENA-BASE:END-BASE]):
        raise ValueError('prototype arena is occupied; refusing to overwrite')
    # Ensure this is the known baseline VWF, not an unrelated newer renderer.
    v = vwf.build_code().assemble()
    if exe[vwf.CODE-BASE:vwf.CODE-BASE+len(v)] != v:
        raise ValueError('unexpected VWF baseline')
    for lo, hi in ((SIZE_CALL, SIZE_CALL+4), (FILL_START, RESUME)):
        if exe[lo-BASE:hi-BASE] != original[lo-BASE:hi-BASE]:
            raise ValueError('unexpected native text-loop signature')
    def put(addr, data): exe[addr-BASE:addr-BASE+len(data)] = data
    put(FORWARD, forward); put(REVERSE, reverse); put(CODE, blob)
    put(COSTS, bytes(native_units(n) for n in range(193)))
    v = vwf.build_code(code.labels['slot_hook'], ui_fixes=True).assemble()
    if vwf.CODE + len(v) > vwf.FLOAT_TAB: raise ValueError('VWF hook overflow')
    put(vwf.CODE, v)
    stub = sh4asm.Asm(SIZE_STUB)
    stub.long_('hook', code.labels['size_hook'])
    stub.mov_l_pc('hook', 3); stub.jmp(3); stub.nop()
    put(SIZE_STUB, stub.assemble())
    put(SIZE_CALL, struct.pack('<H', 0xB000 | ((SIZE_STUB-SIZE_CALL-4)//2 & 4095)))
    stub = sh4asm.Asm(FILL_START)
    stub.long_('hook', code.labels['fill_hook'])
    stub.mov_l_pc('hook', 3); stub.jsr(3); stub.nop()
    stub.bra('resume'); stub.nop(); stub.labels['resume'] = RESUME
    s = stub.assemble()
    if FILL_START + len(s) > SIZE_STUB: raise ValueError('stub overlap')
    put(FILL_START, s)
    return bytes(exe), dict(code_bytes=len(blob), code_labels=code.labels,
                           source_sha256=hashlib.sha256(source).hexdigest(),
                           patched_sha256=hashlib.sha256(exe).hexdigest(),
                           revision=2, scope='English 1..192-cell records, budgeted; line breaks allowed', slots=SLOTS,
                           extra_budget_bytes=EXTRA_BUDGET*512,
                           pool_ceiling_bytes=POOL_CEILING*512,
                           characters=chars, hardware_tested=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT/'build/reusable-atlas-expanded')
    args = p.parse_args()
    exe, manifest = patch((ROOT/'build/1ST_READ.vwf.bin').read_bytes(),
                          (ROOT/'extracted/1ST_READ.BIN').read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'1ST_READ.BIN').write_bytes(exe)
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__': main()
