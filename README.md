# Black/Matrix AD — English translation

English translation and native interface work for **Black/Matrix AD** on
**Dreamcast**, covering the Japanese two-disc edition.

The current release is
**[v0.9.0](https://github.com/retro-trans/Black-Matrix-AD/releases/tag/v0.9.0)**,
the latest stable English translation patch.
The release number identifies the translated game-file content; it does not imply that
every route, screen or line has passed human review or a complete playthrough.

## Contribute

Bug reports, proofreading and playtesting are welcome through this
repository's Issues. Include your disc, patch version, route, screenshot and
reproduction steps. Do not attach complete game images, BIOS files or personal
memory cards. Machine review is not counted as human proofreading.

## Play it

Download the patches and instructions from the
[v0.9.0 release](https://github.com/retro-trans/Black-Matrix-AD/releases/tag/v0.9.0).
You need your own exact Japanese disc dumps. No game image is distributed.

### Apply

Use **[Retro Trans 0.5.20 for Windows](https://github.com/retro-trans/retro-trans-tools/releases/tag/v0.5.20)**
and its **Automatic** tab. Download `Retro-Trans-Windows.zip`, extract it and
run `Retro-Trans.exe`; the ZIP includes the required runtime notices.

Click **Refresh catalog** first (especially after upgrading), then browse to
your original Japanese Disc 1 or Disc 2 **CUE**, with all three BIN
tracks together. Automatic identifies the disc, offers **v0.9.0**,
and downloads the matching DCP when you click **Patch**. Choose a **new output
folder** and GDI or CUE/BIN output. Every original track, downloaded package,
rebuilt game file, boot invariant and CD-audio content is verified.

Initial Automatic recognition uses the published original raw-track fingerprints;
a renamed CUE/track set is accepted when the CUE refers to the renamed tracks.
For CHD inputs or alternate layouts, use the separate **DCP** tab with a manually
downloaded package, or **Apply Patch** in
[Universal Dreamcast Patcher 2.1.8](https://github.com/DerekPascarella/UniversalDreamcastPatcher/releases/tag/2.1.8).
Use the Windows build linked above for these instructions.

| Your original Japanese disc | DCP package |
| --- | --- |
| Disc 1 | `Black-Matrix-AD-Disc1-English-v0.9.0.dcp` |
| Disc 2 | `Black-Matrix-AD-Disc2-English-v0.9.0.dcp` |

When applying manually, select the original disc's **CUE**, **GDI** or **CHD**, then its matching DCP and
a **new output folder**. Keep every companion track beside its CUE/GDI. Choose
GDI or CUE/BIN output and apply; use the rebuilt descriptor to play. Do not
select a loose Track 3 BIN or copy old tracks over the rebuilt result. Never
overwrite your originals. Allow at least 12 GB of temporary/output space.

The two discs are not interchangeable. These are full packages from the original
Japanese game files, not upgrades from local test builds. The package's source
and target game-file-tree hashes are in `DCP-MANIFEST-v0.9.0.json`; a DCP-enabled
Retro Trans build verifies that metadata, boot invariants and audio. Ordinary
Universal Dreamcast Patcher applies the native per-file patch checks.

DCP rebuilds the disc layout and verifies the translated game files. Local
verification covers original CUE input to GDI and CUE/BIN output on both discs.
GDI/CHD input and CHD output are supported by the patcher, but are not separately
claimed tested for these packages. Keep verification enabled and report any
source mismatch rather than forcing it through.

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

The patch also includes **Zero unlocked from the beginning** and
**Domina initially highlighted in master selection**. It is not a
translation-only, original-unlock-order profile.

## Additions beyond translation

- **Analog-stick movement and menu navigation.** The game itself maps the
  Dreamcast analog stick to its existing D-pad input paths, including diagonals
  and normal held-button repeat. The physical D-pad takes priority on each axis.
  This is digital-style navigation, not new 360-degree or variable-speed movement;
  map your controller's stick to the Dreamcast analog stick in your emulator.
- **Faster battle Status opening and closing.** Status elements appear and
  disappear together instead of revealing/removing each row in sequence, with
  the preceding opening fade shortened. A residual pre-open pause is not claimed
  eliminated; the original readiness checks and selection writeback remain.
- **An in-battle S-rank checklist.** The battle system menu's **Turn** panel
  shows Turn, CT, Blood, the provisional score and S-rank target, battle-specific
  Turn/CT limits, tracked penalties, and relevant special objectives. Green
  checks, red crosses and gray pending marks make progress easier to read.
  It reads the game's own scoring rules and counters; it does not change scoring,
  award S ranks, or guarantee a rank before the battle ends. Unranked battles are
  identified, and special rows appear only where relevant.
- **Checklist sprite-allocation safeguards.** The checklist reserves only the
  sprites needed for the current battle instead of always reserving 384, leaving
  more of the fixed engine pool available for other menus. Empty-allocation
  guards are included. This addresses the investigated checklist-related Start
  menu resource shortage, not every possible freeze or out-of-memory condition.
- **Latin-first name entry.** The name-entry screen starts on its Latin page
  and uses English Hira / Kata / Latin / Back / Done controls. All three original
  keyboard pages remain selectable; the saved-name format is unchanged.
- **Zero available from the start.** The game's native unlock is enabled at
  initialization, so the original unlock code is not required.
- **Domina initially highlighted in master selection.** This changes the
  starting cursor, not character/route order, and does not confirm a choice
  or force a route. Zero remains available.
- **Subtitles for the previously voice-only post-credits scene.** Added native
  captions for 18 unique voice clips while retaining the original voices and
  character/master-dependent branches. Fresh playback/timing checks remain pending.
- **Readability and layout improvements.** Redrawn/repaired native fonts and
  button labels, variable-width text/sampling repairs, item-list and selector
  alignment fixes, and raised movie subtitles to reduce bottom-edge clipping.
  Native translated artwork and the current font fixes are embedded in the disc
  patches; no external HD texture pack is needed.
- **VGA compatibility repairs.** Retains VGA boot/video work and a cable-aware
  graphics packet-buffer allocation correction used by the character-selection
  screens. This is not a verified physical-Dreamcast compatibility claim.

These additions are bundled in v0.9.0; it is not a strict translation-only patch.
The list was checked against both release executables; see the
[feature audit](docs/releases/v0.9.0/FEATURE_AUDIT.md).
External HD portrait/background packs and personal Steam Deck installers are not
bundled. Automated checks do not replace gameplay, route or hardware testing.

## What is included

- English script and native interface work for both discs.
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

Both DCP packages are applied to their original CUE sets, rebuilt as GDI and
CUE/BIN, and re-extracted. Every game file must match the frozen translated build;
boot code outside allowed track-table fields and CD audio content/sample alignment
must be preserved. The DCP manifest, verification records and checksums accompany
the packages. These checks do not replace gameplay or hardware testing.

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

This repository contains translation tooling, localized artwork, tests and
patch documentation. The release includes DCP packages, checksums and validation
records for use with your own original Japanese discs.

No original or complete translated disc image, extracted game binary, BIOS,
save, RAM capture or personal install package is distributed. Do not upload
game images, original dialogue sources or personal saves.

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
