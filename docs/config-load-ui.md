# Load, help, Free Action, and confirmations (2026-09-07)

The next nine user screenshots are covered by the regular build pipeline.
Text is System UI. English sources are in `script/ui/config_load.tsv` and
`script/en/system_save_town_prompts.en.tsv`.

## Text records

`tools/config_load_ui.py` runs after `field_battle_ui.py`, retaining that
module's menu/help edits. It patches these character offsets in the executable:

| Offset | English | Fixed record capacity |
|---|---|---|
| `0x88E4A` | Pick VMU | 8 |
| `0x88E5C` | Pick a port | 11 |
| `0x88E74` | Pt.A / Pt.B / Pt.C / Pt.D | four 4-cell slots |
| `0x88E96` | Pick a slot. | 12 |
| `0x88EB0` | Slot1 / Slot2 | two 5-cell slots |
| `0x88086` | Finish setup? | 16 |
| `0x888CA` | Show help again? | 16 |
| `0x8842C` | Show all help. | 18 |
| `0x88452` | Hide all help. | 19 |
| `0x8847A` | Set help by topic. | 19 |
| `0x884A2` | Use help defaults. | 28 |
| `0x884DC` | A: Go back. | 28 |

PARAMETA.DAT character offset `0x7A0D6` keeps its 57 words, arranged into
three 19-cell rows: `Press START to end`, `unit placement.`, and a blank row.

All 22 copies of the two matching System script prompts are translated through
the normal PSI2 repacker: `Leave town?` and `Save progress?`. New full-phrase
glossary entries keep these consistent. A regression test verifies that every
branch in those programs still targets the same original statement.

## Graphic labels

Original PVX descriptor rectangles identify each sprite; no descriptor, UV,
sprite size, archive pointer, or atlas dimension changes.

| Asset | PVX | PVRT | Sprite IDs | English |
|---|---|---|---|---|
| SYSTEM.DAT | `0x21000` | `0x21890` | 63, 64 | Back, OK |
| SYSTEM.DAT | `0x608620` | `0x608810` | 0–13 | Ch. 1–11, Final, Port, Slot |
| SYSTEM.DAT | `0x629040` | `0x6294D0` | 17–20 | Show, Hide, Manual, Defaults |
| EVENT.DAT | `0xBC4000` | `0xBC4090` | 0 | Free Action |

Sprites use their original gold/white color families and ARGB1555 transparency.
Controller/VMU art, colored buttons, portraits, cursor graphics, and the banner's
separate gradient sprite remain byte-for-byte unchanged. Existing save-file
names remain as saved; a Japanese name such as アベル is save data, not a static
load-screen label. The patch does not rewrite saves.

## Verification and play test

21 regression tests pass; one optional captured-menu fixture is absent and
skipped. New tests verify exact byte boundaries for the executable/parameter
records and every edited texture pixel, including preservation of sprite
metadata and neighboring art. Decoded output previews were visually checked:
`build/load-config-labels-english.png` and `build/free-action-english.png`.

Cold-boot the updated Disc 1 CUE, then check VMU selection, saved-game listing,
HELP's four options and their descriptions, the Free Action banner, both script
prompts, and the deployment tutorial/confirmation. These new screens still need
live Flycast verification. Do not restore an older emulator save state.
