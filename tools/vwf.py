"""Build the variable-width-font patch for 1ST_READ.BIN.

Why this works at all is in docs/text-engine.md: a line is composed into a
glyph atlas where every character sits in its own cell, and the on-screen
position of each character comes from a per-cell node in the window's grid.
The node carries the four corners of the character's quad in window-local
coordinates:

    node+12/+16   top-left      (x , y )
    node+20/+24   top-right     (x2, y )
    node+28/+32   bottom-right  (x2, y2)
    node+36/+40   bottom-left   (x , y2)

Confirmed live: writing 100.0 into node+12 moved the rendered quad's corner to
100 + the window's origin.  So a variable-width font is just a matter of
rewriting those X values before the character is dispatched - the glyph
bitmaps, the atlas, the blit and the UVs are all left alone.

The pen position is recomputed from scratch on every call, so the patch is
idempotent: re-running it over an already-shifted grid gives the same answer.

    px    = col * cell_width - slack
    slack = sum of (24 - ink advance) over the characters before this one
            on the same row

Characters keep their full 28- (or 32-) pixel quad and simply overlap into
their neighbour's transparent margin, which is why the UVs need no change.

No FPU arithmetic is used.  Float values are taken from a table of the first
640 non-negative integers, and the integer form of a float already in a node
is recovered by scanning that same table, so FPSCR is never touched.

    python tools/vwf.py build            # write build/1ST_READ.vwf.bin
    python tools/vwf.py disasm           # disassemble what it generated
"""

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import sh4asm
import widths as W
import fontdump as fd
import textlayout

LOAD_BASE = 0x8C010000

# --- addresses in the game -------------------------------------------------
NODE_LOOKUP = 0x8C06BC44      # (window_id, cell_index) -> cell node
DISPATCH    = 0x8C06BEB8      # (node, message) - sends the built command
CMD         = 0x8C0FED0C      # the draw-command struct
COLOUR_TAB  = 0x8C0991D8      # attribute -> vertex colour
WIN_TAB     = 0x8C22B4D8      # 192 window entries, 28 bytes each
PLACE       = 0x8C0603B4      # "place one character" - replaced by a trampoline
PLACE_DEAD  = 0x8C0603C0      # its body, dead once the trampoline is in
PLACE_END   = 0x8C060432      # first byte we must not touch
REC_HOOK    = 0x8C0600EA      # in the layout loop, where R12 is the line record
LINE_RECORDS = 0x8C1D5018    # 32 line records, each 0x190 bytes
LINE_RECORD_STRIDE = 0x190
LINE_RECORD_COUNT = 32

# --- our arena: 6845 bytes of zeros at the tail of the image, still zero in
# --- a live RAM dump taken after the game had booted and run
ARENA       = 0x8C0F5464
G_RECORD    = ARENA           # 4 bytes: the current line record
G_WIDEN     = ARENA + 4       # 1 byte: did this character get the wider quad
CODE        = ARENA + 8
FLOAT_TAB   = 0x8C0F5800      # NTAB floats: 0.0 .. NTAB-1
ARENA_END   = 0x8C0F6F21

# Two more runs of zeros, also still zero in a live RAM dump, hold the metrics:
# one advance and one left bearing per glyph.  They do not fit in the arena
# beside the float table.
ADV_TAB     = 0x8C0F0E50      # 4608 bytes: glyph -> advance
BEAR_TAB    = 0x8C0F3464      # 4608 bytes: glyph -> leftmost inked column

# The float table supplies new pen positions and is also used to recover the
# small integer Y coordinates needed by the height/UV fix.  X geometry no
# longer needs to be scanned: uniform text-grid cells are known to be 28px
# wide.  That lets text windows own twice their stock cells per row without needing a huge
# table merely to recognise the off-screen grid positions of later cells.
NTAB = 1024
NGLYPH = 4608                 # every glyph index the blit will accept


# --- more cells per text row -----------------------------------------------
# A text window owns exactly `columns * rows` cell nodes and a row cannot hold
# more characters than it has cells, however narrow the glyphs are.  That, not
# any measuring, is what caps a line at 17 characters.
#
# 0x8C060504 places cell i at
#
#     x = (i mod columns) * 28      y = (i div columns) * 16
#
# reading `columns` from the window context, so raising it really does give a
# row more cells.  The extra cells run off the right of the box, but the VWF
# hook overwrites every X anyway, so only the row each cell lands on matters -
# and `i div columns` still gets that right.
#
# The three text-window creation paths call 0x8C0602D6 with columns in R5.
# One uses a direct BSR and two load the allocator address from literals before
# an indirect JSR. Route all three through a tail-jumping stub so unrelated
# grid/menu windows do not receive a larger allocation. Both text grids use
# 33 columns because NARR instructions can write into spoken windows too.
# Spoken dialogue has three rows and can use
# at most 33 columns: its transition object has 100 per-cell state slots, so a
# 42-column grid (126 cells) corrupts adjacent state and hangs during opening
# or closing.
GRID_CREATE = 0x8C0602D6
TEXT_CREATE_CALL = 0x8C05FD3C
TEXT_CREATE_CALL_OLD = b'\xCB\xB2'       # BSR GRID_CREATE
TEXT_CREATE_PTRS = (0x8C05E4C4, 0x8C05EB10)
GRID_PITCH_CALL = 0x8C060544
GRID_PITCH_CALL_OLD = b'\x1C\xE9'        # MOV #28,R9
ROW_PITCH_CALL = 0x8C0605AA
ROW_PITCH_CALL_OLD = b'\x08\x40\x08\x40'  # SHLL2 R0 twice: row * 16
EXPAND_TEXT_GRIDS = textlayout.EXPAND_TEXT_GRIDS

# The text-window close poll at 0x8C08C7AC calls the helper at 0x8C08AF52
# through this pointer, passing the active window handle. The helper hands the
# handle straight to 0x8C05E64C with no NULL/-1 check, so a handle of -1 (which
# occurs when a window finishes releasing before the next poll - observed on the
# occult-library AP-warning path, where 0x8C263B04 sits at -1) is dereferenced
# and hard-resets the machine. Routing non-positive handles to the global
# cleanup routine the helper already uses after a normal close (0x8C06B2DC)
# avoids the bad dereference while leaving valid handles on the stock path.
# This is independent of the expanded-grid experiment; it fixes the AP-shortage
# reset even on the stock 17/19-column baseline.
TEXT_CLOSE = 0x8C08AF52
TEXT_CLOSE_PTR = 0x8C08C828
TEXT_GLOBAL_CLOSE = 0x8C06B2DC
# Enabling this (route -1 close handles to global cleanup) did NOT fix the
# AP-shortage reset - the crash flips between freeze and reset with small
# layout changes, which points at the interpreter dispatching a bad offset
# rather than a fixed native null-deref. Left off until the real cause is found.
SAFE_TEXT_CLOSE = False

def _glyph(a, reg):
    """Emit: R0 = the glyph index at character `reg` of the record in R1.

    Leaves T set when the code is outside the glyph range - the caller skips
    the table lookup in that case, which is what happens for the line-break
    marker 0xA0FF and any other control code.
    """
    a.mov(reg, 0)
    a.shll(0)
    a.add_i(4, 0)                        # record + 4 + 2 * index
    a.mov_w_r0(1, 0)
    a.extu_w(0, 0)
    a.mov_w_pc("nglyph", 3)
    a.cmp_hs(3, 0)                       # T when glyph >= 4608


def build_code():
    """Assemble the replacement for 0x8C0603B4 plus the pen calculation."""
    a = sh4asm.Asm(CODE)

    a.long_("node_lookup", NODE_LOOKUP)
    a.long_("dispatch", DISPATCH)
    a.long_("cmd", CMD)
    a.long_("colour_tab", COLOUR_TAB)
    a.long_("win_tab", WIN_TAB)
    a.long_("g_record", G_RECORD)
    a.long_("line_records", LINE_RECORDS)
    a.word_("record_stride", LINE_RECORD_STRIDE)
    a.word_("record_atlas", 0x188)
    a.word_("record_flags", 0x184)
    a.word_("record_live", 0x8000)
    a.long_("g_widen", G_WIDEN)
    a.long_("float_tab", FLOAT_TAB)
    a.long_("adv_tab", ADV_TAB)
    a.long_("bear_tab", BEAR_TAB)
    a.long_("text_close", TEXT_CLOSE)
    a.long_("text_global_close", TEXT_GLOBAL_CLOSE)
    a.long_("f107", 0x0000F107)
    a.word_("op81", 0x0081)
    a.word_("n192", 192)
    a.word_("ntab", NTAB)
    a.word_("nglyph", NGLYPH)
    a.word_("v0off", 150)                # (u,v) pairs at node+148; v of corner 0
    a.word_("v2off", 158)                #                          v of corner 2
    a.word_("v3off", 162)                #                          v of corner 3

    # ---- vwf_place(R4=ctx, R5=cell, R6=char_index, R7=atlas, 0(sp)=attr) ---
    a.label("vwf_place")
    for r in (14, 13, 12, 11, 10, 9, 8):
        a.mov_l_dec(r, 15)
    a.sts_l_pr(15)                       # 32 bytes pushed; attr now at 32(sp)

    a.mov(4, 8)                          # R8  = ctx
    a.extu_w(5, 9)                       # R9  = cell index
    a.extu_w(6, 10)                      # R10 = index within the line record
    a.mov(7, 11)                         # R11 = atlas handle

    a.mov_l_at(8, 4)                     # R4 = *ctx = window id
    a.mov(9, 5)
    a.mov_l_pc("node_lookup", 3)
    a.jsr(3)
    a.nop()
    a.mov(0, 12)                         # R12 = cell node
    a.tst(12, 12)
    a.bt("dispatch_cmd")                 # no node: behave exactly as before
    a.bsr("vwf_adjust")
    a.nop()

    # ---- build command 0x81, as the original did --------------------------
    a.label("dispatch_cmd")
    a.mov_l_pc("cmd", 5)
    a.mov(11, 0)
    a.cmp_eq_i(-1)
    a.bf("have_atlas")
    a.mov_i(0, 6)
    a.mov_w_store(6, 5)                  # cmd->opcode = 0
    a.bra("tail")
    a.mov_i(1, 5)                        # delay slot: message = 1

    a.label("have_atlas")
    a.mov_w_pc("op81", 3)
    a.mov_w_store(3, 5)                  # cmd->opcode = 0x81
    a.mov_l_stored(11, 4, 5)             # cmd+4  = atlas handle
    a.mov(10, 0)
    a.mov_w_stored_r0(8, 5)              # cmd+8  = index within the record
    a.mov_i(12, 0)
    a.mov_l_r0(12, 1)
    a.mov_i(36, 0)
    a.mov_l_str_r0(1, 5)                 # cmd+36 = node+12  (X)
    a.mov_i(16, 0)
    a.mov_l_r0(12, 1)
    a.mov_i(40, 0)
    a.mov_l_str_r0(1, 5)                 # cmd+40 = node+16  (Y)

    a.mov_l_atd(32, 15, 0)               # attr
    a.extu_w(0, 0)
    a.shll2(0)
    a.mov_l_pc("colour_tab", 3)
    a.add(3, 0)
    a.mov_l_at(0, 3)
    a.mov(5, 2)
    a.add_i(68, 2)
    for _ in range(4):                   # the same colour on all four corners
        a.mov_l_store(3, 2)
        a.add_i(4, 2)
    a.mov_l_pc("f107", 5)

    # The original tail-jumped to the dispatcher.  We have to call it instead:
    # it writes the character's UVs into the node itself, so anything the hook
    # sets before this point is overwritten.  An empty cell node has its local
    # quad set but its UVs zero, which is what gives that away.
    a.label("tail")
    a.mov(12, 4)                         # R4 = node for the dispatcher
    a.mov_l_pc("dispatch", 3)
    a.jsr(3)
    a.nop()
    a.bsr("uv_fix")
    a.nop()
    a.lds_l_pr(15)
    for r in (8, 9, 10, 11, 12, 13, 14):
        a.mov_l_inc(15, r)
    a.rts()
    a.nop()

    # ---- uv_fix: widen the UV span the dispatcher just wrote --------------
    # in: R12 node.  Runs only when vwf_adjust widened the quad to match.
    a.label("uv_fix")
    a.tst(12, 12)
    a.bt("uvf_out")
    a.mov_l_pc("g_widen", 0)
    a.mov_b_at(0, 0)
    a.extu_b(0, 0)
    a.tst(0, 0)
    a.bt("uvf_out")

    # --- widen the quad and the sample to the whole atlas cell -------------
    # The renderer only samples 14 of the cell's 16 rows, which is what caps
    # how tall a glyph can be drawn.  Rows 14 and 15 are in the atlas and are
    # blank for all 4608 stock glyphs, so widening costs nothing that is
    # already on screen and buys two rows for the redrawn Latin.
    #
    # This has to run after the dispatcher.  The dispatcher rebuilds the
    # node's quad from the position in the command plus a fixed cell size, so
    # anything written before it is discarded - the pen survives only because
    # it travels through the command's own X field.  The UVs are written there
    # too; an empty cell node has a quad but zero UVs, which is what gives
    # that away.
    #
    # Both the quad and the UV span are rounded up to the next power of two,
    # which is the cell size in each case (14 -> 16 rows, 0x38 -> 0x40 of a
    # 64-pixel segment, 0x70 -> 0x80 of a 32-pixel one).  Rounding *up to*
    # rather than *past* a power of two keeps this idempotent.
    a.mov_i(16, 0)
    a.mov_l_r0(12, 5)                    # bits of y
    a.mov_i(32, 0)
    a.mov_l_r0(12, 6)                    # bits of y2
    a.mov_l_pc("float_tab", 1)
    a.mov_i(0, 2)
    a.mov_i(-1, 13)
    a.mov_i(-1, 7)
    a.mov_w_pc("ntab", 14)
    a.label("yscan")
    a.mov_l_inc(1, 0)
    a.cmp_eq(5, 0)
    a.bf("yscan_1")
    a.mov(2, 13)
    a.label("yscan_1")
    a.cmp_eq(6, 0)
    a.bf("yscan_2")
    a.mov(2, 7)
    a.label("yscan_2")
    a.add_i(1, 2)
    a.cmp_ge(14, 2)
    a.bf("yscan")

    a.cmp_pz(13)
    a.bf("uvf_out")                      # not integers we know: leave it alone
    a.cmp_pz(7)
    a.bf("uvf_out")
    a.sub(13, 7)                         # R7 = quad height
    a.cmp_pl(7)
    a.bf("uvf_out")
    a.mov_i(1, 3)
    a.label("pow_y")
    a.cmp_ge(7, 3)
    a.bt("pow_y_done")
    a.bra("pow_y")
    a.shll(3)
    a.label("pow_y_done")
    a.add(13, 3)                         # index of the new bottom edge
    a.mov_w_pc("ntab", 2)
    a.cmp_ge(2, 3)
    a.bt("uvf_out")
    a.mov_l_pc("float_tab", 1)
    a.mov(3, 0)
    a.shll2(0)
    a.mov_l_r0(1, 2)
    a.mov_i(32, 0)
    a.mov_l_str_r0(2, 12)
    a.mov_i(40, 0)
    a.mov_l_str_r0(2, 12)

    a.mov_w_pc("v0off", 0)
    a.mov_w_r0(12, 5)
    a.extu_w(5, 5)                       # v of the top edge
    a.mov_w_pc("v2off", 0)
    a.mov_w_r0(12, 6)
    a.extu_w(6, 6)                       # v of the bottom edge
    a.mov(6, 7)
    a.sub(5, 7)                          # sampled span
    a.cmp_pl(7)
    a.bf("uvf_out")
    a.mov_i(1, 3)
    a.label("pow_v")
    a.cmp_ge(7, 3)
    a.bt("pow_v_done")
    a.bra("pow_v")
    a.shll(3)
    a.label("pow_v_done")
    a.add(5, 3)                          # top edge + the whole cell
    a.mov_w_pc("v2off", 0)
    a.mov_w_str_r0(3, 12)
    a.mov_w_pc("v3off", 0)
    a.mov_w_str_r0(3, 12)
    a.label("uvf_out")
    a.rts()
    a.nop()

    # ---- vwf_adjust: rewrite the node's four X coordinates ----------------
    # in:  R8 ctx, R9 cell index, R10 index within the record, R12 node
    # out: nothing; leaves the node untouched unless everything checks out
    a.label("vwf_adjust")
    a.sts_l_pr(15)
    a.mov_l_pc("g_widen", 0)
    a.mov_i(0, 3)
    a.mov_b_store(3, 0)                  # assume not widened until it is

    a.mov_l_at(8, 1)                     # window id
    a.cmp_pz(1)
    a.bf("adj_out")
    a.mov_w_pc("n192", 2)
    a.cmp_ge(2, 1)
    a.bt("adj_out")
    a.mov_i(28, 2)
    a.mul_l(2, 1)
    a.sts_macl(1)
    a.mov_l_pc("win_tab", 3)
    a.add(3, 1)                          # R1 = window table entry
    a.mov_w_at(1, 2)
    a.extu_w(2, 2)
    a.mov_i(8, 3)
    a.tst(3, 2)
    a.bt("adj_out")                      # flag 0x0008: a uniform character grid

    a.mov_w_atd_r0(8, 8)                 # ctx+8 = columns
    a.extu_w(0, 3)
    a.tst(3, 3)
    a.bt("adj_out")

    a.mov(9, 4)                          # col = cell index mod columns
    a.label("col_loop")
    a.cmp_hs(3, 4)
    a.bf("col_done")
    a.bra("col_loop")
    a.sub(3, 4)
    a.label("col_done")

    # Flag 0x0008 above proves this is the game's uniform text grid.  Its cell
    # width is the fixed 28 used by the grid builder, so there is no reason to
    # scan a float table for x and x2.  Besides being cheaper, using the known
    # width permits more off-screen cell nodes than the float arena can span.
    a.mov_i(28, 7)                       # R7 = cell width

    # The pen puts each glyph's *ink* where the previous glyph's ink ended, so
    # the cell has to be pulled left by the glyph's own left bearing as well:
    #
    #   origin = bearing(row's first glyph)
    #          + sum of advances before this character
    #          - bearing(this glyph)
    #
    # At column 0 the two bearings are the same character's and cancel, which
    # keeps the left edge of every row exactly where the game put it.
    # Deferred menu placement does not pass through REC_HOOK. G_RECORD may
    # describe another window (even an empty/released line) by this point.
    # R11 is the atlas handle supplied to THIS placement call, so resolve its
    # owning live record. Handles are shared by a line's cells, not by windows.
    # Never use an unmatched record or read beyond its character storage.
    a.mov(11, 0)
    a.cmp_eq_i(-1)
    a.bt("adj_out")
    a.mov_l_pc("line_records", 1)
    a.mov_i(LINE_RECORD_COUNT, 2)
    a.label("record_search")
    a.mov_w_pc("record_flags", 0)
    a.mov_w_r0(1, 3)
    a.mov_w_pc("record_live", 5)
    a.tst(5, 3)
    a.bt("record_next")
    a.mov_w_at(1, 3)
    a.extu_w(3, 3)
    a.cmp_hs(3, 10)                      # character index must be < count
    a.bt("record_next")
    a.mov_w_pc("n192", 5)
    a.cmp_hs(3, 5)                       # count must be <= 192
    a.bf("record_next")
    a.mov_w_pc("record_atlas", 0)
    a.mov_l_r0(1, 3)
    a.cmp_eq(11, 3)
    a.bt("record_found")
    a.label("record_next")
    a.mov_w_pc("record_stride", 5)
    a.add(5, 1)
    a.add_i(-1, 2)
    a.tst(2, 2)
    a.bf("record_search")
    a.bra("adj_out")
    a.nop()
    a.label("record_found")
    a.cmp_hs(4, 10)                      # prevent negative row-start indices
    a.bf("adj_out")
    a.mov_i(0, 13)                       # R13 = accumulator

    a.mov(10, 2)
    a.sub(4, 2)                          # R2 = first character on this row
    a.mov(2, 6)                          # R6 = keep it

    a.label("adv_loop")
    a.cmp_hs(10, 2)
    a.bt("adv_done")
    _glyph(a, 2)                         # R0 = glyph at index R2, T set if bad
    a.bt("adv_next")
    a.mov_l_pc("adv_tab", 3)
    a.mov_b_r0(3, 0)
    a.extu_b(0, 0)
    a.add(0, 13)
    a.label("adv_next")
    a.bra("adv_loop")
    a.add_i(1, 2)
    a.label("adv_done")

    _glyph(a, 6)                         # bearing of the row's first glyph
    a.bt("bear_1")
    a.mov_l_pc("bear_tab", 3)
    a.mov_b_r0(3, 0)
    a.extu_b(0, 0)
    a.add(0, 13)
    a.label("bear_1")

    _glyph(a, 10)                        # bearing of this glyph
    a.bt("bear_2")
    a.mov_l_pc("bear_tab", 3)
    a.mov_b_r0(3, 0)
    a.extu_b(0, 0)
    a.sub(0, 13)
    a.label("bear_2")

    a.mov(13, 0)                         # px
    a.cmp_pz(0)
    a.bf("adj_out")
    a.mov_w_pc("ntab", 3)
    a.cmp_ge(3, 0)
    a.bt("adj_out")
    a.mov(0, 6)                          # R6 = px
    a.mov(6, 5)
    a.add(7, 5)                          # R5 = px + cell width
    a.mov_w_pc("ntab", 3)
    a.cmp_ge(3, 5)
    a.bt("adj_out")

    a.mov_l_pc("float_tab", 1)
    a.mov(6, 0)
    a.shll2(0)
    a.mov_l_r0(1, 2)                     # float bits for px
    a.mov(5, 0)
    a.shll2(0)
    a.mov_l_r0(1, 3)                     # float bits for px + width
    a.mov_i(12, 0)
    a.mov_l_str_r0(2, 12)
    a.mov_i(20, 0)
    a.mov_l_str_r0(3, 12)
    a.mov_i(28, 0)
    a.mov_l_str_r0(3, 12)
    a.mov_i(36, 0)
    a.mov_l_str_r0(2, 12)

    # Everything below has to happen *after* the dispatcher, so record that
    # this node qualifies and let uv_fix do it.
    a.mov_l_pc("g_widen", 0)
    a.mov_i(1, 3)
    a.mov_b_store(3, 0)

    a.label("adj_out")
    a.lds_l_pr(15)
    a.rts()
    a.nop()

    # ---- safe_text_close(R4=window handle) -------------------------------
    # Positive tagged handles go through the stock state machine. If the
    # expanded window has already released itself, finish the global cleanup
    # instead of dereferencing the NULL result of resolving handle -1.
    a.label("safe_text_close")
    a.cmp_pl(4)
    a.bt("text_close_valid")
    a.mov_l_pc("text_global_close", 0)
    a.jmp(0)
    a.nop()
    a.label("text_close_valid")
    a.mov_l_pc("text_close", 0)
    a.jmp(0)
    a.nop()

    return a


def build_record_stub():
    """The two instructions replaced in the layout loop, plus the stash.

    0x8C0600EA/EC originally read the line's atlas handle:

        MOV.W  @(disp,PC),R0     ; 0x188
        MOV.L  @(R0,R12),R7

    R12 is the line record, and the character codes the pen needs live in it.
    The stub does the original work and saves R12 on the way past.
    """
    a = sh4asm.Asm(PLACE_DEAD)
    a.long_("g_record", G_RECORD)
    a.long_("g_widen", G_WIDEN)
    a.long_("grid_create", GRID_CREATE)
    a.word_("off188", 0x0188)
    a.label("stub")
    a.mov_l_pc("g_record", 0)
    a.mov_l_store(12, 0)
    a.mov_w_pc("off188", 0)
    a.rts()
    a.mov_l_r0(12, 7)                    # delay slot: the original load

    # These call sites also construct small UI grids, including the 3x2
    # Yes/No selector. Expand only the two stock dialogue widths; doubling
    # every input turns that selector into 6x2 and puts "YesNo" on one row.
    # Preserve PR and tail-jump to the real grid allocator.
    a.label("column_stub")
    a.mov(5, 0)
    a.cmp_eq_i(17)
    a.bf("not_spoken")
    a.mov_i(textlayout.SPOKEN_COLS, 5)    # 33 * 3 = 99 transition cells
    a.bra("column_ready")
    a.nop()
    a.label("not_spoken")
    a.mov(5, 0)
    a.cmp_eq_i(19)
    a.bf("column_ready")
    a.mov_i(textlayout.NARRATION_COLS, 5) # shared width; opcode != window type
    a.label("column_ready")
    a.mov_l_pc("grid_create", 0)
    a.jmp(0)
    a.nop()

    # 0x8C060504 normally starts every cell 28 pixels after the previous one.
    # Expanded text grids would otherwise initialise unused nodes far beyond
    # the box. Visible glyphs are moved by the VWF hook, but unused nodes are
    # revisited by transitions such as PSI opcode 0x2B. Both text window
    # types now use 33 columns, at 14px pitch including the trailing quad.
    # The instruction after the hook remains the original FPU delay slot.
    a.label("pitch_stub")
    a.mov_i(28, 9)
    a.mov_w_atd_r0(8, 11)                # context+8 = columns
    a.extu_w(0, 0)
    a.cmp_eq_i(textlayout.SPOKEN_COLS)
    a.bf("pitch_done")
    a.mov_i(14, 9)
    a.label("pitch_done")
    a.rts()
    a.nop()

    # Normal-height row path only (ctx+14 != 1). Keep compact menus' separate
    # row*14 path and other grids' row*16 unchanged. R0 enters as row index;
    # R1 is scratch after the division helper. Return the integer Y to the
    # original LDS/FLOAT sequence without touching FPU state or cell counts.
    a.label("row_pitch_stub")
    a.mov(0, 1)
    a.mov_w_atd_r0(8, 11)
    a.cmp_eq_i(textlayout.SPOKEN_COLS)
    a.bt("row_pitch_text")
    a.cmp_eq_i(textlayout.NARRATION_COLS)
    a.bt("row_pitch_text")
    a.mov_i(16, 0)
    a.bra("row_pitch_multiply")
    a.nop()
    a.label("row_pitch_text")
    a.mov_i(textlayout.TEXT_ROW_PITCH, 0)
    a.label("row_pitch_multiply")
    a.mul_l(0, 1)
    a.sts_macl(0)
    a.rts()
    a.nop()
    return a


def float_table():
    return b"".join(struct.pack("<f", float(i)) for i in range(NTAB))


def font_image():
    """The font the metrics must describe.

    tools/latin.py writes a redrawn sheet to build/FONT.vwf.bin; the advance
    and bearing tables have to come from *that*, not from the stock font, or
    the pen will space narrow glyphs as if they were still full-width.
    """
    redrawn = os.path.join(ROOT, "build", "FONT.vwf.bin")
    if os.path.exists(redrawn):
        return redrawn
    return os.path.join(ROOT, "extracted", "FONT.BIN")


def metrics(exaggerate=None):
    """(advance, left bearing) per glyph, measured off the font sheet.

    `exaggerate` forces a constant advance on every glyph, which makes a first
    on-screen test unmistakable rather than subtle.
    """
    data = open(font_image(), "rb").read()
    adv = bytearray()
    bear = bytearray()
    for g in range(NGLYPH):
        e = W.extents(data, g)
        if exaggerate is not None:
            adv.append(exaggerate)
            bear.append(0)
        elif e is None:
            adv.append(W.SPACE_ADVANCE)
            bear.append(0)
        else:
            adv.append(min(255, (e[1] - e[0] + 1) + W.BEARING))
            bear.append(e[0])
    return bytes(adv), bytes(bear)



def apply(exaggerate=None):
    exe = bytearray(open(os.path.join(ROOT, "extracted", "1ST_READ.BIN"), "rb").read())

    def poke(addr, blob):
        off = addr - LOAD_BASE
        if off < 0 or off + len(blob) > len(exe):
            raise ValueError("%08X is outside the image" % addr)
        exe[off:off + len(blob)] = blob

    code = build_code()
    code_bytes = code.assemble()
    if CODE + len(code_bytes) > FLOAT_TAB:
        raise ValueError("code overruns the float table by %d bytes"
                         % (CODE + len(code_bytes) - FLOAT_TAB))

    stub = build_record_stub()
    stub_bytes = stub.assemble()
    if PLACE_DEAD + len(stub_bytes) > PLACE_END:
        raise ValueError("the record stub does not fit in the dead routine body")

    # the trampoline: 0x8C0603B4 becomes a jump to our replacement
    tramp = sh4asm.Asm(PLACE)
    tramp.long_("vwf_place", code.labels["vwf_place"])
    tramp.mov_l_pc("vwf_place", 0)
    tramp.jmp(0)
    tramp.nop()
    tramp_bytes = tramp.assemble()

    # the layout loop calls the stub instead of doing the load itself
    hook = sh4asm.Asm(REC_HOOK)
    hook.bsr("stub")
    hook.nop()
    hook.labels  # noqa - the label lives in the other assembly unit
    disp = (stub.labels["stub"] - (REC_HOOK + 4)) // 2
    if not -2048 <= disp <= 2047:
        raise ValueError("the record hook cannot reach the stub")
    hook_bytes = struct.pack("<HH", 0xB000 | (disp & 0xFFF), 0x0009)

    if EXPAND_TEXT_GRIDS:
        call_off = TEXT_CREATE_CALL - LOAD_BASE
        if bytes(exe[call_off:call_off + 2]) != TEXT_CREATE_CALL_OLD:
            raise ValueError("%08X does not hold the expected text-grid call"
                             % TEXT_CREATE_CALL)
        column_disp = (stub.labels["column_stub"] - (TEXT_CREATE_CALL + 4)) // 2
        if not -2048 <= column_disp <= 2047:
            raise ValueError("the text-grid call cannot reach the column stub")
        poke(TEXT_CREATE_CALL, struct.pack("<H", 0xB000 | (column_disp & 0xFFF)))
        for ptr in TEXT_CREATE_PTRS:
            ptr_off = ptr - LOAD_BASE
            if bytes(exe[ptr_off:ptr_off + 4]) != struct.pack("<I", GRID_CREATE):
                raise ValueError("%08X does not hold the expected text-grid pointer"
                                 % ptr)
            poke(ptr, struct.pack("<I", stub.labels["column_stub"]))

        pitch_off = GRID_PITCH_CALL - LOAD_BASE
        if bytes(exe[pitch_off:pitch_off + 2]) != GRID_PITCH_CALL_OLD:
            raise ValueError("%08X does not hold the expected grid-pitch setup"
                             % GRID_PITCH_CALL)
        pitch_disp = (stub.labels["pitch_stub"] - (GRID_PITCH_CALL + 4)) // 2
        if not -2048 <= pitch_disp <= 2047:
            raise ValueError("the grid-pitch call cannot reach the pitch stub")
        poke(GRID_PITCH_CALL, struct.pack("<H", 0xB000 | (pitch_disp & 0xFFF)))
        row_off = ROW_PITCH_CALL - LOAD_BASE
        if bytes(exe[row_off:row_off+4]) != ROW_PITCH_CALL_OLD:
            raise ValueError('unexpected row-pitch instructions at %08X' % ROW_PITCH_CALL)
        row_disp = (stub.labels['row_pitch_stub'] - (ROW_PITCH_CALL+4)) // 2
        if not -2048 <= row_disp <= 2047:
            raise ValueError('row-pitch hook cannot reach its stub')
        poke(ROW_PITCH_CALL, struct.pack('<HH',0xB000 | (row_disp & 0xFFF),0x0009))
    poke(PLACE, tramp_bytes)
    poke(PLACE_DEAD, stub_bytes)
    poke(REC_HOOK, hook_bytes)
    poke(CODE, code_bytes)
    if SAFE_TEXT_CLOSE:
        close_ptr_off = TEXT_CLOSE_PTR - LOAD_BASE
        if bytes(exe[close_ptr_off:close_ptr_off + 4]) != struct.pack("<I", TEXT_CLOSE):
            raise ValueError("%08X does not hold the expected text-close pointer"
                             % TEXT_CLOSE_PTR)
        poke(TEXT_CLOSE_PTR, struct.pack("<I", code.labels["safe_text_close"]))
    adv, bear = metrics(exaggerate)
    poke(FLOAT_TAB, float_table())
    poke(ADV_TAB, adv)
    poke(BEAR_TAB, bear)

    return exe, code, stub, len(code_bytes), len(stub_bytes)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "build"
    exaggerate = None
    if "--flat" in argv:
        exaggerate = int(argv[argv.index("--flat") + 1], 0)

    exe, code, stub, clen, slen = apply(exaggerate)

    if cmd == "disasm":
        sys.path.insert(0, HERE)
        import sh4dis
        data = bytes(exe)
        for addr, n in ((PLACE, 16), (REC_HOOK, 4), (PLACE_DEAD, slen),
                        (CODE, clen)):
            print("\n--- %08X ---" % addr)
            for line in sh4dis.disassemble(data, addr - LOAD_BASE, n):
                print(line)
        return 0

    out = os.path.join(ROOT, "build", "1ST_READ.vwf.bin")
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    open(out, "wb").write(bytes(exe))
    print("wrote %s" % out)
    print("  metrics from %s" % os.path.relpath(font_image(), ROOT))
    print("  hook code   %08X..%08X  (%d bytes, %d free before the float table)"
          % (CODE, CODE + clen, clen, FLOAT_TAB - CODE - clen))
    print("  record stub %08X..%08X  (%d bytes, dead body has %d)"
          % (PLACE_DEAD, PLACE_DEAD + slen, slen, PLACE_END - PLACE_DEAD))
    print("  float table %08X  %d entries" % (FLOAT_TAB, NTAB))
    print("  advances    %08X  %d glyphs%s"
          % (ADV_TAB, NGLYPH,
             "" if exaggerate is None else "  (forced to %d)" % exaggerate))
    print("  bearings    %08X  %d glyphs" % (BEAR_TAB, NGLYPH))
    print("  record      resolved by this cell's atlas handle (deferred-menu safe)")
    if EXPAND_TEXT_GRIDS:
        sites = (TEXT_CREATE_CALL,) + TEXT_CREATE_PTRS
        print("  columns     expanded (spoken 17->33, narration 19->33) at %s"
              % ", ".join("%08X" % site for site in sites))
        print("  grid pitch  compacted for expanded text grids at %08X"
              % GRID_PITCH_CALL)
    else:
        print("  columns     stock 17/19-cell grids (stability baseline)")
    if SAFE_TEXT_CLOSE:
        print("  text close  routes -1 handles to global cleanup at %08X"
              % TEXT_CLOSE_PTR)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
