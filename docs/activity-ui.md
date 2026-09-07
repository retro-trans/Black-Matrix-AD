# Activity and field UI localization (2026-09-05)

The activity and field screens requested by the user are patched by the normal
`python tools/build.py` pipeline, not by editing screenshots or emulator RAM.

## System prompts

`script/en/ch1_activity_prompts.en.tsv` adds three previously untranslated
PSI2 `st 0x20` prompt records, using original SCENARIO.DAT offsets:

| Offset | Source | English |
|---|---|---|
| `0x51068` | まき割りをしますか？ (AP4 glyphs) | Chop wood? (4 AP) |
| `0x51868` | 料理をしますか？ΑΒΓΖ | Cook? (3 AP) |
| `0x61848` | 掃除をしますか？ΑΒΓΕ | Clean? (2 AP) |

The apparent Greek letters are the original font's compact AP-cost glyphs.
The English prompts spell out their meaning. Only the text is replaced; AP
cost expressions, choices, and activity logic are not changed. These are
non-diegetic System prompts, not character dialogue. Exact prompt phrases have
glossary IDs, expanded through the existing `$$Japanese phrase$$` mechanism.

## Cooking help graphic

The control diagram is EVENT.DAT group 34, SCL at `0x7FF000`. Its native
image is 640x240 and is displayed at 640x480. The map has 40x15 16-pixel tiles,
starting at SCL+32; each 32-bit descriptor stores Y in bits 0..7, X in bits
8..15, and atlas index in bits 16..31. SCL+20 is a halfword-relative pointer
to the texture directory, whose entries point to GBIX headers. Its two raw
RGB565/twiddled PVRT headers are at `0x7FF9B0` and `0x81F9D0`.

`tools/pvr_atlas.py` decodes this map and re-tiles the translated screen into
the same two 256x256 textures. `tools/cooking.py` replaces text while keeping
the controller, button colors and connector lines. Wording and source text
are in `script/ui/cooking_help.tsv`, with glossary controls checked on load.
`tools/hud.py` invokes the patch, so no extra disc-injection step is needed.

The new map uses 354 of the existing 512 available tiles. No file extents,
SCL headers, texture headers, or resource-directory pointers are resized.
The decoded-output preview is `build/cooking-help-english.png`.

## Woodcutting help and field menus

`tools/woodcutting.py` patches EVENT.DAT group 33, SCL `0x7BE000`, using the
same tilemap encoder. English wording is in `script/ui/woodcutting_help.tsv`.
The controller, button colors and guide lines are unchanged. The output uses
236 of 512 available tiles; preview: `build/woodcutting-help-english.png`.

`tools/build.py` translates the two executable field-menu strings at `0x88B62`
and `0x89854` to `Save Load Setup`. These are three fixed five-cell rows, so
the space following Save/Load is required slot padding; Setup fits exactly.

`script/en/ch1_gate_prompts.en.tsv` translates the six System gate prompts at
`0x44048` through `0x49048` (stride `0x1000`) to `Go past the gate?`.
The corresponding six route files shorten the player's responses to
`Go outside!` / `Stay inside!`. Both fit the 15-cell choice capacity even
after alignment padding, preventing text from spilling into adjacent slots.
Prague's question at `0x48586` is `Well? Still want to go outside?`, wrapping
to two rows at 17 cells. Her speaker range is recorded in `script/speakers.tsv`.

## Verification

- `python -m unittest discover -s tests -v`: 15 tests pass, including the
  preceding VWF/AP regressions.
- Original cooking screen decodes to match the supplied reference screenshot;
  RGB565 decode/encode/decode round-trip is pixel-exact.
- Only the map and its two texture payloads change; controller/guide-line
  pixels remain identical. The encoded English preview was visually checked.
- All nine added activity/gate prompts preserve original branch destinations.
- Woodcutting controller pixels and bytes outside its map/texture payloads
  remain identical. All twelve shortened choices fit their storage slots;
  Prague's question wraps to exactly two lines.

Cold-boot the rebuilt Disc 1 CUE in Flycast to verify the cooking confirmation,
Explain screen, cleaning/woodcutting confirmations, woodcutting Explain screen,
Save/Load/Setup menu and gate choices. Do not load an old emulator state.
These are build/resource checks, not an emulator play-test result.
