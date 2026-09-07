# Handoff — occult-library menu artifacts and AP-shortage input lock

Date: 2026-09-04

## Update 2026-09-05: menu ownership and AP decoder fixes

Implemented and injected into the Disc 1 build. **A cold-boot play test is still
required**; instruction-level and archive verification are not an emulator
playthrough. Do not restore a save state containing the old code/script.

### AP reset: the earlier "all branch targets are valid" conclusion was wrong

`tools/psi2.py` described mode-3 (`st 0x09`) sub `0x23` as `ee`. The dispatch
table entry at `0x8C09A408 + 0x23*4` actually points to `0x8C08E1E6`, which
calls the expression reader **once**, stores the cost at `0x8C264894`, then
polls the native AP modal. Its signature is `e`.

In original group 106, the warning is at `0x84`, its expression ends at
`0x92`, and the next statement is `st 0x03` at `0x92`, with target operand
at `0x94`. The incorrect second expression interpreted that statement word as
variable tag 3, the low target word `0x2FA2` as a variable index, and its zero
high word as the expression terminator. The walker therefore silently omitted
the unconditional jump from both relocation and validation.

After translation, the warning begins at `0x8C` and the jump field is at
`0x9C`. Previously it still held `0x2FA2`, jumping to file `0x2FB2` inside
translated text. With the corrected signature it holds `0x5A22`, targeting
file `0x5A32`, the original exit's relocated `st 0x12` return. This explains
why text-layout changes changed the failure symptoms. No modal bypass, AP-cost
change, or speculative native close patch is involved.

The original archive passes the corrected walker for all 501 PSI2 programs.
The previous translated archive fails it in nine groups. The rebuilt archive
passes, and every one of its 7,533 branch destinations maps to the same
statement as in the original program. The build now relocates 5,217 changed
targets, 11 more than before this fix.

### Menu: resolve the record from the atlas used by the placement call

The user left the Seven Sins menu open for a read-only RAM capture:
`build/book-menu-20260905-before.bin` (local, git-ignored). It confirms:

- Window 22, context `0x8C1E7A3C`, 14 columns, 7 rows, 98 cells.
- Record 0 at `0x8C1D5018`: 98 glyphs, flags `0x8800`, atlas handle 12.
- `G_RECORD` points at empty record 1, `0x8C1D51A8`.
- Every occupied menu cell's atlas handle is 12.

The replacement placement routine already preserves its **actual** atlas
argument in R11. `vwf_adjust` now searches the 32-record pool for that handle
in a live record with a valid count and character index. The pen no longer
reads `G_RECORD`. Unmatched/released records, invalid handles/counts, and
negative row-start indices leave the quad unchanged instead of reading
unrelated character storage. This also handles immediate dialogue/AP placement
without a broad window-flag bypass.

The hook is 688 bytes (`0x8C0F546C..0x8C0F571C`), leaving 228 bytes before
the float table. Stock grid widths, font, AP warning fields, native close code,
and transition behavior are unchanged.

### Verification and remaining work

- `python -m unittest discover -s tests -v`: nine tests pass. A small strict
  integer SH-4 runner executes the emitted pen/UV routine, not a duplicate
  Python implementation. Synthetic tests cover stale globals, deferred menus,
  dialogue/AP widths, invalid records, non-text grids and idempotent UV height.
- Optional local-fixture test replays the new SH-4 on all 98 captured menu
  cells. All match the font metrics; 82 previously incorrect X positions change.
- AP tests check the original handler bytes, a minimal swallowed-jump fixture,
  and relocation of the library AP exit after growing its prompt.
- Full build succeeds; all four disc payloads match the generated files.
- Cold boot in Flycast, verify book-menu spacing and ordinary dialogue, then
  dismiss `AP: LOW! (1/3)` and confirm movement resumes. This was requested
  from the user after the rebuilt disc was verified; results are pending.
- The 105 other overlong choice labels remain out of scope for this fix.

Everything below predates these fixes and is retained as investigation history.

## Update 2026-09-04 (later): menu artifact root-caused and fixed

**The choice-menu "stale glyph at the far right of every row" is fixed.** It was
not a VWF or window bug. Choice statements (PSI2 `st 0x1D`, handler
`0x8C08C8E6`) store every option into a buffer with a **fixed 15-word stride**
and cap the copy at 15 units, but statement `0x1E` (`0x8C08C9A6`) reads back
`width` units per option, where `width` is the **uncapped** longest option in
the menu. When any option exceeds 15 units, every row over-reads one or more
words into the *next* option's slot and paints that option's leading glyph at
the right edge — the stale "V" of "Virtue" in the screenshot. The last row has
no next option, so it shows no trailing glyph, which is exactly what the
capture showed. The longest *original Japanese* menu option in the whole game
is 15 units, confirming 15 is the hard engine limit.

Four occult-library labels exceeded it after translation. They are shortened in
`script/en/ch1_occult_library.en.tsv`:

- `Seven Sins Guide` (16) → `Sins Guide`
- `Gods' History I/II` (15/16) → `Gods' Hist. I` / `Gods' Hist. II`
- `Sin: Human Rights` (17) → `Sin: Rights` (`人権|Rights`)
- `Virtue: Gluttony` (16) → `Virtue: Excess` (`暴食|Excess`; the term had to be
  abbreviated because `Virtue: ` + `Gluttony` cannot fit)

**Watch the alignment padding.** `scriptpack.preserve_record_alignment` appends
one full-width space when a translation's parity differs from the original, so
a 15-unit label over an even-length original stores as 16 and re-triggers the
bug. `Sin: Friendship` (15) and the first `Virtue: Gluttony` fix hit exactly
this — both were pushed to ≤14 (`Sin: Friends`, `Virtue: Excess`). The real
constraint is the **stored** count after padding, not the source length.

A build-time guard was added: `tools/scriptpack.py` now flags every translated
`st 0x1D` option whose stored count exceeds 15 (`MENU_CHOICE_MAX_UNITS`). It is
a **warning**, not a hard failure, because the English script still carries a
backlog of **105 pre-existing over-limit options**, almost all in not-yet
play-tested ch2–4 menus (e.g. `I don't want to go outside!`,
`Let's not splash in the water!`, `Forget the war and find a new master`).
Every one of them will show the same trailing-glyph artifact when its menu is
reached. The full list (absolute offset, stored count, text, source file) is in
`docs/menu-labels-over-15.txt`; regenerate it from the build warning at any
time. They should be shortened to ≤15 stored units as a translation pass; once
the backlog is clear, promote the guard to a build-stopping error.

## Update 2026-09-04 (session 2): live menu capture, crash confirmed

### The menu has TWO defects, not one

1. **Trailing stale glyph** (the "V" at every row's right edge) — **fixed** above
   by keeping options ≤15 stored units.
2. **Glyph overlap** (cramped, e.g. "Si n: Freedom") — **still open**. This is a
   separate VWF-positioning bug and is the one the earlier handoff meant by
   "fix the menu in its actual window/context."

### Overlap root cause (from a live capture)

`build/menu-open.bin` is the Seven Sins menu captured while open (width=14, 7
options, 98 cells). Findings:

- The menu's glyphs live in **line record 0** (`0x8C1D5018`, count 98, holding
  SJIS→glyph *indices*: 0x00B2=S, 0x00C9=i, 0x0006=colon, 0x0000=space, …).
- But the VWF's global "current record" pointer `G_RECORD` (`0x8C0F5464`) points
  to **record 1** (`0x8C1D51A8`, count 0 — empty).
- The captured cell X-positions in window 22 do **not** match a correct VWF
  computation over record 0. Row 1's advances are a uniform ~8px (an empty
  record → every glyph reads advance[0]); row 0 is partially correct. So
  different rows were positioned from different stale record states.
- Conclusion: the menu's cells are placed **once, during the open animation
  (deferred)**. By the time each row's quad is placed, `G_RECORD` has already
  moved on (a later window's render set it to the empty record 1). The advances
  are therefore read from the wrong record and the pen is garbage.

**Why no flag gate works:** the AP-warning box is *also* a `0x8009` uniform-grid
window (`ap-open.bin` shows win 26/27, flag `0x8009`), and it renders correctly
because it is a single line placed immediately. Skipping the VWF for `0x8009`
windows would therefore break the AP box too. The fix must key on the menu's
*deferred* placement, or associate the correct record per-window/per-cell rather
than through the single global `G_RECORD`. That is an engine change; no safe
one-liner was found.

### The AP "lock" is actually a hard reset — and it is layout-sensitive

Three captures in one cold boot (`build/ap-before.bin`, `ap-open.bin`,
`ap-after.bin`):

- `ap-before`: field, group 37, AP 1/10.
- `ap-open`: group 106, interpreter parked on the AP-warning opcode
  (**PSI2 `st 0x09` sub `0x23`**, handler `0x8C08E1E6`, at group offset `0x8C`),
  native modal state `0x8C1D3450 == 4` (input poll), close handle
  `0x8C263B04 == -1`.
- `ap-after`: **group 0** — captured on the Dreamcast boot logo. It is a **hard
  reset**, not an input lock.

**Key observation from the player:** the scene **froze** before this session's
occult-label edit and **hard-resets** after it. That edit only shrank group 106
by 44 bytes (`used_end` 0x5A60 → 0x5A34). A few bytes of layout shift flipping
freeze↔reset means the interpreter is **dispatching a bad offset** (landing on
garbage that is benign in one layout and fatal in another), **not** a fixed
native null-deref (which would crash identically regardless of layout).

Both the old-build and rebuilt group 106 walk cleanly and **every branch target
lands on a statement boundary** — so this is not a static mis-relocation. The
bad landing is a *runtime* effect. Leading candidates, in order:

1. The AP-low path, after the warning, falls into the same book-menu build code
   (`st 0x1C`/`0x1D`/`0x1E` at `0x174`–`0x24C`) that has the deferred-placement
   record bug above. In the AP-low path the record may actually be **released**,
   so the game's own quad dispatcher (`0x8C06BEB8`, which dereferences the
   record's `+0x188` atlas/segment handle) reads a freed handle → reset. This
   would make the overlap and the reset the **same** root cause.
2. A mode-2 sub-opcode in `0xA0`–`0x126` (sub `0x22`×4, `0x08`, `0x13/14/15`,
   `0x2B`) reading a stale/bad pointer.

### What was tried and ruled out this session

- **`-1` close-handle fix** (`safe_text_close`: route `0x8C08C7AC`'s non-positive
  handle to global cleanup `0x8C06B2DC` instead of the stock deref in
  `0x8C08AF52`→`0x8C05E64C`). Built, injected, cold-booted — **did not fix the
  reset**. Left in `tools/vwf.py` but disabled (`SAFE_TEXT_CLOSE = False`); its
  ineffectiveness is itself evidence the crash is not that native deref.

### Getting the crash PC (next step)

The reset needs the exact faulting instruction. **flycast's GDB stub does not
work on this build** — `Debug.GDBEnabled=yes` (+`WaitForConnection=yes`, dynarec
off) never opens port 3263. Alternatives:

1. Launch flycast from the command line with stderr captured; with the JIT off
   the interpreter tends to log the faulting PC on an unhandled exception.
   Disc: `build/disc/Black-Matrix Advanced (Japan) (Disc 1).cue`.
2. Use redream (has a working debugger) or a flycast dev build with a real stub.
3. Enable a flycast serial/log-to-file sink.

Once the PC is known: if it is in `0x8C06BEB8`/`0x8C05E64C`/the record teardown,
candidate 1 (freed-record deref) is confirmed and the fix is to keep the menu's
line record alive (or place its cells non-deferred) through the AP-low path.

### Evidence files (build/, git-ignored)

| file | state |
|---|---|
| `menu-open.bin` | Seven Sins menu open (overlap bug live) |
| `ap-before.bin` / `ap-open.bin` / `ap-after.bin` | the 3-capture AP-low → reset sequence |
| `lock-after-dismiss.bin` | old-build freeze state (streamptr parked at `0x2FB4`) |

---

## Update 2026-09-04 (later): AP-lock diagnosis refined

The AP warning is a **PSI2 opcode** (`st 0x09` sub `0x23`, handler
`0x8C08E1E6`), invoked from the shelf script at group-106 offset `0x0084`; it
calls the native modal `0x8C04E4CE` and yields until dismissed. In a fresh
capture of the locked state (`build/lock-after-dismiss.bin`):

- The game's main loop is still running — two captures a few seconds apart
  differ only in the low SH-4 stack region (~227 words around `0x8C00F000`),
  a shallow native idle loop. This is a **soft lock**, not a crash.
- The AP modal state machine is fully reset: `0x8C1D3450 == 0`. The modal
  itself closed cleanly.
- The PSI2 interpreter is **idle**, not the cause. Its stream pointer
  `0x8C263AB4 == 0x8C702FB4` is unchanged between captures and points *inside*
  a text record (`st 0x14` at `0x2F7C`), i.e. it is a stale leftover from the
  last book read, not a live parked statement. The tempting coincidence that
  `0x2FB2` is the *original* target of the `st 0x03` exit jump is a red herring:
  in the built/live scenario that jump correctly relocates to `0x5A5E`, a valid
  boundary (verified in `build/SCENARIO.vwf.dat` and in the live buffer).

So the lock is in the **native free-action controller** that owns the shelf
interaction, which fails to re-enable input after the PSI2 opcode returns — not
in the modal and not in the script. This matches the original conclusion and
still needs the three-capture cold-boot sequence (before the low-AP
interaction, warning open, just after dismissal) to pin the exact controller
state that the Japanese path restores. No speculative native patch was applied,
per the warning below about bypasses regressing other scenes.

---

## Current baseline

The project has been rolled back to the exact code shape used when these two
bugs were first reported. The build intentionally keeps:

- the variable-width Latin renderer with the stock logical grids (`17` spoken
  columns and `19` narration columns);
- the compact translated occult-library labels and display aliases;
- the executable prefix translation `AP: LOW! ` while preserving its final two
  live words, which display the current and required AP.

The later experimental record guards, node-state guard, 33/38-column expanded
grids, and AP-modal bypass are not active. This means the warning is visible
again, but the input lock after dismissing it remains reproducible.

Always test this baseline with a full cold boot. Do not carry emulator save
states between builds.

## Reproduction

### Choice-menu artifact

1. Cold-boot the patched disc and reach the rehabilitation-house bookshelves.
2. Interact with a shelf while the character has at least 3 AP.
3. At `Read it? (3 AP)`, choose a book group such as Seven Sins or Seven
   Virtues.
4. The short English labels fit, but a stale `Sin` or `Virtue` prefix can
   appear at the far right of every menu row.

### AP-shortage input lock

1. Reduce the character to 1 AP.
2. Interact with a shelf action that requires 3 AP.
3. The translated warning `AP: LOW! (1/3)` appears.
4. Dismiss the warning.
5. The warning closes, but free-action movement/input does not resume. A cold
   boot is currently required to recover.

## Evidence collected

The diagnostic RAM capture is `build/current-menu-ap-ram.bin` (16 MiB). It was
taken after dismissing the AP warning, so it is useful for the input-lock state
but too late to identify the live choice-menu row that produced stale glyphs.

At the time of that capture:

- the scenario group field at `0x8C0FD572` was `105`, corresponding to loaded
  physical/logical group 106;
- the loaded scenario bytes matched the then-current built group 106;
- the AP modal task state at `0x8C1D3450` was `0` after dismissal, showing that
  the modal state machine itself had reset;
- the AP window handle field at `0x8C1D41E0` was `0x00010000`, and no active
  dialogue grid remained in `WIN_TAB` at capture time;
- the interpreter/global stream pointer at `0x8C263AB4` was `0x8C702FB4`, inside
  a translated narration record in the experimental build. This retained
  pointer is suspicious but is not yet a proven cause;
- the line record at `0x8C1D5018` had count zero after release while retaining
  stale glyph indices, including an `AP: LOW!` prefix and older text. Released
  records therefore cannot be assumed to have cleared character storage.

The renderer uses `G_RECORD` at `0x8C0F5464`; the internal line-record area
begins at `0x8C1D5018` with stride `0x190`. A dialogue line record has its count
at `+0` and glyph words beginning at `+4`, as described in
`docs/text-engine.md`.

## AP warning implementation notes

The fixed executable record begins at file offset `0x88C80`; its character
data starts at `0x88C82` and contains 11 u16 words. The first nine words are
patched to `AP: LOW! ` by `tools/uistr.py put-prefix`. The final words are live
fields and must remain byte-for-byte unchanged.

The executable contains a pointer to runtime record `0x8C098C80` at file offset
`0x3E684`. The warning handler begins at runtime address `0x8C04E4CE`. Its state
machine stores state at `0x8C1D342C + 0x24` (`0x8C1D3450`) and creates, polls,
and closes the modal through routines around `0x8C08AB3C`, `0x8C08ACB0`,
`0x8C08AD04`, and `0x8C08AE10`.

The last experiment replaced the handler entry at file offset `0x3E4CE` with
an immediate finished return. That hid the warning and did not solve the
underlying controller-resume problem, so it has been removed.

## Reverted experiments and conclusions

- Guarding VWF adjustment on the current record's count made menu text fall
  back to stock wide spacing because menu records can be released before their
  deferred cell quads are placed.
- Guarding on the node occupied bit also regressed ordinary dialogue and did
  not fix the lock. A global per-node guard is therefore not safe.
- Expanding spoken/narration grids to 33/38 columns improved some long dialogue
  cases but did not remove the choice-menu artifact or the AP lock.
- Bypassing the AP warning removed visible feedback and merely avoided the
  reproduction path. It is not an acceptable fix.

## Recommended next investigation

1. Capture RAM while the affected Seven Sins or Seven Virtues menu is still
   visibly open. Inspect `G_RECORD`, all 32 line records, active uniform-window
   entries, and every cell node's flags and glyph index. Compare used rows with
   unused rows before dismissing the menu.
2. Fix the menu in its actual window/context instead of adding another global
   VWF guard. Determine whether the menu has a distinct row stride, column
   count, or window flag that can safely gate the adjustment.
3. For the AP lock, take three captures in one cold boot: immediately before
   the low-AP interaction, while the warning is open, and immediately after it
   is dismissed. Diff the controller near `0x8C1D342C`, scheduler/task fields,
   and free-action mode. A matching Japanese-version capture would be the best
   control.
4. Do not bypass the warning or change AP costs. Find the controller state or
   callback result that the Japanese path restores after the modal closes.
5. Retest every candidate fix from a cold boot without save states.
