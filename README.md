# Black/Matrix AD — English translation

English translation and native interface work for **Black/Matrix AD** on
**Dreamcast**, covering the Japanese two-disc edition.

This repository and its releases are **private**. The current release is
**[v0.9.0](https://github.com/retro-trans/Black-Matrix-AD/releases/tag/v0.9.0)**,
an experimental prerelease based on internal cumulative build 0.1.13.
The release number identifies these exact disc bytes; it does not imply that
every route, screen or line has passed human review or a complete playthrough.

## Contribute

Bug reports, proofreading and playtesting are welcome through this private
repository's Issues. Include your disc, patch version, route, screenshot and
reproduction steps. Do not attach complete game images, BIOS files or personal
memory cards. Machine review is not counted as human proofreading.

## Play it

Download the patches and instructions from the
[v0.9.0 release](https://github.com/retro-trans/Black-Matrix-AD/releases/tag/v0.9.0).
You need your own exact Japanese disc dumps. No game image is distributed.

### Apply

Use **Apply xdelta** in [Retro Trans](https://github.com/retro-trans/retro-trans-tools),
[DeltaPatcher](https://github.com/marco-calautti/DeltaPatcher), or xdelta3.
Download the assets through your authorized GitHub account first: Retro Trans's
public Automatic catalog does not fetch this private release.

| Your source file | Patch |
| --- | --- |
| Japanese Disc 1, original raw Track 3 BIN | `Black-Matrix-AD-Disc1-Native-v0.9.0-from-original.xdelta` |
| Japanese Disc 2, original raw Track 3 BIN | `Black-Matrix-AD-Disc2-Native-v0.9.0-from-original.xdelta` |

Patch **Track 3 only**, separately for each disc. The patcher does not take the
CUE, an entire disc folder, a CHD, an extracted executable or a merged BIN as
an interchangeable source. The two discs are not interchangeable. This first
release supplies full patches only, not upgrades from earlier local test builds.

Check the exact source sizes and SHA-256 hashes in `README-v0.9.0.txt` or
`BUILD-MANIFEST.json`. Keep checksum verification enabled. A mismatch means the
source is not the supported file; do not force it through.

For example, create the new `patched-disc1` folder first:

```text
xdelta3 -d -s "Black-Matrix Advanced (Japan) (Disc 1) (Track 3).bin" "Black-Matrix-AD-Disc1-Native-v0.9.0-from-original.xdelta" "patched-disc1/Black-Matrix Advanced (Japan) (Disc 1) (Track 3).bin"
```

For Disc 2, use its own Track 3 BIN and matching patch. Never overwrite your
originals. In each new disc folder, copy the unchanged Track 1, Track 2 and CUE
from your own matching original disc set. Keep the patched Track 3 basename
identical to the CUE's FILE reference, and keep TRACK/INDEX/timing unchanged.
Boot the matching **CUE**, not a loose BIN. CHD conversion is not provided by
this patch: an extraction must produce the exact documented source bytes.

**Boot fresh and load an in-game VMU save.** Old emulator save states can keep
the earlier executable and artwork in memory. Preserve your existing VMU/card
files, backups and emulator profile; the release does not include or overwrite
them. Use the same VMU with both discs and use the emulator's disc-swap function
when the game requests the other disc.

### Native interface and options

Translated native graphics and the current font/layout fixes are included in
the patches; no optional texture pack is required. A standalone HD pack and
personal full-game/Steam Deck installation packages are not release assets.
Existing VGA compatibility repairs are retained, but physical Dreamcast hardware
has not been verified. Emulator-specific launcher settings are not bundled.

This cumulative profile also includes **Zero unlocked from the beginning** and
**Domina first in master selection**, as requested during development. It is
not a translation-only, original-unlock-order profile.

## What is included

- The cumulative English script and interface work already integrated into
  the two local disc builds. Unbuilt working-tree edits are not automatically
  part of the release.
- Native font/sampling and menu alignment repairs, including the current
  Equip fallback and matching Join/Remove/other footer work.
- English story cards, disc-change prompts, results/party and battle UI work.
- English credits, movie subtitle safe-area adjustments, and captions for
  18 unique voices in the post-credits angel-CG section.
- Twelve newly translated battle badge groups after auditing all 169 sprites
  in the primary battle UI atlas: Miss!, Guard, Stone, Poison, Paral., Status,
  Sleep, Up, Down, Freeze, Stance and Magic. Their actual ImageGen lettering is
  packed into native sprites, rather than supplied only as a reference.

See [the release notes](docs/releases/v0.9.0/RELEASE.md) and
[internal build changelog](docs/ACTION_BADGES_CHANGELOG.md) for exact scope.

## Validation and status

Every released patch is decoded from its exact original Track 3 source and
checked against the complete target size and SHA-256. The protocol manifest,
validation records and checksums accompany the patches. Unchanged companion
tracks and CUE files are checked separately. Those binary checks do not replace
gameplay, visual, audio or hardware testing.

Known limitations include:

- Fresh gameplay confirmation of the latest battle badges, Join and Equip
  lettering remains pending. Normal/Latent's older lettering is unchanged.
- The primary battle atlas audit is not a claim that all Japanese text images
  throughout the game have been found or translated.
- One scrolling-credit staff name retains Japanese because its reading is not
  verified. Four brief post-credits voice calls retain moderate Whisper
  confidence; fresh timed ending playback still needs confirmation.
- A full route/branch/endings playthrough and physical hardware testing have
  not been completed. This is not a claim of complete human proofreading.

## Source and tooling

The tagged snapshot records the selected cumulative patch tooling, generated
English battle-lettering asset and release preparation sources. The release
manifest identifies its exact commit. The accompanying provenance lists the
frozen local input hashes separately: this snapshot alone is not a complete,
one-command recipe for regenerating every historical cumulative input.
Use the `.xdelta` assets to patch your own supported discs.

The existing repository history predates this release. No original or complete
translated disc image, extracted game binary, BIOS, save, RAM capture or personal
install package is added to the release. Do not redistribute GitHub access or
publish this private project's contents without approval.

| Path | Contents |
| --- | --- |
| `docs/releases/v0.9.0/` | Release notes, release provenance and patch instructions |
| `docs/RETRO_TRANS_RELEASES.md` | Patch-only release procedure and safety rules |
| `tools/hd_ui/action_badges_english.py` | Final cumulative battle-badge build step |
| `assets/ui/battle-labels/action-badges-v1/` | Actual generated English lettering, prompt and review |
| `tests/test_action_badges_english.py` | Sprite scope, palette, provenance and disc checks |

## Translation and acknowledgements

Project direction and playtesting: **pow**. Translation, editing,
reverse engineering and tooling were assisted by large language models,
including Codex; the text is machine-produced and then edited, not represented
as a hand translation by a fluent translator. Whisper supplied the initial
post-credits voice transcripts. ImageGen supplied selected localized artwork.
Thanks to contributors and the original game's creators. Only work and review
actually documented for this project are credited; SRW-Z's contributors and
proofreading statistics are not borrowed.

This README and release structure are adapted from
[SRW-Z v0.9.90](https://github.com/retro-trans/SRW-Z/releases/tag/v0.9.90),
with Dreamcast-specific patch and save instructions.

## Do not sell this

The patch is free. Do not sell it, pre-patched discs/images, loaded memory cards,
consoles or anything made with it. Do not place downloads behind payment,
advertising or paid access. This is an unofficial fan translation; rights to
the original game remain with their respective holders.
