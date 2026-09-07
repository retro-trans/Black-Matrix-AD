# Field/battle menus, deployment help, and chapter cards (2026-09-07)

## Latest follow-up: refill heading and defensive stances

Executable character record `0x8A054` changes `補血` to `BP` within its two
cells. The three stance rows at `0x87FD8` become `Grd`, `Eva`, and `Ctr`
(Guard, Evade, Counter), preserving their three-cell strides and nine-word
record count. TANK BP, LIMIT BP, numeric values and saved character names
are unchanged. Tests bind these offsets to the original Japanese and check
that every byte outside the selected text ranges is preserved.

## Latest follow-up: status, equipment, and BP refill

Ten more fixed 3x19-cell help pages are translated in `battle_help.tsv`, bringing
the help-page total to 22. Status pages start at character offset `0x7C01A`
and continue at stride `0x74` through `0x7C25E` (six pages). BP refill pages
start at `0x7AA5A` and continue at that stride through `0x7ABB6` (four pages).
The translations preserve the 2-AP cost, requirement to refill before movement,
attacks, magic or armor summoning, the cap increasing with command time, and
Up/Down increments of 10 versus Left/Right increments of 1.

The status screenshot's equipment uses fixed eight-word name fields. The name
count is independent of that struct stride; the original three-character names
are followed by five verified space words. `field_battle_ui.py` uses that
padding for `Stick` at `0x65392`/`0x654B2` and `Jailwear` at `0x713F2`, updating
only the name count and its eight slots. The following flags, prices and stats
are preserved. Descriptions at `0x653A8`, `0x654C8`, and `0x7141E` remain 2x19
characters. Sources/glossary aliases are in `script/ui/status_items.tsv`.

`config_load_ui.py` now patches the empty-equipment record at `0x89EBC` to
`Empty` (seven-word capacity). SYSTEM.DAT PVX `0x21000` sprite IDs 51, 59, 57,
and 6 become Status, Equip, Magic, and V (the original vertical/縦 badge).
Only these captions use horizontal compression to retain text height inside
their original narrow sprite bounds. Preview: `build/status-labels-english.png`.
Existing player names still come from the save; they are not overwritten.

Checks: 23 tests pass; one optional captured-menu fixture is skipped. Tests
bind all help pages to their Japanese originals, validate padded row lengths,
and preserve non-text parameter data and neighboring sprite pixels. Additional
item checks verify the new counts, eight-slot bounds and following flag words.
Live Flycast verification remains pending. Earlier counts below are historical.

## Follow-up: attack and item help

The subsequent six screenshots add four more 57-word pages, bringing this
patch to twelve attack/item pages. They explain item range (A, red tiles),
target selection (D-pad then A), unlimited discards before using an item, and
the Y-button Yes/No discard confirmation. Character offsets are `0x7A88A`,
`0x7A8FE`, `0x7A972`, and `0x7A9E6`, respectively. The item-details page and
repeat-help prompt in that batch were already translated. The existing
source/row/boundary tests cover all twelve pages.

The next batch of screenshots adds eight PARAMETA.DAT help records, each with
three fixed 19-character rows (57 words total). Sources and glossary references
are in `script/ui/battle_help.tsv`; `field_battle_ui.py` applies them during the
normal build, after reading the original parameter archive.

| Character offset | Page |
|---|---|
| `0x7A2A6` | Normal/latent attacks each cost 1 AP |
| `0x7A31A` | Normal attack: physical hit with the equipped weapon |
| `0x7A38E` | Latent abilities: weapon specials cost BP |
| `0x7A402` | Up/Down chooses the attack mode; yellow tiles show range |
| `0x7A476` | D-pad selects the target; A attacks/activates |
| `0x7A72E` | Use or discard items |
| `0x7A7A2` | Item command: once per unit per turn (two screenshots share this page) |
| `0x7A816` | Select an item from the list; X shows its effects |

The separate white Move heading is SYSTEM.DAT PVX `0x629040`, sprite 56,
atlas page 1: PVRT `0x6494F0`, rectangle `(112,64)-(200,80)`. It is now rendered
as `Move` through `config_load_ui.py`. The fixed three-cell executable command
still uses `Mov`. Preview: `build/move-heading-english.png`.

The supplied repeat-help prompt matches the previously patched executable
record at `0x888CA` (`Show help again?`). There is only one matching original
executable record; the prior built file already contained its English text.
That alone does not establish which build/state produced the user's screenshot.
Cold-boot verification is still required for these pages and the Move heading.

Tests now total 22 passed and one optional capture test skipped. New checks
compare each page's Japanese source against the exact original record, verify
all three padded rows after encoding, and preserve all bytes outside the
selected records. Sprite checks cover both atlas pages and retain their
headers, descriptors, and neighboring pixels. Older counts below predate this
follow-up.

The five user-supplied screens are localized by the regular build pipeline.
All text is System UI. This change does not modify the text engine, AP costs,
script control flow, or logical grid sizes.

## Fixed executable menu records

`tools/field_battle_ui.py` patches these character-data offsets in
`1ST_READ.vwf.bin`, preserving their preceding u16 counts:

| Offset | Layout | English rows |
|---|---|---|
| `0x88B28` | 7 x 4 characters | Stat / Rite / Item / Shop / Abil / Sys / Exit |
| `0x8981A` | 7 x 4 characters | Same, with Go! (deploy) in the last row |
| `0x87FA6` | 8 x 3 characters | Mov / Atk / Mag / Itm / Sta / BP+ / Stn / Arm |
| `0x8823A + 8*i` | 8 separate 3-character records | Same battle labels |

Rite means Ritual; Abil lists latent abilities. BP+ replenishes Blood Points;
Stn changes the defensive stance; Arm is armor summoning. The short labels
are necessary because these records contain fixed row slots. Full-length
English labels would require separate renderer/layout work.

The deployment help is a 57-character PARAMETA.DAT record at character offset
`0x7A062`. Its three 19-cell rows become:

```text
Set starting spots.
Select a unit, then
choose a new spot.
```

The build now generates and injects `build/PARAMETA.vwf.dat` as a fifth disc
payload. The original extracted file is unchanged. Sources and glossary
controls are in `script/ui/field_battle.tsv`.

## Chapter artwork

`tools/chapter_cards.py`, called by `tools/hud.py`, patches EVENT.DAT SCL maps:

- `0x2DF6800`: Chapter 1 / Pandora's Garden / End.
- `0xF60800`: Chapter 2 / Golgotha Prison.

Both screens are native 640x240 and display at 640x480. The ending keeps its
plain black background and serif lettering. The opening uses two dark caption
panels to cover the original Japanese lettering; all pixels outside those
panels retain the original sigil artwork. Text sources are in
`script/ui/chapter_cards.tsv`; Pandora's Garden has a new glossary entry and
Golgotha uses the existing canonical spelling.

The maps are re-tiled into their existing RGB565 textures: 121/256 tiles for
the ending and 590/768 for the opening. No resource pointers or file extents
change. Encoded-output previews are `build/chapter1-end-english.png` and
`build/chapter2-open-english.png`.

## Verification

The regression suite passes 17 tests with one optional RAM-capture test skipped
on this checkout. New checks cover row-slot limits, byte-for-byte preservation
outside the edited records and texture/map payloads, atlas capacity, and
unchanged artwork outside the opening-card caption panels. Both encoded title
previews were visually inspected.

Cold-boot the rebuilt CUE and verify all five screens in Flycast. Resource and
instruction tests do not substitute for that play test; never load a save state
containing an older executable. The pre-existing 93 overlong script choices
remain outside this change.
