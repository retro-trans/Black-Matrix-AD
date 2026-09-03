# Black/Matrix AD — text engine

Everything below is read out of `1ST_READ.BIN` with `tools/sh4dis.py`.
Addresses are Dreamcast RAM; `1ST_READ.BIN` loads at `0x8C010000`, so
`file offset = address - 0x8C010000`.

## Font format

`0x8C05DD1A` — character index to glyph address:

```
EXTU.W R4,R4          ; glyph index
MOV.L  @(...),R3      ; R3 = 0x8C1D8318
SHLL2  R4 ; SHLL2 R4
MOV.L  @R3,R0         ; R0 = *(0x8C1D8318) = font base
SHLL2  R4 ; SHLL  R4  ; index * 128
ADD    R4,R0
RTS
ADD    #16,R0
```

    glyph = *(0x8C1D8318) + index * 128 + 16

`0x8C05D486` stores the base once, and it is a hardcoded address, not an
allocation:

    *(0x8C1D8318) = 0x8C75F800

Each 128-byte record is **two 16x16 tiles of 64 bytes**, 2 bits per pixel,
four pixels per byte with the most significant pair leftmost. Maximum index is
4608, so the sheet is `4608 * 128 + 16` = 589,840 bytes, and it starts with a
16-byte header whose magic is `"MFD "`.

Confirmed layout, verified by re-rendering 「表示速度を遅くします。」 from the
dump and matching it against the game's own config screen:

- glyph cell is **24 wide x 16 tall**
- tile 0 covers x 0..15, tile 1 covers x 16..23 (tile 1's right half is unused)
- pixel order inside a tile is PowerVR **twiddled**, `morton(y, x)` — y goes
  into the low bits of the interleave
- pixel values: 0 transparent, 1 the main ink, 2 and 3 anti-aliasing

The blit at `0x8C05DC42` copies the two tiles to `dst+0` and `dst+256`, which
is what puts them side by side once the destination is read as a twiddled
texture.

Note the SJIS slots that are unassigned in the standard (`8240`-`824E`,
`825C`, `827D`-`8280`, `829B`-`829D`, `81AF`-`81B7`) are **not blank** here:
they hold the game's gaiji, the JIS level-2 kanji it needs. That is why a disc
scan keyed on "blank cells before the digits" found nothing.

## SJIS to glyph index

`0x8C05DD2E`. Three ranges, each a plain 16-bit add (wrapping):

| SJIS range      | add      | glyph index   |
|-----------------|----------|---------------|
| `8140` – `81BF` | `+0x7EC0`| 0 – 127       |
| `8240` – `83BF` | `+0x7E40`| 128 – 511     |
| `889F` – `9872` | `+0x7961`| 512 – 4563    |

Anything else passes through unchanged, and `0x8C05DC42` rejects any index
`>= 0x1200` (4608). Checks: `8140` (full-width space) wraps to index 0, and
`889F` (亜, the first kanji) lands on 512.

Note this means glyph indices 128–142 correspond to SJIS `8240`–`824E`, which
are unassigned, and 143–152 are the full-width digits `０`–`９`.

## Line records

32 records live at `0x8C1D5018`, stride `0x190` (400 bytes):

| offset  | type    | meaning                          |
|---------|---------|----------------------------------|
| `+0x000`| u16     | character count on the line      |
| `+0x004`| u16[192]| the characters themselves        |
| `+0x184`| u16     | flags (`0x0800`, `0x4000`, `0x8000`) |
| `+0x186`| u16     | size of the owned bitmap buffer  |
| `+0x188`| ptr     | the bitmap buffer                |
| `+0x18C`| ptr     | next record                      |

192 characters per line is the same 192 that `0x8C05DC42` range-checks the
column index against.

## Rendering path

- `0x8C06006E` — cursor / line layout. Compares each character against
  `0xA0FF` at `0x8C06012C`; that literal appears exactly once in the binary,
  which is what identified this routine.
- `0x8C05D934` — computes the byte size of a line's bitmap.
- `0x8C05E060` — allocates the line buffer, then loops the characters calling
  the per-glyph draw.
- `0x8C05DC0E` — column index to destination address:
  `table[seg] + n*256 - (128 if index is odd)`, table at `0x8C1E7740`.
- `0x8C05DC42` — the blit. Expands 2bpp source to 4bpp destination, adding a
  colour built as `attr * 17 * 0x101`.
- `0x8C05E364` — frees a line's records and buffers.
- `0x8C090944` — plain memcpy (used to install the font, so the font is **not**
  compressed on disc).

## The destination: a glyph atlas, not a text strip

Confirmed by decoding the game's own composed buffer out of a live RAM dump
while the config screen's help line was on screen.

A line is composed into one or more **4bpp palettised twiddled PVR textures**
(data format `0x05`). For an 11-character line the game built:

    PVRT @8C1D8F80  64x64     8 character slots
    PVRT @8C1E0FA0  32x32     2 slots
    PVRT @8C1E2FC0  32x32     2 slots

The table at `0x8C1E7740` holds 8 pointers: entries 0-3 are the pixel data,
entries 4-7 the PVR headers 16 bytes earlier.

Within a texture, character *k* is written at

    offset = within_segment*256 - 128*(k & 1)

and the blit puts its two tiles at `+0` and `+256`. Running those through the
twiddle, character *k* lands on tiles `(0,k)` and `(1,k)` - so **each character
occupies its own 32x16 cell**, and the cells stack down the texture (a 64x64
segment is a 2x4 grid of them). Characters are *not* laid out horizontally.

The line record's `+0x186` size field is in units of two characters (11
characters reported 6), and `+0x188` is a segment handle, not a pointer.

## Where a character is actually positioned

The compositing path carries no X position, so placement happens where the
quads are emitted.  `0x8C06006E` walks the line one character per call and
hands each to `0x8C0603B4`:

    0x8C0603B4(ctx, cell_index, index_in_record, atlas_handle, attr)

which fetches a **cell node** through `0x8C06BC44(*ctx, cell_index)`, copies
the node's position into the draw command at `0x8C0FED0C`, and tail-jumps to
`0x8C06BEB8` to dispatch it.

`0x8C06BC44` validates `window_id < 192`, indexes a 28-byte table at
`0x8C22B4D8`, requires flag `0x8000` in the entry's first u16, bounds-checks
against the count at `entry+4`, then walks a list from `entry+24` following
`+164`.  The window entry also holds the window's screen origin:

| offset | meaning |
|--------|---------|
| `+0`   | u16 flags: `0x8000` live, `0x0008` uniform character grid |
| `+4`   | u32 cell count |
| `+8`   | float origin X |
| `+12`  | float origin Y |
| `+24`  | first cell node |

### The cell node

168 bytes, `+164` chains to the next.  The important part is a **quad in
window-local coordinates**, corner by corner:

| offset | meaning |
|--------|---------|
| `+0`   | u16 flags: `0x8081` occupied, `0x8000` empty |
| `+8`   | index within the line record |
| `+12/+16` | top-left      x , y  |
| `+20/+24` | top-right     x2, y  |
| `+28/+32` | bottom-right  x2, y2 |
| `+36/+40` | bottom-left   x , y2 |
| `+84..+116` | the same four corners in screen coordinates (local + origin) |
| `+148..+164` | four (u,v) pairs, u16 8.8 fixed, normalised to the atlas |

Verified against a live RAM dump with the config screen up.  Window 3 is that
screen's help line: 38 cells, 19 columns of 28x14 at a 16-pixel row pitch,
cells 0..10 occupied by the 11 characters of 「表示速度を遅くします。」.  The
UVs step by `0x40` per character in v (16/64 of a 64x64 atlas segment) and by
`0xE0`/`0x70` once the line spills into the 32x32 segments - exactly the
per-character atlas cells described above.

Poking `100.0` into `node+12` of a live cell moved its rendered corner to
`154.0`, which is `100 + 54`, the window origin.  **That is the whole hook
point for a variable-width font.**

## The variable-width font

Implemented in `tools/vwf.py`; it assembles with `tools/sh4asm.py` and is
verified by disassembling its own output.

Because each glyph already sits in its own atlas cell, a VWF needs no change
to the font, the atlas, the blit or the UVs.  It only has to move each
character's quad.  Characters keep their full 28-pixel cell and simply overlap
into their neighbour's transparent margin.

The pen puts every glyph's *ink* where the previous glyph's ink ended:

    origin = bearing(first glyph on the row)
           + sum of advances of the characters before this one
           - bearing(this glyph)

    advance = ink width + 1        bearing = leftmost inked column

At column 0 the two bearings belong to the same character and cancel, so every
row starts exactly where the game put it.  The result is recomputed from
scratch on each call, so the patch is idempotent - it can run over an
already-shifted grid and give the same answer.

Three hooks:

| address | change |
|---------|--------|
| `0x8C0603B4` | replaced by a trampoline to the new routine; its old body is dead space |
| `0x8C0600EA` | `BSR` to a stub in that dead space, which saves the line record pointer and then does the load it replaced |
| `0x8C0F546C` | the new routine, in unused zero space at the tail of the image |

The stub is needed because `0x8C0603B4` is given the character's *index*, not
its code; the record pointer lives in R12 at the call site.

Two guards keep it off anything that is not a character grid: the window
entry's `0x0008` flag, and a sanity check that the node's own X coordinates
are integers found in the routine's float table.  The config screen's option
labels are a `0x8001` window of whole-string quads at irregular positions, and
they are correctly left alone.

No FPU arithmetic is used.  Floats are read out of a table of the first 640
integers, and the integer value of a float already in a node is recovered by
scanning that same table, so FPSCR is never touched and no FP register is
clobbered.

Memory used, all of it runs of zeros that were still zero in a RAM dump taken
after the game had booted and run:

    0x8C0F546C   452 bytes   the routine
    0x8C0F5800  2560 bytes   floats 0.0 .. 639.0
    0x8C0F0E50  4608 bytes   advance per glyph
    0x8C0F3464  4608 bytes   left bearing per glyph

The existing Latin glyphs are *full-width* forms averaging 16.4px of ink in
the 24px cell, so they only gain about 1.46x.  Redrawing them as narrow forms
is what turns that into the 2.5-3x an English script needs.

## Ink values

Value 1 is the solid ink; 2 and 3 are anti-aliasing. Counted over 400 kanji,
value 1 is 92% of all inked pixels and 95% of the pixels in the *interior* of
a horizontal stroke, while 2 and 3 cluster at stroke ends:

    interiors   1: 15253   2: 813   3: 58
    ends        1:  3617   2: 1152  3: 681

Which of 2 and 3 is the lighter shade cannot be told from the sheet - the blit
at `0x8C05DC42` turns a source pixel into destination nibble `value + attr`,
so the ordering lives in a palette that has not been read. `tools/latin.py`
therefore writes only value 1. At a 9-pixel cap height that is crisp rather
than mushy, and it is guaranteed correct.

Note `fontdump.LEVELS` renders 2 brighter than 1, which is only a preview
ramp and does not match this.

## The redrawn Latin

`tools/latin.py` replaces the full-width Latin with narrow proportional forms
rendered from a system TrueType font. Glyphs go into the full-width SJIS
slots, so English is encoded as full-width SJIS and the game's own character
decoder is untouched:

    0-9   SJIS 824F-8258   glyph 143-152
    A-Z   SJIS 8260-8279   glyph 160-185
    a-z   SJIS 8281-829A   glyph 193-218
    punctuation             the full-width ASCII forms

The vertical band is the only real constraint, and it is worth filling. The
first attempt used Tahoma at 12px, which needs only 12 rows, and on screen it
read as too condensed.

Stock, the renderer samples **14** of the cell's 16 rows, which caps a capital
at 11 rows however the font is chosen - against Japanese glyphs that fill 13.
That is why English looked short next to it. No glyph in the sheet, in any of
the 4608 slots, has ink in rows 14 or 15, so the patch widens the sample to
the whole cell (see "Widening the sample" below) and **rows 0..15** are
available. Verdana at 17px then puts capitals on rows 1..12 against the
Japanese 0..12.

Lines are 16 pixels apart and the quad is now 16 tall, so consecutive rows of
English leave exactly one blank row between them - tight next to Japanese,
which leaves three. Dropping a point size buys leading back if that reads
badly.

`choose_baseline` fits a font into the band, preferring the baseline of the
font being replaced (y=11) so English and Japanese sit on the same line, and
moving up only when a font's descenders are deeper.

The default is **Verdana**, stretched horizontally by 1.3.

Height is the binding constraint and width is not, which is worth knowing
before reaching for a different face. With the sample widened the glyphs use
rows 0..15 - the entire budget - while the widest of them is 19 pixels of a
24-pixel cell and the mean is 10. That imbalance is why the text first looked
tall and thin. The glyph record actually stores 32 columns (two 16x16 tiles),
so there is even more room than the 24 the cell nominally uses.

Glyphs are drawn at four times the target size and scaled back down before
thresholding, which gives much better stroke weight than rasterising directly
at 12 pixels. Doing it that way also makes the stretch free: the vertical
scale stays 4:1 while the horizontal becomes 4/1.3.

`build()` steps the point size down until the whole character set fits the
band, so asking for a size that is too tall costs a little size rather than a
clipped descender.

Alternatives, measured against the same sample sentence, which is 2464 pixels
at the fixed 28-pixel pitch:

Cap heights, with the sample widened to 16 rows:

| font | size | cap rows | note |
|---|---|---|---|
| **Verdana** | **17** | **12** | the default |
| Tahoma 17 | 17 | 12 | narrower |
| Trebuchet 17 | 17 | 12 | |
| Franklin Gothic Medium 19 | 19 | 13 | exact parity with the Japanese, but bold |
| Segoe UI 16 | 16 | 11 | |

`tools/latin.py preview` compares faces without booting anything, and
`build/height_compare.png` renders each against a line of the game's own
Japanese.

Georgia is the closest match to the game's serif UI, but its figures are
oldstyle: 0123 vary in height. In a tactical RPG full of damage and stat
numbers that is a functional defect rather than a matter of taste.

The font sheet is stored raw in `SYSTEM.DAT` at file offset `0x424E0`, so
installing it is a straight overwrite followed by `tools/inject.py`.

### Widening the sample, and where it has to happen

A cell node's quad is 14 pixels tall and its UVs span 14 of the 16 rows of the
atlas cell (`0x38` of a `0x40` step in a 64-pixel segment, `0x70` of `0x80` in
a 32-pixel one). The hook rounds both up to the whole cell:

    quad bottom = quad top + next power of two >= (bottom - top)
    v of corners 2 and 3 = v of corner 0 + next power of two >= (v2 - v0)

Rounding *up to* rather than *past* a power of two is what keeps it
idempotent - a second pass over an already-widened node changes nothing.
Existing text is unaffected because rows 14 and 15 are blank in every one of
the 4608 stock glyphs.

**This has to run after `0x8C06BEB8`, not before.** That routine rebuilds the
node from the command: it writes the quad from the position plus a fixed cell
size, and it writes the character's UVs. Anything the hook puts there first is
discarded. The pen position survives only because it travels *through* the
command - `0x8C0603B4` copies `node+12` into `cmd+36` and the dispatcher
copies it back - so it looks like node writes stick when they do not.

The tell was already in a RAM dump: an **empty** cell node has its local quad
set but its UVs zero. The quad is grid data written once; the UVs are written
when a character is placed.

So the hook calls the dispatcher instead of tail-jumping to it, and repairs
the node afterwards. Getting this half right is very visible: widening only
the UVs squeezes 16 rows of texture into a 14-pixel quad, which drops pixels
from the top and bottom of every letter.

## Cell positions, and the column count

`0x8C060504(ctx, first, count)` clears a window's cells and places each one.
For cell *i*, reading `cols` from `ctx+8`:

    x = (i mod cols) * 28
    y = (i div cols) * 14      when ctx+14 == 1
        (i div cols) * 16      otherwise

The pitch constants are immediates in the routine (`MOV #28,R9`,
`MOV #14,R8`), independent of `cols`. It converts each with `LDS`/`FLOAT`,
builds the quad in the command struct - position, then the far corners by
adding the cell size held in FR15 and FR14 - and sends message 9 to the node
through `0x8C06BEB8`.

So **a row holds exactly `cols` cells**. That, not any measuring, is what
capped a line at 17 characters: there is no node to put an 18th character in.

### Raising it

`cols` reaches the context through `0x8C0602D6(ctx, cols, rows)`, which stores
it at `ctx+8` *and* multiplies it by `rows` for the allocation, so scaling it
there scales both together. There are three text-window creation paths: a
direct call at `0x8C05FD3C`, plus indirect calls whose allocator pointers are
stored at `0x8C05E4C4` and `0x8C05EB10`. All three are redirected through a
small stub. It recognizes the stock window widths and raises spoken dialogue
from 17 to 33 columns and narration from 19 to 38. Spoken windows have three
rows, while the open/close transition object at `0x8C08AF7A` contains only 100
per-cell state slots. Thus 33 * 3 = 99 is the hard safe maximum; the former
42-column experiment allocated 126 cells and corrupted the transition state.
Narration has two rows, so 38 * 2 = 76 remains safe. Wrapping still stops at
476 pixels.
The extra cells sit off the right of the box,
which does not matter: the VWF hook overwrites every X, and only which row a
cell lands on - `i div cols` - still has to be right, and it is.

The stock grid initializer originally left the unused doubled cells far off
screen, reaching `x=1036` and `x2=1064` in a 38-column row. Visible glyphs were
repositioned by the VWF hook, but unused cells retained that geometry and were
revisited by the `0x2B` screen-fade transition after the sixth narration line.
That consistently killed Redream's rendering window. The `MOV #28,R9` at
`0x8C060544` is now routed through a small conditional stub: 33- and
38-column text grids use a 14-pixel initialization pitch, while ordinary grids
keep 28. This contains every expanded text node within the stock horizontal
span; the VWF still assigns final visible positions.

The stub preserves the BSR return address and tail-jumps to the real allocator:

    CMP/EQ #17,R5 / #19,R5
    MOV    #33,R5 / #38,R5
    JMP   0x8C0602D6
    NOP

The indirect paths matter for narration: every text-window creation path must
allocate the same number of cells assumed by the script wrapper. A mismatch can
render the first translated lines and then overrun the window's per-cell state,
producing a black screen or a stalled scene. The current patch routes all three
known text-window call sites through the same gated sizing stub and keeps each
window type within the transition object's 100-slot limit.

The close poll at `0x8C08C7AC` passes the active window handle to
`0x8C08AF52`. With an expanded grid, the window can finish releasing before
the next poll and leave `0x8C263B04` at `-1`. The stock helper resolves that
invalid handle to NULL and dereferences it. The patched pointer at
`0x8C08C828` therefore routes non-positive handles to the stock global cleanup
routine at `0x8C06B2DC`; positive tagged handles still use the original close
state machine. Returning without that cleanup is also unsafe because it leaves
the following scene half-initialized.

Text teardown at `0x8C08C7AC` must remain stock. Its indirect target
`0x8C08AF52` closes global text state and does not consume the value placed in
R4 by the call's delay slot. Treating a negative R4 as an already-closed window
and returning early leaves scene state partially alive: first the portrait can
remain without a text box, and the following scene entry can reset the game.

### The float table and off-screen grid cells

The first VWF hook recovered a cell's width by scanning `FLOAT_TAB` for its X
coordinates. That made the table cover off-screen grid positions rather than
visible pen positions: at 34 columns, cell 22 already had `x2 = 644`.

Uniform character-grid windows carry flag `0x0008`, and their builder uses a
fixed 28-pixel cell width. The hook now uses that known width directly instead
of scanning X coordinates. `FLOAT_TAB` remains 1024 entries for output pen
positions and the small Y-coordinate scan used by the 16-row height fix. This
allows 33/38 allocated cells per row without needing a large X-coordinate table.

## Line breaking

Two rules, both learned from the screen:

- **The engine wraps by cell count and ignores word boundaries.** It will
  split "worry" across two rows. The patch allocates 33 cells for spoken text
  and 38 for narration, while `tools/patchline.py` also wraps on spaces at the
  original 476-pixel window width.
- **A break after a row that is already full skips a row.** The break sets
  `next = (cell / cols + 1) * cols`, and after exactly `cols` characters the
  cursor has already moved to the next row, so the break moves it again. A
  full row needs no break; dropping the space at the same point keeps the
  following row flush left.

The script wrapper measures the same generated font image that `vwf.py` uses
for its advance table, keeping build-time line decisions and runtime placement
in sync.

## PSI instruction alignment

PSI text records can move, but every replacement must preserve its original
size modulo four. The typed-operand reader at `0x8C08BC96` aligns 32-bit
payloads from the live program pointer; padding embedded by the original PSI
compiler is therefore only correct while the containing instruction retains
its original modulo-four address. An earlier repacker version allowed a text
record to change size by two modulo four. After the sixth narration line this
moved opcode `0x2B` by two bytes, causing its intended value `2` to be read as
`0x00020000`; the fade remained black indefinitely.

`tools/scriptpack.py` now appends one invisible full-width space when a
translation's u16 count has different parity from the original record. Thus
each replacement changes the program by a multiple of four bytes, preserving
the alignment of every later opcode and typed operand.

## PSI2 statement grammar and branch relocation

The full statement grammar — dispatch tables, operand readers, the
expression encoding, and the three statements that embed branch targets
(`0x02`, `0x03`, `0x1D`, all storing file offset minus 0x10) — is
documented in `tools/psi2.py`, which decodes every group and is validated
against the whole original SCENARIO.DAT (`python tools/psi2.py check`).
PSI2 has no labels; the six-byte pattern an earlier repacker treated as a
label marker is the tail of an ordinary expression. `tools/scriptpack.py`
relocates every branch-target operand through that decoder and re-walks
each rebuilt group before accepting it.
