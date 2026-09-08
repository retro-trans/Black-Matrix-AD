# Stock Flycast font-atlas experiment (option 2)

Status: the user visually confirmed both help and dialogue HD text on stock
Flycast. Revision 3 adds full main-menu names; revision 4 also expands the eight
battle commands. Revision 5 fixes rows crossing native text-record boundaries
and reduces the Yes/No selector's text height. Revision 6 refines its alignment,
indents battle labels, and adds a stock texture replacement for the deployment
heading. Tests and disc readback pass; **full-menu layout,
broader playtesting and hardware testing remain pending.** This is budgeted
coverage of the shared text engine, not every pre-rendered bitmap label.

This route uses the unchanged installed `D:/Program/FlyCast/flycast.exe`, copied
to `build/stock-atlas-run`. Setup and launch verify that the two executables
have identical SHA-256 hashes. No custom emulator, loader DLL, or BMHDFNT file
is involved. `tools/hd_ui/run.ps1` belongs to the OLD custom-emulator prototype;
do not use that launcher for this experiment.

## Testing revision 10

Revision 10 replaces the fitted-font prototype with direct Bizin Gothic
rasterization: 16px em size, one 12.5px baseline, no per-glyph X/Y resizing,
and the font's own advances (8px for half-width Latin, 16px for full-width
symbols). Sidebearings remain in the raster, not measured from the old font.
The isolated disc's English metric entries and native fallback font now use
the same model. Other native glyphs and baseline build artifacts are unchanged.
The old Yes/No-only 16-to-11px vertical squeeze is disabled for this build.
Heading-pack revision 5 renders the entire line at 15px, then splits it across
the HUD tiles without independently stretching any word.

Close Flycast and run `tools/hd_ui/run_stock_atlas.cmd`, now selecting
`build/reusable-atlas-ui-r10/disc/`. Use a normal VMU save, not an emulator save
state. The previous revision 9 disc remains intact. Font outlines, native
fallback encoding, metric-table scope, emitted SH-4 pen placement and
unsqueezed selector geometry have automated checks. All three injected files
(executable, parameters and SYSTEM.DAT) pass disc readback verification.
In-game appearance remains a user visual check, not an automated guarantee.

### Previous layout revisions

Revision 9 translates the seven stance-help pages in PARAMETA.DAT and expands
the stance selector to Guard / Evade / Counter, with seven columns and three
rows. A checked 20-byte constructor helper separates column width from the
original shared constant 3; that constant remains intact for stance IDs and
selection count. Tests execute the helper's encoded SH-4 and verify both
logical and allocated dimensions. Only the stance constructor, its literal,
and reserved arena bytes change; combat dispatch is unchanged.

Revision 9 used `build/reusable-atlas-ui-r9/disc/`. Fully close the
test emulator and cold-boot this disc using a normal VMU save, not an old
emulator save state. Revision 8 remains available in its original directory.
The seven pages are patched into a copy of the current translated parameter
archive, preserving all other archive bytes. Executable and archive readback
are verified; in-game menu layout/navigation still require visual testing.

The previous shared HD font pack used 87.5% ink size in both axes, following the
user's request for smaller text throughout selection boxes. Heading-pack
revision 4 uses the same reduction with Bizin Gothic Regular. This is a texture-only update: restart
Flycast fully; the font itself needs no new disc. Native-font fallbacks and graphics
not covered by these four replacement textures retain their existing sizes.

Revision 8 increases battle-menu left padding from six to ten native pixels,
moving only its labels four pixels farther right. Selection geometry and text
size are unchanged. The launcher selects `build/reusable-atlas-ui-r8/disc/`.

Revision 7 moves Yes/No up two native pixels after the user's screenshot showed
excess top clearance. Its eleven-pixel glyph height and all other layout stay
unchanged. Revision 6's disc is retained at `build/reusable-atlas-ui/disc/`.

1. Run `tools/hd_ui/run_stock_atlas.cmd`. Its process-only execution-policy
   override avoids changing the machine's PowerShell policy.
2. Cold-boot the separate test disc and load a normal in-game VMU save. Do not
   load an old emulator save state: that restores the old executable in RAM.
3. Check dialogue, a menu (items/status/equipment), and attack help. Check
   correct letters, line breaks, highlights, opening/closing and page changes.
   The existing three HD textures are reused without any emulator rebuild.
   The main menu should now read Status / Ritual / Items / Shop / Abilities /
   System / Exit (Deploy instead of Exit in deployment). Check the wider menu
   and selection bar for screen-edge clipping; disabled entries should stay dim.
   The battle menu should read Move / Attack / Magic / Items / Status /
   Refill BP / Stance / Summon. Check every selection and its highlight.
   Revisit item-use help: “show item range” should have ordinary spacing.
   Yes/No text should sit inside its selection band with vertical clearance.
   Battle text should clear the left cursor; the lower-right deployment HUD
   should read “Initial Setup Mode.” Restart Flycast fully to load the PNG.
4. If a new palette still shows native text, run `tools/hd_ui/stock_atlas_pack.py`
   with the project's Python environment after capturing that screen.
   It finds only dumps whose entire pixel layout matches the canonical sheet,
   then installs hash-named 512×512 PNGs in this test profile's texture folder.
5. After installing additional textures, fully close/restart and revisit the
   screen. A budget fallback or pre-rendered image will not become HD merely by
   installing another hash; diagnose those separately.

The user handles all navigation. Missing/mismatched dumps cause the pack
installer to stop without installing replacements. Different palettes may
need additional captured hashes. The final portable pack can be distributed
once those hashes and normal stock replacement behavior are confirmed.

## What the game patch does

### Full main-menu labels

The old `Stat`, `Rite`, `Item`, `Abil` and `Sys` strings were intentionally
abbreviated translations in fixed four-character rows—not clipping by Flycast.
`tools/mainmenu.py` now relocates only the free-action and deployment menu
records to `0x8C0F6800..0x8C0F6900`. Each record has seven nine-cell rows (63
characters), within the 100-cell transition capacity. Both constructors' own
logical/allocated column counts and record pointers are updated; no global
four-column rule is changed. Original record bytes, command order, enable masks
and selection handling are left intact. Native/VWF text drawing and the stock
HD atlas path handle the new labels without changing the emulator or font pack.

This adapts only the menu patch from local `origin/main` commit `db857bb` and
adds atomic validation plus HD-arena composition tests. The remote font,
dialogue wrapping and other changes have **not** been merged. Labels live in
`script/ui/main_menu.tsv`; the old fixed-stride TSV remains for baseline builds.

### Full battle-menu labels

Revision 4 adds `Move`, `Attack`, `Magic`, `Items`, `Status`, `Refill BP`,
`Stance`, and `Summon` from `script/ui/battle_menu.tsv`. The old three-cell
abbreviations are replaced by eight nine-cell rows (72 cells). Only this
menu's record pointer and constructor column count change; its eight rows,
command order, enable flags, and combat dispatch remain untouched.

`tools/hd_ui/battle_menu.py` validates the HD code, original record count,
pointer, constructor opcode, and empty storage before writing. Its 146-byte
record follows the assembled atlas hook code and must end before `COSTS`.
Tests check exact labels, scoped byte changes, atomic rejection, and composition
with the main-menu patch. In-emulator layout/selection testing is still needed.
The deployment-mode heading uses the separate texture pack described below.

### Record-boundary spacing and selector size

The native engine chains 192-character text records. Captured item help split
the second row after `sh` in `show`, causing the old VWF negative-row-start
guard to leave the remaining letters at fixed-cell positions. Revision 5's
opt-in VWF adjustment resolves the live predecessor through its `next` pointer,
includes its trailing advances and first bearing, then continues in the current
record. It never assumes that linked records occupy adjacent slots. Missing or
released predecessors fail closed. Synthetic nonadjacent records and the local
RAM capture are replayed through the emitted SH-4 code in regression tests.

Only three-column, two-row Yes/No grids compress the full sixteen atlas rows
into eleven screen rows. The two-pixel vertical inset is derived from the cell
index, so repeated placement cannot drift. All UV rows remain available; the
font pack, horizontal advances, dialogue sizes, and selection geometry stay
unchanged. These UI fixes are opt-in for the stock-atlas experiment; the normal
baseline VWF code bytes remain unchanged.

The battle-menu padding adds ten native pixels to each glyph's calculated X position
only in the nine-column, eight-row battle menu. This clears the cursor without
changing the selection box, font metrics, dialogue, or seven-row main menu.

### Deployment heading: stock PNG replacement

The visible heading is assembled from individual HUD sprite tiles, not text
records. In the captured live atlas 4, sprites 100..103 and 107..111 occupy
the three word groups at `(184,80,216,96)`, `(144,96,176,112)`, and
`(144,112,224,128)`. `deployment_heading_pack.py` replaces these with “Initial,”
“Setup,” and “Mode,” preserving meaningful whole word groups and leaving stance
sprites 104..106 untouched. The source archive location is not yet resolved.
Heading-pack revision 2 reserves three native pixels on both sides of each
word group, giving at least six pixels between words. The first pack's one-pixel
margins looked run together in the user's screenshot. The installer permits an
upgrade only from the exact known previous pack hash or an identical output.

This uses ordinary stock Flycast replacement `240fd9ad.png`. The generator
requires an exact SHA-256 match of all decoded source pixels, emits a 4x PNG,
and refuses to overwrite a different existing replacement. Tests verify that
all pixels outside the nine heading tiles remain unchanged at integer scale.
Other HUD art is nearest-neighbor replicated, not redrawn. The preview assembles
the three word groups; actual sprite rendering still needs cold-boot testing.

This heading change is **emulator-only**, not a translated disc graphic;
original hardware retains the Japanese heading. Setup installs it when the
verified dump is available; otherwise capture the deployment screen in the
isolated profile and run `tools/hd_ui/deployment_heading_pack.py` once.

### Font-sheet coverage and memory

For revisions 8/9 only, `generate.COMPACT_INK_SCALE` controlled a 12.5% ink
reduction. The original native matching mask, slot layout, low-resolution font,
advance/bearing tables, line breaks, selection geometry, and indentation are
unchanged. Smaller glyphs are centered horizontally in their prior ink bounds;
all vertical coordinates share one line-centered transform so cap height,
x-height, baseline and descenders remain related. This deliberately preserves
character advances (slightly more whitespace between letters), not text reflow.
The legacy generator's default remains full-size. Tests cover every supported
glyph, unchanged native masks, exact reduced bounds and atlas-cell containment.

Revision 1 covered the captured help's 192- and 93-character records. Revision 2
accepts 1..192 characters per record, including the structural `0xA0FF` line
break. Every printable glyph must belong to the known English map. Japanese,
unmapped symbols, and inline palette controls keep the original blit path;
existing vertex-color highlighting is unchanged. Pre-rendered UI sprite labels
do not use this text engine and are outside this patch's coverage.

Eligible records allocate 128 native 4bpp slots and fill every slot with the
same glyph order, including blank padding. The stock allocator's strict >128
threshold splits this into four 128×128 textures (32 slots each), not a single
256×256 texture. Three contain glyphs; the fourth is blank padding and is not
replaced. At draw time the VWF
hook resolves the live record by texture handle and converts character index
to fixed glyph slot. Original text, line breaks/layout, pen metrics, vertex
colors, handle ownership, allocation accounting and freeing remain in place.
Each record still owns a separate allocation: this prototype reuses CONTENT
and layout, not one globally shared VRAM allocation. The native allocator uses
96 units for 192 characters, 48 for 93, and 64 for the fixed sheet (one unit
is 512 bitmap bytes). Thus the old 93-character allocation does grow by 8 KiB;
the earlier assumption that it already occupied 128 slots was incorrect.

The sizing hook first obtains the original descriptor/size, then admits an
enhanced allocation only if both checks pass:

- Extra bitmap memory above live records' original sizes stays within 64 KiB.
- Current use, the fixed sheet, and native capacity reserved for every other
  allocated pending record fit within 224 KiB of the existing 256 KiB pool.

Otherwise the original descriptor, allocation and blit are retained. A 32-byte
side table remembers this decision and its incremental cost; drawing never
re-evaluates a changing memory budget. Reusing a record clears its old decision.
Freed records are excluded from accounting by their cleared live flags. Native
capacity lookup follows the verified `[128,32,8,2,0]` allocator table.

Tests include all 192 supported lengths, line breaks, stale handles, slot
bounds, original palette controls, memory-budget fallback, released records,
and a full pending 32-record menu that must remain native to fit the pool.
This limits risk but does not replace testing future overlapping windows and
resource pressure on hardware. Busy screens may intentionally mix HD and native
text when the budget does not permit all records to use the fixed sheet.

Hooks occupy the unused `0x8C0F6900` arena, immediately after the new main-menu
records at `0x8C0F6800..0x8C0F6900`. Patching checks baseline VWF bytes,
native hook signatures and empty arena space and refuses unknown baselines.
The normal `vwf.build_code()` output remains unchanged unless an explicit
atlas hook is supplied. The standard build pipeline does not enable this.

## Isolation and regeneration

### Outline font

The stock HD pack and deployment heading use **Bizin Gothic Regular v0.0.4**
from [the official release](https://github.com/yuru7/bizin-gothic/releases/tag/v0.0.4).
Run `python tools/hd_ui/font_style.py` once to fetch the pinned font and its
SIL OFL 1.1 license. Downloads are SHA-256 checked; the TTF stays under
`build/fonts/bizin-gothic-v0.0.4/`, without installing a Windows font.
Both stock generators share this default so regeneration retains the choice.

Run `python tools/hd_ui/stock_atlas_pack.py` and
`python tools/hd_ui/deployment_heading_pack.py` to regenerate the four current
replacements. The license is copied alongside them. Fully restart the stock
test emulator to load the updated PNGs; no disc or emulator rebuild is needed.

For revision 10, `bizin_font.py` generates native/HD font art and metrics from
the outline itself, without old bitmap bounds. Dialogue's existing explicit
line breaks are retained; this does not automatically reflow translated text.

Install the extra hash dependency with
`python -m pip install -r tools/hd_ui/requirements-stock.txt`.
`prepare_stock_atlas.py` builds the matching native font and game metric tables
and seeds the three new HD PNG names through `seed_bizin_pack.py` when the
verified original captures exist. The seeder reconstructs the 128px twiddled
4bpp payloads and requires all three original hashes to agree on Flycast's
palette/format XOR salt (`0x870df5a5`). New texture hashes follow the same
stock XXH32 rule. This is offline pack generation, not an emulator patch.
New Bizin scene captures can also be matched by `stock_atlas_pack.py` normally.
The old MFD is used only to authenticate previous captures, never to size or
space the new font. Native fallbacks now render Bizin as well; the standard
non-experimental build retains its existing font.

### Disc/profile regeneration

Based on local translation commit `34a0669`; divergent remote `db857bb` has
not been merged. Close the test emulator before regenerating.

`tools/hd_ui/prepare_stock_atlas.py` prepares revision 10:

- `build/reusable-atlas-ui-r10/1ST_READ.BIN`, `PARAMETA.DAT`, `SYSTEM.DAT` and a manifest with hashes.
- `build/reusable-atlas-ui-r10/disc/`: independent copy of the translated disc.
- `build/stock-atlas-run/`: stock emulator, separate configuration and VMU copies.

The previous main-menu-only build remains at `build/reusable-atlas-menu/disc/`.
The revision 5 battle-menu disc remains at `build/reusable-atlas-battle/disc/`.
The known-good help-only disc remains at `build/reusable-atlas/disc/`, launched
with `tools/hd_ui/run_stock_atlas.cmd -HelpOnly`. The expanded HD build with the
old menu labels remains at `build/reusable-atlas-expanded/disc/`, launched with
`tools/hd_ui/run_stock_atlas.cmd -PreviousLayout`. All use the same isolated
stock profile and VMU copies; close one before launching another.

Setup refuses to modify a test disc named in a running Flycast command line.
It reads back the injected executable to check equality. It never modifies the
regular emulator/profile or the baseline translated disc. Existing test VMUs
are not overwritten. Game binaries, font-derived assets and disc copies remain
in ignored `build/`; do not commit or redistribute them as source fixtures.

Intended hardware behavior is ordinary native-resolution text, with no HD PNG
loading on the Dreamcast. This is not a claim of hardware compatibility until
tested; texture lifetime, transitions, memory pressure and every affected UI
still require playtesting before broadening eligibility.
