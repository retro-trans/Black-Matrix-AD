"""Opt-in native battle Turn-panel checklist, with script-derived live rules.

Only the Turn panel is changed. No score, battle, input or save-state writes.
The original panel constructor/close state machines are retained. Rendering
uses the game's existing HUD atlas and per-sprite geometry, so both native
and HD texture configurations work without new hash-dependent text textures.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import sh4asm
import s_rank_rules

BASE = 0x8C010000
RENDER = 0x8C0F2800
DRAW = 0x8C083340
MARK = RENDER + 400
READ = 0x8C0F4700
TABLE = 0x8C0F4A00
ROWS = 0x8C0F4BC0
STRINGS = 0x8C0F4D20
END = 0x8C0F50D8
FLOATS = 0x8C0F5800
VALUES_SIZE = 80
STACK_SIZE = 144  # values[80], string[64]
ATLAS = 0x8C261234
CMD = 0x8C0FED0C
GROUP = 0x8C0FD572
V3 = 0x8C0FD950
COUNTERS = 0x8C1940DC
MAX_SPRITES = 384
GLYPH_WIDTH = 14
GLYPH_HEIGHT = 9
CHAR_ADVANCE = 12
ROW_ADVANCE = 11
TICK_SLANT = 1
PANEL_COLUMNS = 11
PANEL_ROWS = 12
PANEL_WIDTH = PANEL_COLUMNS * 32
PANEL_HEIGHT = PANEL_ROWS * 16  # framebuffer units, not displayed pixels
DISPLAY_Y_SCALE = 2  # 640x240 framebuffer -> 640x480 display
# Clockwise quad corners in framebuffer units; Y doubles on display.
# Two solid strokes, not distorted font glyphs. Each shape fits its 14x9 slot.
MARK_SHAPES = {
    67: ((1,4,3,3,7,6,5,7), (4,6,12,1,14,2,6,7)),
    69: ((2,2,4,1,13,6,11,7), (2,6,11,1,13,2,4,7)),
    43: ((3,4,12,4,12,5,3,5),),
}

# text, numeric value index/position/digits, check index, visibility mask.
# Checks: 0 none; positive = nonzero passes; negative = zero passes.
# masks: 1 ranked, 2 Faust, 4 recruitment, 8 prisoners, 16 turn27, 32 unranked.
ROW_DEFS = [
    ('TURN 000', 0, 5, 3, 0, 0),
    ('CT 000', 1, 3, 3, 0, 0),
    ('BLOOD 00000', 2, 6, 5, 0, 0),
    ('S RANK CHECKLIST', -1, 0, 0, 0, 1),
    ('Score now 00  Target 7', 3, 10, 2, 0, 1),
    ('Starting score 4', -1, 0, 0, 0, 1),
    ('Turn limit 000  2p', 4, 11, 3, 14, 1),
    ('CT limit 000    1p', 5, 9, 3, 15, 1),
    ('No healing items -0 cap3', 6, 18, 1, -6, 1),
    ('No blood refills -0 cap2', 7, 18, 1, -7, 1),
    ('No ally deaths -0 cap2', 8, 16, 1, -8, 1),
    ('No armor summon -0 cap1', 9, 17, 1, -9, 1),
    ('No low bio magic -0 cap1', 10, 18, 1, -10, 1),
    ('SPECIAL CONDITION', -1, 0, 0, 0, 30),
    ('Defeat Faust  0 of3', 11, 14, 1, 11, 2),
    ('Recruit objective -0 cap1', 12, 19, 1, -12, 4),
    ('Spare prisoners -0 cap1', 12, 17, 1, -12, 8),
    ('Finish by turn27 -0 cap1', 12, 18, 1, -12, 16),
    ('Ticks mean still on track', -1, 0, 0, 0, 1),
    ('No rank for this battle', -1, 0, 0, 0, 32),
]
# SYSTEM's HUD sheet has A-Z and digits, NOT the lowercase glyphs that the
# generic ASCII converter can address. Those slots contain unrelated icons.
ROW_DEFS = [(text.upper(), *fields) for text, *fields in ROW_DEFS]


def rules():
    rows = [r for r in s_rank_rules.catalog() if set(r['limits']) == {'turn','ct'}]
    assert len(rows) == 55
    result = []
    for r in rows:
        faust = any(s['args'][1:] == [0x35, [('int',3)]] for s in r['special_writes'])
        flags = 1 | (2 if faust else 0) | {143:8,207:4,277:16}.get(r['group'],0)
        result.append((r['group'],r['limits']['turn'],r['limits']['ct'],flags))
    return result


def reader():
    """R4 -> 80-byte caller buffer. Only R0-R7 are clobbered; no calls."""
    a = sh4asm.Asm(READ)
    for name,v in [('group',GROUP),('table',TABLE),('counters',COUNTERS),('vars',V3+0x64),
                   ('special',V3+0x118),('master',0x8C0FD5FE)]: a.long_(name,v)
    a.mov_i(0,0)
    for off in range(0,64,4): a.mov_l_stored(0,off,4)
    a.mov_l_pc('counters',5)
    a.mov_w_at(5,0); a.extu_w(0,0); a.mov_l_stored(0,0,4)
    a.mov_w_atd_r0(2,5); a.extu_w(0,0); a.mov_l_stored(0,4,4)
    a.mov_l_atd(16,5,0); a.mov_l_stored(0,8,4)
    a.mov_i(32,0); a.mov_l_stored(0,52,4)
    a.mov_l_pc('group',1); a.mov_w_at(1,6)
    # The CMP2 header occupies archive entry 0. Its runtime resource table
    # starts with entry 1: runtime 187 loads archive group 188, for example.
    a.add_i(1,6); a.mov_l_pc('table',5)
    a.label('search'); a.mov_w_at(5,0); a.tst(0,0); a.bt('done')
    a.cmp_eq(6,0); a.bt('found'); a.add_i(8,5); a.bra('search'); a.nop()
    a.label('found')
    for src,dst in [(2,16),(4,20),(6,52)]:
        a.mov_w_atd_r0(src,5); a.mov_l_stored(0,dst,4)
    a.mov_l_pc('vars',5)
    for src,dst in [(8,24),(10,28),(16,32),(12,36),(14,40),(6,44)]:
        a.mov_w_atd_r0(src,5); a.mov_l_stored(0,dst,4)
    # Recruitment penalties are evaluated at victory by PSI. Mirror those
    # exact predicates here without mutating the script's provisional flags.
    a.mov_l_pc('special',7); a.mov_i(0,3)
    a.mov(6,0); a.mov_i(-113,2); a.extu_b(2,2); a.cmp_eq(2,0); a.bf('not143')
    a.mov_l_pc('master',1); a.mov_w_at(1,0); a.cmp_eq_i(5); a.bt('special_done')
    a.mov_w_atd_r0(12,7); a.mov(0,1); a.mov_w_atd_r0(14,7); a._w(0x201B)
    a.tst(0,0); a.bt('special_done'); a.mov_i(1,3); a.bra('special_done'); a.nop()
    a.label('not143'); a.mov(6,0); a.mov_i(-49,2); a.extu_b(2,2); a.cmp_eq(2,0); a.bf('not207')
    a.mov_w_at(7,0); a.cmp_eq_i(1); a.bf('special_done')
    a.mov_i(0,1)
    for off in (0,2,4,6): a.mov_w_atd_r0(off,7); a.add(0,1)
    a.mov_i(2,2); a.cmp_ge(1,2); a.bf('special_failed')
    a.mov_l_pc('counters',1); a.add_i(24,1)
    a.mov_w_atd_r0(8,1); a.mov(0,2); a.mov_w_atd_r0(10,1); a.add(0,2)
    a.mov_i(4,1); a.cmp_ge(2,1); a.bt('special_done')
    a.label('special_failed'); a.mov_i(1,3); a.bra('special_done'); a.nop()
    a.label('not207'); a.mov_l_atd(52,4,0); a.mov_i(16,2); a.tst(2,0); a.bt('special_done')
    a.add_i(-20,7); a.mov_w_at(7,3)  # v3[130], becomes 1 after turn 27
    a.label('special_done'); a.mov_l_stored(3,48,4)
    # The score is max(4 - penalties, 0), THEN add Turn/CT/Faust bonuses.
    a.mov_i(4,6)
    for off in (24,28,32,36,40,48): a.mov_l_atd(off,4,0); a.sub(0,6)
    a.cmp_pz(6); a.bt('nonnegative'); a.mov_i(0,6)
    a.label('nonnegative')
    for tag,current,limit,stored,out,bonus in [('turn',0,16,2,56,2),('ct',4,20,4,60,1)]:
        a.mov_l_atd(current,4,1); a.mov_l_atd(limit,4,2)
        a.mov_i(0,3); a.cmp_ge(1,2); a.bf(tag+'_done')
        a.mov_w_atd_r0(stored,5); a.tst(0,0); a.bt(tag+'_done')
        a.mov_i(1,3); a.add_i(bonus,6)
        a.label(tag+'_done'); a.mov_l_stored(3,out,4)
    a.mov_l_atd(44,4,0); a.add(0,6); a.mov_l_stored(6,12,4)
    a.label('done'); a.rts(); a.nop()
    return a.assemble()


def draw():
    """R4=node, R5=glyph, R6=x, R7=y, R0=color -> next node.

    Build the sprite with the stock HUD dispatcher, then set all 4 corners.
    Uses the pre-existing VWF integer/float lookup table, not FPU state.
    """
    a = sh4asm.Asm(DRAW)
    for n,v in [('cmd',CMD),('atlas',ATLAS),('dispatch',0x8C06BEB8),('next',0x8C06BC18),
                ('mask',0xF007),('floats',FLOATS)]: a.long_(n,v)
    for r in (8,9,10,11): a.mov_l_dec(r,15)
    a.sts_l_pr(15)
    a.mov(4,8); a.mov(6,9); a.mov(7,10); a.mov_i(0,11)
    a.cmp_eq_i(-1); a.bt('plain')
    a.mov(0,3); a.mov(5,0); a.cmp_eq_i(67); a.bf('restore_color')
    a.mov_i(TICK_SLANT,11)  # Slant the green V into an asymmetric check mark.
    a.label('restore_color'); a.mov(3,0)
    a.label('plain'); a.mov_l_pc('cmd',1)
    a.mov_i(-127,2); a.extu_b(2,2); a.mov_w_store(2,1)
    a.mov_l_pc('atlas',2); a.mov_l_at(2,2); a.mov_l_stored(2,4,1)
    a.mov(0,3); a.mov(5,0); a.mov_w_stored_r0(8,1)
    a.add_i(68,1)
    for off in (0,4,8,12): a.mov_l_stored(3,off,1)
    a.mov_l_pc('dispatch',3); a.mov_l_pc('mask',5); a.jsr(3); a.mov(8,4)
    a.mov_l_pc('floats',7)
    for off,reg,extra in [(12,9,0),(16,10,0),(20,9,GLYPH_WIDTH),(24,10,0),
                           (28,9,GLYPH_WIDTH),(32,10,GLYPH_HEIGHT),(36,9,0),(40,10,GLYPH_HEIGHT)]:
        a.mov(reg,0)
        if extra: a.add_i(extra,0)
        if off in (16,40): a.add(11,0)
        a.shll2(0); a.mov_l_r0(7,1); a.mov_l_stored(1,off,8)
    a.mov_l_pc('next',3); a.jsr(3); a.mov(8,4)
    a.lds_l_pr(15)
    for r in (11,10,9,8): a.mov_l_inc(15,r)
    a.rts(); a.nop()
    return a.assemble()


def mark():
    """Render real solid-colour check/cross/dash quads; same ABI as draw().

    Native node attribute +44 bit31 enables texturing (8C06C914). Attribute
    0x60 keeps the allocator's ordinary blend bits but disables texturing.
    Dispatch mask F011 sets active/absolute-coordinate flags, attributes and
    all vertex colours. Geometry is populated directly, as for HUD text.
    """
    a=sh4asm.Asm(MARK)
    for key,value in [('cmd',CMD),('dispatch',0x8C06BEB8),('next',0x8C06BC18),
                      ('mask',0xF011),('floats',FLOATS)]:a.long_(key,value)
    # Shape table is fixed at +320, clear of this helper's literal pool.
    for key,off in [('check',0),('cross',16),('dash',32)]:a.long_(key,MARK+320+off)
    for r in (8,9,10,11,12,13,14):a.mov_l_dec(r,15)
    a.sts_l_pr(15)
    a.mov(4,8);a.mov(6,9);a.mov(7,10);a.mov(0,13);a.mov_i(2,12)
    a.mov(5,0);a.cmp_eq_i(67);a.bf('not_check');a.mov_l_pc('check',11);a.bra('setup');a.nop()
    a.label('not_check');a.cmp_eq_i(69);a.bf('dash_shape');a.mov_l_pc('cross',11);a.bra('setup');a.nop()
    a.label('dash_shape');a.mov_l_pc('dash',11);a.mov_i(1,12)
    a.label('setup');a.mov_l_pc('cmd',1)
    a.mov_l_atd(12,1,14)  # shared command scratch: restore its attributes below
    a.mov_i(-127,0);a.extu_b(0,0);a.mov_w_store(0,1)
    a.mov_i(96,0);a.mov_l_stored(0,12,1)
    a.add_i(68,1)
    for off in (0,4,8,12):a.mov_l_stored(13,off,1)
    a.label('stroke');a.tst(8,8);a.bt('done')
    a.mov_l_pc('dispatch',3);a.mov_l_pc('mask',5);a.jsr(3);a.mov(8,4)
    a.mov_l_pc('floats',7)
    for i in range(8):
        a.mov_b_at(11,0);a.add_i(1,11);a.add(9 if i%2==0 else 10,0)
        a.shll2(0);a.mov_l_r0(7,1);a.mov_l_stored(1,12+i*4,8)
    a.mov_l_pc('next',3);a.jsr(3);a.mov(8,4);a.mov(0,8)
    a.add_i(-1,12);a.tst(12,12);a.bf('stroke')
    a.label('done');a.mov_l_pc('cmd',1);a.mov_l_stored(14,12,1)
    a.mov(8,0);a.lds_l_pr(15)
    for r in (14,13,12,11,10,9,8):a.mov_l_inc(15,r)
    a.rts();a.nop()
    code=a.assemble();assert len(code)<=320
    table=bytes(v for shape in MARK_SHAPES.values() for quad in shape for v in quad)
    return code+bytes(320-len(code))+table


def render(vector_marks=True, guard_empty=False):
    a = sh4asm.Asm(RENDER)
    for n,v in [('read',READ),('rows',ROWS),('clear',0x8C06BCAE),('first',0x8C06BBF0),
                ('handle',0x8C26360C),('draw',DRAW),('copy',0x8C06D0DC),
                ('number',0x8C06CF40),('convert',0x8C06D026),('resume',0x8C0835E4),
                ('green',0xFF60FF70),('red',0xFFFF6060),('pending',0xFFAAAAAA),
                ('state',0x8C2634CC)]:a.long_(n,v)
    if vector_marks:a.long_('mark_draw',MARK)
    a.add_i(-72,15); a.add_i(-72,15)
    a.mov(15,13); a.mov(15,14); a.add_i(80,14)
    a.mov_l_pc('read',3); a.jsr(3); a.mov(13,4)
    for name in ('clear','first'):
        a.mov_l_pc('handle',1); a.mov_l_at(1,4); a.mov_l_pc(name,3); a.jsr(3); a.nop()
    a.mov(0,12); a.mov_l_pc('rows',8); a.mov_i(5,9)
    if guard_empty:
        a.tst(12,12); a.bt('done')
    a.label('row'); a.mov_l_at(8,5); a.tst(5,5); a.bt('done')
    a.mov_w_atd_r0(14,8); a.tst(0,0); a.bt('visible')
    a.mov_l_atd(52,13,1); a.tst(1,0); a.bt('skiprow')
    a.label('visible'); a.mov_l_pc('copy',3); a.jsr(3); a.mov(14,4)
    a.mov_w_atd_r0(4,8); a.cmp_pz(0); a.bf('converted')
    a.shll2(0); a.mov_l_r0(13,4)
    a.mov_w_atd_r0(6,8); a.mov(14,5); a.add(0,5)
    a.mov_w_atd_r0(8,8); a.mov(0,6); a.mov_l_pc('number',3); a.jsr(3); a.nop()
    # CF40 terminates the formatted field. Restore its following space.
    a.mov_w_atd_r0(6,8); a.mov(0,1); a.mov_w_atd_r0(8,8); a.add(1,0)
    a.mov_i(32,1); a._w(0x0E14)  # MOV.B R1,@(R0,R14)
    a.label('converted')
    a.mov_w_atd_r0(10,8); a.mov(0,5); a.mov_l_pc('convert',3); a.jsr(3); a.mov(14,4)
    a.mov_i(12,10); a.mov_i(0,11)
    a.mov_w_atd_r0(12,8); a.tst(0,0); a.bt('text')
    a.mov(0,2); a.cmp_pz(0); a.bt('positive')
    a.mov_i(0,0); a.sub(2,0)
    a.label('positive'); a.shll2(0); a.mov_l_r0(13,1)
    a.cmp_pz(2); a.bt('test_positive')
    a.tst(1,1); a.bt('pass'); a.bra('fail'); a.nop()
    a.label('test_positive'); a.tst(1,1); a.bf('pass')
    a.mov(2,0); a.cmp_eq_i(11); a.bt('pending_mark')
    a.label('fail'); a.mov_l_pc('red',0); a.mov_i(69,5); a.bra('mark'); a.nop() # X
    a.label('pass'); a.mov_l_pc('green',0); a.mov_i(67,5); a.bra('mark'); a.nop() # V
    a.label('pending_mark'); a.mov_l_pc('pending',0); a.mov_i(43,5)
    a.label('mark'); a.mov(12,4); a.mov(10,6); a.mov(9,7)
    a.mov_l_pc('mark_draw' if vector_marks else 'draw',3); a.jsr(3); a.nop(); a.mov(0,12); a.mov_i(30,10)
    a.label('text'); a.mov_w_atd_r0(10,8); a.cmp_ge(0,11); a.bt('nextrow')
    a.mov(11,0); a.mov_b_r0(14,5); a.extu_b(5,5)
    a.mov(5,0); a.cmp_eq_i(80); a.bt('advance')
    if guard_empty:
        a.tst(12,12); a.bt('done')
    a.mov(12,4); a.mov(10,6); a.mov(9,7); a.mov_i(-1,0)
    a.mov_l_pc('draw',3); a.jsr(3); a.nop(); a.mov(0,12)
    a.label('advance'); a.add_i(CHAR_ADVANCE,10); a.add_i(1,11); a.bra('text'); a.nop()
    a.label('nextrow'); a.add_i(ROW_ADVANCE,9)
    a.label('skiprow'); a.add_i(16,8); a.bra('row'); a.nop()
    a.label('done'); a.add_i(72,15); a.add_i(72,15)
    a.mov_l_pc('state',8); a.mov_l_pc('resume',3); a.jmp(3); a.nop()
    return a.assemble()


def data_blobs():
    table = b''.join(struct.pack('<4H',*r) for r in rules()) + bytes(8)
    rows = bytearray(); strings = bytearray()
    for text,idx,pos,digits,check,mask in ROW_DEFS:
        assert len(text) < 32 and (idx < 0 or text[pos:pos+digits] == '0'*digits)
        rows += struct.pack('<Ihhhhhh', STRINGS+len(strings),idx,pos,digits,len(text),check,mask)
        strings += text.encode('ascii') + b'\0'
    rows += bytes(16)
    return {TABLE:table, ROWS:rows, STRINGS:strings}


def patch(source,vector_marks=True):
    original = (ROOT/'extracted/1ST_READ.BIN').read_bytes()
    if len(source) != len(original): raise ValueError('Unknown executable size')
    if source[0x731CA:0x73652] != original[0x731CA:0x73652]:
        raise ValueError('Turn panel differs from authenticated original')
    for lo,hi in [(RENDER,RENDER+1024),(READ,END)]:
        if any(source[lo-BASE:hi-BASE]) or any(original[lo-BASE:hi-BASE]):
            raise ValueError(f'Checklist reservation occupied: {lo:x}')
    for n in range(400):
        if source[FLOATS-BASE+n*4:FLOATS-BASE+n*4+4] != struct.pack('<f',n):
            raise ValueError('Requires the current VWF float lookup table')
    blobs={RENDER:render(vector_marks),DRAW:draw(),READ:reader(),**data_blobs()}
    assert RENDER+len(blobs[RENDER]) <= MARK
    if vector_marks:blobs[MARK]=mark()
    assert MARK+len(mark()) <= RENDER+960
    assert DRAW+len(blobs[DRAW]) <= 0x8C0835E4
    assert READ+len(blobs[READ]) <= TABLE
    assert TABLE+len(blobs[TABLE]) <= ROWS
    assert ROWS+len(blobs[ROWS]) <= STRINGS
    assert STRINGS+len(blobs[STRINGS]) <= END
    # Expand only this panel's allocation to 384 nodes (24 << 4).
    # The constructor literal hook preserves its original R4=32 delay slot.
    stub_at=RENDER+960
    aa=sh4asm.Asm(stub_at).long_('allocator',0x8C06B9BE)
    aa.mov_i(24,4);aa.shll2(4);aa.shll2(4);aa.mov_l_pc('allocator',3);aa.jmp(3);aa.nop()
    blobs[stub_at]=aa.assemble()
    blobs[0x8C083300]=struct.pack('<I',stub_at)
    jump=sh4asm.Asm(0x8C083324).long_('draw',RENDER)
    jump.mov_l_pc('draw',0);jump.jmp(0);jump.nop()
    blobs[0x8C083324]=jump.assemble()
    blobs[0x8C083264]=struct.pack('<HH',0xE000|PANEL_ROWS,0xE200|PANEL_COLUMNS)
    result=bytearray(source)
    for addr,blob in blobs.items():result[addr-BASE:addr-BASE+len(blob)]=blob
    return bytes(result)
