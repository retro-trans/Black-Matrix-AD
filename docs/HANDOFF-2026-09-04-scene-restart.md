# Prague cabin scene restart — root cause found and fixed (2026-09-04)

The restart was **not** the text grids, the VWF hook, or the close helper.
The repacker was moving every statement after a grown text record while
leaving every real branch target pointing at the old offsets.  The fix is a
full decode of the PSI2 statement stream (`tools/psi2.py`) and relocation of
every branch-target operand in `tools/scriptpack.py`.  The current build in
`build/disc/` contains the fixed SCENARIO; it needs a play test through the
Prague cabin scene (expected line at original absolute `0x2EA26`:
"Hmph! So you can finally move around. This week was a bother!").

## What was actually wrong

`tools/scriptpack.py` used to relocate "labels": u32 operands whose value
equalled the position of a six-byte marker `FF 00 80 00 00 00`.  Reversing
the interpreter in `1ST_READ.BIN` showed that model was wrong end to end:

- That byte pattern is not a label.  It is the tail of an ordinary RPN
  expression: tag `0002`, variable index `0x00FF`, operator `0x0080`, end
  `0x0000`.  There are no labels in PSI2 at all.
- Real control flow stores u32 **file offsets minus 0x10** (groups load at
  `0x8C700000`, execution starts at `0x8C700010`) inside three statements:
  `0x02` conditional jump, `0x03` jump, and `0x1D` menu-choice target
  (taken later through the choice table at `0x8C26422C`).
- The original SCENARIO.DAT contains **7,513** such branch targets.  The
  old repacker relocated 26 — all coincidental value matches, i.e. 26
  corrupted operands — and left every genuine target stale.  A full repack
  moves text in nearly every group, so nearly every jump in a rebuilt group
  landed mid-statement.  Group 50 (the Prague cabin scene,
  `script/en/ch1_seasonal_prague.en.tsv`) alone has 95 targets, none of
  which were relocated; its scene-entry dispatch chain (an
  if/jump chain in the group header) jumped into garbage, which is why the
  scene reset the game even with stock text geometry.  The earlier stall
  with a text-close (`0x18`) on handle `-1` was the same corruption: a
  stale jump skipped the window-open statement.

## The fix

- `tools/psi2.py` — new module.  Documents the interpreter (dispatch
  tables at `0x8C09A26C/0x8C09A32C/0x8C09A408/0x8C09A4D0/0x8C09A5E4`, the
  operand readers at `0x8C08BC3C/0x8C08BC4A/0x8C08BC96`, the expression
  grammar) and linearly decodes a whole PSI2 program with per-opcode
  operand signatures.  `python tools/psi2.py check` walks all 501 real
  groups of the original file: every byte parses, and all 7,513 branch
  targets land on statement boundaries.  The signatures were corrected
  against that corpus, so the validation is load-bearing; keep it passing.
- `tools/scriptpack.py` — label logic deleted.  It now walks each
  translated group, relocates every branch target
  (`new = mapped(old + 0x10) - 0x10`), rewrites the operand at its moved
  field position, then re-walks the rebuilt group and requires every
  relocated target to land on a statement boundary and every translated
  record to sit on a text statement.  The current full repack relocates
  **5,203** targets.
- Nothing in the executable changed for this fix.  The VWF hook, font and
  stock 17/19 text grids are as the previous baseline build.

## State of the disc

`python tools/build.py` has been run; `build/disc/` holds the fixed image:

- `build/SCENARIO.vwf.dat`: 2,240,512 bytes, 10,287 translated records,
  growth +399,568 bytes, 5,203 relocated branch targets, relocated to
  LBA 50,000.
- The group-load buffer at `0x8C700000` extends to `0x8C70B000` (next
  static objects referenced at `0x8C70B000`/`0x8C70C800`), so the largest
  rebuilt group (24,576 bytes) fits with room to spare.

## What still needs doing

1. **Play test** the Prague cabin scene in Flycast on the current build.
   If it still restarts, capture RAM at the failure
   (`powershell -ExecutionPolicy Bypass -File tools\dumpram.ps1 -ProcName
   flycast -Out build\NAME.bin`) and compare the loaded group at
   `0x8C700000` with the rebuilt group bytes.
2. If the scene now advances, re-enable wider grids one axis at a time
   (`EXPAND_TEXT_GRIDS` in `tools/vwf.py`, columns in
   `tools/patchline.py`) — the earlier expanded-grid crashes were probably
   this same relocation bug, so the grid experiments deserve a retest.
3. The older notes in `docs/HANDOFF.md` and `docs/text-engine.md` predate
   this fix; where they talk about labels or the 26 relocated references,
   this document supersedes them.

## Evidence trail (for re-verification)

- Statement/operand grammar: docstring of `tools/psi2.py`.
- Conditional jump reads target then expression: `0x8C08BF06`; jump:
  `0x8C08BF2A`; choice target consumed at `0x8C08C8E6`, jumped through
  `0x8C08CC40`/`0x8C08CE74`; scene call by group number: `0x8C08C3BE`
  (call stack at `0x8C263AB8`, current group at `0x8C0FD572`).
- Group 50 event chain: original targets `0x20F0/0x261C/0x1850/...` now
  relocated to `0x2A34/0x31E4/0x1F54/...` in the rebuilt group.
