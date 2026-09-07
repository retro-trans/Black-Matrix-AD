# Handoff — Black/Matrix AD translation project

> **Start here (2026-09-07):** [current consolidated handoff](HANDOFF-2026-09-07.md)
> covers the complete change set, build/test evidence, local prerequisites,
> pending Flycast checks, and the current 93-choice backlog. Counts and
> diagnoses in older entries below are historical snapshots.

> **Activity/field UI update 2026-09-05:** the build now includes cooking,
> cleaning and woodcutting prompts; cooking/woodcutting control graphics;
> Save/Load/Setup field-menu rows; and six route gate confirmations.
> Gate responses fit the 15-cell choice slots, and Prague's question wraps
> to two lines. See `docs/activity-ui.md` for offsets and implementation.
> Full build: 10,298 translated records, 5,252 relocated targets; 15 tests pass.
> The unrelated overlong-choice backlog is now 93, down from 105.
> Rebuilt/injected Disc 1 CUE is in `build/disc`; cold-boot play test pending.

> **Update 2026-09-05: fixes implemented and rebuilt; cold-boot play test pending.**
> Both library issues below now have targeted fixes. `tools/vwf.py` resolves
> each placement's live line record by its atlas handle instead of reading the
> shared `G_RECORD`. Replaying the emitted SH-4 on the user's captured 98-cell
> menu corrects all 82 incorrect X positions. The AP reset was a decoder error:
> mode-3 sub `0x23` takes **one** expression, not two. The second supposed
> expression swallowed the following exit jump, preventing its relocation.
> In group 106 the field at `0x9C` now targets file offset `0x5A32` (return)
> instead of `0x2FB2` (inside translated text). All 501 programs and 7,533
> branch destinations verify against the original control flow. Nine regression
> tests pass (`python -m unittest discover -s tests -v`). See the new top section
> in `docs/HANDOFF-2026-09-04-book-menu-ap-lock.md` for evidence and retest steps.
> The 105 overlong choice labels elsewhere remain a separate backlog.
>
> The 2026-09-04 notes below are historical; in particular, their assertion that
> every AP-path branch was already relocated was based on the faulty decoder.

> **Open issues (2026-09-04), both in the occult-library shelf scene — full
> detail in `docs/HANDOFF-2026-09-04-book-menu-ap-lock.md`:**
>
> 1. **Choice-menu glyph overlap** (cramped text like "Si n: Freedom"). The VWF
>    positions the menu's cells during the open animation (deferred), by which
>    time the global "current record" pointer has moved to an empty record, so
>    advances are read from the wrong data. Confirmed with a live capture. No
>    safe flag-gate exists (the AP box shares the window flag and renders fine);
>    needs a per-window record fix or non-deferred menu placement.
> 2. **`AP: LOW!` dismissal hard-resets the machine** (Dreamcast logo), and the
>    behaviour flips freeze↔reset with tiny group-106 layout changes — i.e. the
>    interpreter is dispatching a bad offset at runtime (all branch targets are
>    static-valid). The `-1` close-handle fix did NOT resolve it. The exact
>    faulting PC is still needed; flycast's GDB stub does not work on this build.
>
> **Fixed (2026-09-04):** the occult-library menu's stale *trailing* glyph (the
> "V" at every row's right edge) — a separate defect from the overlap. Root
> cause: PSI2 choice options store at a fixed 15-unit stride but the menu width
> is the uncapped longest option, so any option over 15 units over-reads into the
> next option's slot. The four long occult labels are shortened, and
> `tools/scriptpack.py` now warns on any `st 0x1D` option over 15 stored units.
> **105 other menu options across the game still exceed the limit**
> (`docs/menu-labels-over-15.txt`) and need a shortening pass.

> **Update (2026-09-04):** the Prague cabin scene restart was root-caused to
> unrelocated PSI2 branch targets in the repacker and fixed — see
> `docs/HANDOFF-2026-09-04-scene-restart.md`. The current build awaits a play
> test. Anything below about "labels" or relocated label references is
> superseded: PSI2 has no labels; `tools/psi2.py` decodes the real statement
> grammar and `tools/scriptpack.py` relocates every branch-target operand.

Dreamcast, Japanese, being translated to English.

The original disc images in the project root are **untouched**. All patching
happens against a copy in `build/disc/`, which is edited in place.

Read `docs/text-engine.md` before changing anything. It has the whole model of
how text reaches the screen, and every constant in it was verified against the
running game rather than assumed.

## Where things stand

The rendering side is **done and verified in the running game**. English
dialogue displays correctly spaced, at a sensible size, on one line:

- **Variable-width font.** Each glyph's ink starts where the previous glyph's
  ink ended. Recomputed from scratch per call, so it is idempotent. No FPU
  arithmetic, so FPSCR and the FP registers are never touched.
- **Narrow Latin.** The full-width Latin is replaced with proportional forms
  rendered from Verdana, stretched 1.3x horizontally. A sample sentence that
  is 2464 pixels at the game's fixed 28-pixel pitch is 849 with the new font
  and pen — **2.9x**.
- **Full-height glyphs.** The renderer sampled 14 of the atlas cell's 16 rows,
  which capped a capital at 11 rows against Japanese glyphs that fill 13. It
  now samples all 16, and capitals match.
- **Row capacity.** A row held 17 characters because a window owns exactly
  `columns * rows` cell nodes. All three text-window construction paths expand
  the column count, giving spoken rows 33 cells and narration rows 38; visual
  wrapping still uses the original 476-pixel width. Spoken windows have three
  rows, and the engine's transition object has 100 per-cell slots, making
  33 * 3 = 99 the safe maximum. Expanded grids use a 14-pixel initialization
  pitch so unused nodes stay inside the stock span during transitions.
- **Line breaking.** `tools/patchline.py` measures generated glyph advances,
  wraps on word boundaries at 476 pixels, and avoids the full-row break that
  used to skip a row.

**Script repacking is implemented.** `tools/scriptpack.py` rebuilds variable-
length text records, relocates PSI2 labels and references, rebuilds the CMP2
sector table, preserves the original modulo-four instruction alignment, and
verifies every translated and untouched logical group. The 307 translated
intro records can now exceed their Japanese record lengths. Alignment is
preserved with an invisible trailing space when a translated record's u16
count has different parity; without it, PSI's aligned 32-bit operand reader
can read from the middle of a value and stall the script.

`SCENARIO.DAT` has no free sectors before `SOUND.DAT`, so the complete build
relocates it to verified free space at LBA 50,000. All 562 logical groups,
including the 60 unused `0x11` placeholders, remain physically sequential.
They must not share a sector: the runtime starts each CMP2 group at the
previous table entry's cumulative end, even though `end - count` looks like
an equivalent start offset in an original contiguous archive.

**Terminology and speakers are enforced.** `script/glossary.tsv` is the
canonical Japanese-to-English term list. English source text marks a term as
`$$Japanese term ID$$`; the build expands every marker from the glossary, so a
canonical translation can be changed once without editing dialogue records.
Unknown/malformed markers, unmarked source terms, and markers absent from the
Japanese line stop the build before repacking.

`script/speakers.tsv` records the confirmed character for every translated
TALK/NARR range, along with Japanese register, English voice guidance, and a
research URL. The current masters are Domina, Prica, Courreges, Michette,
Prague, and Zero; narration is Abel. A translation with no confirmed speaker
also stops the build. The mostly-zero voice IDs are not treated as identity
evidence. `tools/build_script.py` writes the resolved name into the `speaker`
column of every bilingual row.

### Screenshots worth keeping

| shot | what it shows |
|---|---|
| `build/shot_config.png` | the config help line, unpatched — the baseline |
| `build/shot_dlg2.png` | the VWF working on the original Japanese |
| `build/shot_cols.png` | current build |
| `build/jp_en_height.png` | English against Japanese in one frame, matched heights |
| `build/final_compare.png` | first font attempt vs current, zoomed |
| `build/wide_compare.png` | 1.0 / 1.15 / 1.3 horizontal stretch |
| `build/height_compare.png` | candidate faces against a line of the game's Japanese |
| `build/latin_preview.png` | the redrawn glyphs, decoded back out of the font sheet |
| `build/shot_repack_intro.png` | first variable-length translated PSI2 record live in redream |

## The build loop

    python tools/build.py
    powershell -ExecutionPolicy Bypass -File tools\runcfg.ps1 -Out build\shot.png

`build.py` runs every step in the one correct order and injects into the disc
copy. **Do not run the steps by hand** unless you have read why the order
matters: `vwf.py` bakes a per-glyph advance and bearing into the executable and
those must describe the font that actually ends up on the disc. Building the
executable before redrawing the font gives wide gaps between letters and a tiny
word space — it looks like a VWF bug and is not one.

Useful switches:

- `tools/build.py --font tahoma.ttf --size 14 --wide 1.0` — different typeface
- `tools/latin.py preview` — compare faces without booting anything
- `tools/latin.py install --mark` — draws a bar in glyph rows 14-15, which are
  blank in every stock glyph. If the bar shows on screen, the widened sample
  is live in that window. This is how the UV problem below was found.
- `tools/vwf.py build --flat N` — forces a constant advance on every glyph, the
  quickest way to prove the hook is firing at all
- `tools/vwf.py disasm` — disassembles what the assembler just emitted

## Tools

| tool | what it does |
|---|---|
| `tools/build.py` | **runs the whole build in the right order** — start here |
| `tools/latin.py` | redraw the Latin glyphs; `preview` to compare faces |
| `tools/vwf.py` | build the VWF patch; `disasm` reads back what it emitted |
| `tools/sh4asm.py` | SH-4 assembler: labels, literal pools, branch relaxation |
| `tools/sh4dis.py` | SH-4 disassembler, resolves PC-relative literals inline |
| `tools/inject.py` | list/read/write a file inside the GD-ROM track, in place |
| `tools/patchline.py` | replace one script line in `SCENARIO.DAT`, same length |
| `tools/scriptpack.py` | rebuild translated PSI2 programs and the CMP2 sector table |
| `tools/glossary.py` | enforce canonical terms against the Japanese source lines |
| `tools/terms.py` | expand `$$Japanese term ID$$` controls from the glossary |
| `tools/progress.py` | report full-game translation coverage by text kind and PSI group |
| `tools/uistr.py` | list/patch the UI string table inside `1ST_READ.BIN` |
| `tools/fontdump.py` | extract/verify/render the font sheet |
| `tools/widths.py` | per-glyph ink extents and advances |
| `tools/cells.py` | walk the window table and cell nodes in a RAM dump |
| `tools/bmtext.py` | ISO listing, file extraction, script text dump |
| `tools/pac.py` | list/extract CMP2 + PAC archive members |
| `tools/gfx.py` | PNG writer, PVR decode, 1/2/4bpp renderers |
| `tools/build_script.py` | merge English TSV against live Japanese and annotate speakers |
| `tools/runcfg.ps1` | boot the patched disc and drive it to the config screen |
| `tools/shot2.ps1` | screenshot redream **without** focus — use this one |
| `tools/shot.ps1` | screenshot by copying the screen — needs focus, avoid |
| `tools/dumpram.ps1` | dump live Dreamcast RAM (see the RAM gotcha) |
| `tools/pokeram.ps1` | write live Dreamcast RAM — **data only**, see gotchas |
| `tools/findram.ps1` | locate Dreamcast RAM by searching for the game's code |
| `tools/watchram.ps1` | sample one address repeatedly, for per-frame values |
| `tools/rawread.ps1` | read at the logged RAM base with no sanity check |

## Next steps, in priority order

1. **Run through every translated intro route.** The repacker validates the
   archive structure, the rebuilt disc boots, and the first translated record
   has been verified in redream. The remaining character routes and both
   chapter-choice branches still need an end-to-end playthrough.
2. **Anti-aliasing in the new glyphs.** Only ink value 1 is written, because
   which of values 2 and 3 is the lighter shade depends on a palette that has
   not been read. Needs the RAM problem solved. Would soften the letterforms.
3. **Disc rebuild for distribution.** `inject.py` rewrites files in their own
   sectors and does not recompute EDC/ECC, which redream does not check. Real
   hardware does. Anything meant for a console needs an EDC/ECC pass.

## Gotchas that cost real time

**Emulator and testing**

- **redream JIT-compiles SH-4 blocks, so poking code into its live RAM does
  nothing.** The write lands, the behaviour does not change. *Data* pokes work
  fine and are how the cell-node layout was confirmed. Code changes have to go
  through the disc, which `inject.py` makes cheap — no image rebuild, the file
  is rewritten where it lies.
- **Reading redream's memory only works for instances a human launched — this
  is unsolved.** For a redream started from here, the game's code cannot be
  found *anywhere* in the process: `findram.ps1` scans every readable committed
  region (~1100 regions, 736 MB) and comes up empty while the patched game is
  demonstrably running and drawing. A hand-launched instance reads fine at the
  base its log reports. What differs was never worked out. Verify visually with
  `shot2.ps1` instead; RAM dumps need a hand-launched emulator.
- **Use `shot2.ps1`, not `shot.ps1`.** `shot.ps1` copies from the screen and
  photographs whatever overlaps redream. `shot2.ps1` uses `PrintWindow` with
  `PW_RENDERFULLCONTENT`, needs no focus, works while the window is buried, and
  does not interrupt anyone.
- **Never send keys without knowing what is on screen.** The sequence that
  reaches Config from the title will start a New Game if the game is elsewhere.
  Screenshot first, or use `runcfg.ps1`, which relaunches so the state is known.
- **Winning the focus check is not sufficient.** Keys have been observed to
  reach nothing with redream in the foreground. Always confirm with a
  screenshot rather than assuming a sequence landed.
- **The title menu remembers its cursor.** It *clamps* at the top rather than
  wrapping, so three ups then two downs always reaches Config.
- **Start redream with `-NoNewWindow`** from PowerShell here, or the launcher
  exits immediately and no emulator comes up.
- redream's internal-resolution upscaling is a paid feature, and it would not
  help the text anyway: glyphs are texels in a fixed atlas, so upscaling
  magnifies and filters them rather than adding detail.

**Toolchain**

- **PowerShell 5.1 parses `0x8C000000` as a negative Int32.** Spell SH-4
  addresses as `[uint64]2348810240` or every offset is silently wrong.
- **The project's Python is 32-bit** and cannot read a 64-bit process's address
  space at all — `VirtualQueryEx` returns 0. Memory work has to be PowerShell.
- **Backslashes get mangled through Bash heredocs here.** Write Python with the
  Write tool, not `cat <<'EOF'`. `"\n"` arrives as a real newline and silently
  breaks string literals. This bit twice.
- **File offset vs memory address.** `1ST_READ.BIN` loads at `0x8C010000`;
  `file = addr - 0x8C010000`.

**Traps specific to this patch**

- **The dispatcher rebuilds the node after the hook runs.** `0x8C06BEB8` writes
  the quad from the command position plus a fixed cell size, and writes the
  UVs. Anything the hook sets *before* calling it is discarded. The pen
  survives only because it travels through the command's own X field. So the
  hook calls the dispatcher and repairs the node afterwards. Getting half of it
  right is very visible — widening only the UVs squeezes 16 rows of texture
  into a 14-pixel quad and drops pixels from every letter.
- **Do not scan off-screen X coordinates through the float table.** That older
  approach broke at 34 cells when cell 22 reached `x2 = 644`. Uniform text
  grids are flagged and always use 28-pixel cells, so the hook now uses that
  known width. The table only needs to cover output pen and Y positions.
- **A line break after a row that is already full skips a row.** The break sets
  `next = (cell / cols + 1) * cols`, and after exactly `cols` characters the
  cursor has already moved on. A full row needs no break at all.
- **Rebuild the metrics whenever the font changes.** `build.py` handles it.
- The font is **2bpp twiddled**, not 4bpp linear. Calibrate against SJIS
  `81A1` (■), `815D` (―) and `8142` (。).

## Memory map of the patch

All of this is in runs of zeros in `1ST_READ.BIN` that were still zero in a RAM
dump taken after the game had booted and run — that is the evidence they are
not touched at runtime.

| region | size | holds |
|---|---|---|
| `0x8C0F0E4E` | 9262 | advance per glyph, at `0x8C0F0E50` (4608 bytes) |
| `0x8C0F3464` | 7284 | left bearing per glyph, at `0x8C0F3464` (4608 bytes) |
| `0x8C0F5464` | 6845 | globals, code at `0x8C0F546C` (640), floats at `0x8C0F5800` (4096) |

Code sites changed in the executable:

| address | change |
|---|---|
| `0x8C0603B4` | trampoline to the new placement routine; its old body is dead space |
| `0x8C0603C0` | stub in that dead space: saves the line-record pointer, then does the load it replaced |
| `0x8C0600EA` | `BSR` to that stub |
| `0x8C05FD3C`, `0x8C05E4C4`, `0x8C05EB10` | text-grid creation paths routed through the guarded 33/38-column allocator stub |
| `0x8C0F546C` | the new routine |

`SYSTEM.DAT` carries the font sheet raw at file offset `0x424E0`.

There are also ~149 unused sectors (305 KB) after `1ST_READ.BIN` on the disc —
it is the last file in the image, so it can grow if it ever needs to.

## Environment

redream at `M:\Program\Redream`. Keyboard: START=space, A=l, B=p, dpad =
t/g/f/h, F5 = redream's own screenshot.

Disc: `.cue` plus three `.bin` tracks, MODE1/2352, high-density track 3 starts
at LBA 45000. `1ST_READ.BIN` is at LBA 548537, 947300 bytes. `SYSTEM.DAT` at
LBA 364123, `SCENARIO.DAT` at LBA 356857.

Font rendering needs PIL (present, 10.4.0) and the TrueType faces in
`C:\Windows\Fonts`.
