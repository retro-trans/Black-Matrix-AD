# Handoff — font, wrapping, main menus and Chapter 1 ending

## Read first: possible unpushed work on another PC

The user says the other PC may not have pushed all its changes, including an
earlier chapter-card translation. This session inspected only this checkout
and available Git history, not that PC. The correct conclusion is that the
card patch was missing from this checkout's build pipeline, NOT that it had
never been translated. Compare the other PC's working tree and local commits
before integrating this work. Preserve its changes; do not reset or force-push.
Resolve overlapping font, menu, glossary and graphics changes deliberately.

This handoff supersedes the earlier September 7 handoff and historical font/
33-versus-38-column notes further down docs/HANDOFF.md and text-engine.md.

## Current implementation

- Bundled unmodified Bizin Gothic Regular v0.0.4 with upstream OFL license and
  provenance in assets/fonts/bizin-gothic. Build defaults: 19px requested size,
  1.5x horizontal scaling, fitted to 16 bitmap rows, baseline 12. H is 12x12;
  Latin letters reach 13px width, punctuation reaches 20px. No glyph clipping.
  Only mapped Latin/digit/punctuation glyph slots change; Japanese stays stock.
- Normal text row pitch is 18px for 16px glyphs. Three rows cover 52px. Compact
  menus and other widths retain stock row pitches. Live border clearance is
  not confirmed yet.
- Both 17- and 19-column native text grids now allocate 33 columns. Both TALK
  and NARR wrappers use 33 plus the 476px measured-width limit. NARR is NOT a
  reliable indication of window shape: town records 0x1B6FA and 0x1B7A6 use
  a spoken-width window. The previous 38-column assumption caused the reported
  split `sl/ave?!` and a blank second row after an already full first row.
- Preserve patchline's omission of explicit newlines after exactly full rows:
  the engine already auto-wraps, so another newline skips a row. New regression
  tests replay the native cursor for both reported source lines. Their wording
  and speakers were not changed.
- tools/mainmenu.py translates field and deployment main menus. Original
  28-word records at executable offsets 0x88B26 and 0x89818 are retained;
  pointers target new 63-word records at RAM 0x8C0F6800 and 0x8C0F6880.
  Only those constructors' logical/allocation widths change 4->9. Labels are
  Status, Ritual, Items, Shop, Abilities, System, Exit (Deploy in deployment).
  Seven rows / selection semantics are retained. Unrelated small grids stay
  untouched. UI strings are in script/ui/main_menu.tsv.
- tools/chaptercards.py translates the Chapter 1 ENDING bitmap at EVENT.DAT
  SCL 0x2DF6800: Chapter 1 / Pandora's Miniature Garden / End. It retains the
  original tile/atlas allocation and uses 87 unique tiles. The chapter-opening
  graphic and other chapter cards are NOT covered. Source/control IDs are in
  script/ui/chapter1_end.tsv; hud.py includes it on every full build.
- New glossary category menu_label applies only to exact UI label records:
  e.g. 状態 becomes Status in the menu, without imposing that phrasing on
  contextual dialogue about someone's condition. UI references still use
  $$Japanese term$$ controls. There are now 394 canonical entries.

## Build and verification

Run from the repository root with Python/Pillow, the original extracted assets,
and the Disc 1 copy in build/disc:

```powershell
python -m unittest discover -s tests -v
python -u tools/build.py
```

The full build and injection completed on this PC. Verification:

- 25 tests passed, including emitted SH-4 grid/spacing hooks, exact screenshot
  wrapping, main-menu patch boundaries, font bounds and chapter asset bounds.
- All four injected files match generated payloads: 1ST_READ.BIN, SYSTEM.DAT,
  EVENT.DAT and SCENARIO.DAT.
- All 501 PSI programs and 7,533 branch destinations retain their corresponding
  original statement targets. 5,252 changed target operands were relocated.
- 10,298 translated records; 3,903 glossary occurrences and 9,995 dialogue/
  narration lines with known speakers pass metadata checks.
- Encoded Chapter 1 ending preview visually checked. This is NOT live Flycast
  verification. Existing 93 overlong choice warnings remain unrelated backlog.

Boot in Flycast:
`E:\Projects\Black Matrix AD\build\disc\Black-Matrix Advanced (Japan) (Disc 1).cue`

Use a cold boot, not an old emulator save state with stale code/assets. Original
disc images, extracted data, generated builds, RAM captures and preview images
are ignored and are NOT pushed. Another PC must rebuild with its own originals.

## Next checks and implementation cautions

1. Reconcile the other PC's unpushed work before merging overlapping changes.
2. Ask the user to check both main menus, the two town lines, the Chapter 1
   ending, and three-line text box clearance/transitions in Flycast. The user
   can navigate and provide screenshots. Do not claim runtime success yet.
3. Leave the original text-close routine untouched (SAFE_TEXT_CLOSE=False).
   Retain the atlas-based live-record lookup that fixed deferred book menus.
4. Keep the AP opcode 0x23 single-expression grammar and PSI modulo-four record
   alignment fixes. Do not revert them when reconciling older code.
5. Record stub uses 96/114 bytes. Main VWF code uses 688 bytes, with 228 bytes
   left before FLOAT_TAB. Main-menu strings reserve RAM 0x8C0F6800..0x8C0F6900
   immediately after the 1,024-entry float table; do not reuse this arena.
6. Translation requirements remain: glossary controls for terms, confirmed
   speaker before translating dialogue, and research for newly encountered
   characters' voice/personality. These new menus/cards are System UI.
