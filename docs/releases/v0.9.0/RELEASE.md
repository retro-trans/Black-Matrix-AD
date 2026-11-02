English translation of **Black/Matrix AD** for **Dreamcast**, with separate
**DCP packages** for the Japanese **Disc 1** and **Disc 2**.

**v0.9.0 is an experimental English translation patch.** You need your own
original Japanese discs; no complete game images are distributed.

### Apply

Use **[Retro Trans 0.5.20 for Windows](https://github.com/retro-trans/retro-trans-tools/releases/tag/v0.5.20)**
and its **Automatic** tab. Download `Retro-Trans-Windows.zip`, extract it and
run `Retro-Trans.exe`; the ZIP includes the required runtime notices.

Click **Refresh catalog** first (especially after upgrading), then browse to
your original Japanese Disc 1 or Disc 2 **CUE**, keeping all three BIN
tracks together. Automatic identifies the disc, offers experimental **v0.9.0**
and downloads its matching DCP when you click **Patch**. Choose a new output
folder and GDI or CUE/BIN output. Original tracks and downloaded packages are
hash-verified; rebuilt game files, boot invariants and CD audio are verified.

Initial recognition uses the published original raw-track fingerprints; renamed
files are accepted when the descriptor refers to them. For CHD inputs or
alternate layouts, manually apply the package in the **DCP** tab, or use
**Apply Patch** in
[Universal Dreamcast Patcher 2.1.8](https://github.com/DerekPascarella/UniversalDreamcastPatcher/releases/tag/2.1.8).
Use the Windows build linked above for these instructions.
You need your own original Japanese disc set, with its companion tracks.

| Your original disc | DCP package |
| --- | --- |
| Disc 1 | `Black-Matrix-AD-Disc1-English-v0.9.0.dcp` |
| Disc 2 | `Black-Matrix-AD-Disc2-English-v0.9.0.dcp` |

For manual application, select the source **CUE**, **GDI** or **CHD**, the matching DCP, and a **new output
folder**. Keep the original CUE/GDI companion tracks together. Choose GDI or
CUE/BIN output, apply, and boot the rebuilt descriptor. Do not select a loose
Track 3 BIN or overwrite originals. Allow at least 12 GB of temporary/output space.
The discs are not interchangeable, and these packages do not upgrade local test
builds. Keep checksum verification enabled.

Each DCP contains native per-game-file deltas and the standard 32 KiB custom
boot header retaining the existing VGA flag, not complete disc images or archives. A
DCP-enabled Retro Trans build also verifies the source/target game-file-tree
metadata, boot invariants and audio. DCP rebuilds the disc layout and verifies
the translated game files.
GDI/CHD inputs and CHD output are patcher features, not separately verified routes
for this release; local tests use original CUE input to GDI and CUE/BIN output.

**Boot fresh and load an in-game VMU save.** Old save states may retain old code
or graphics. Keep your original VMUs/profile and backups; no saves, BIOS,
emulator configuration or personal full-game install package is distributed.
Use the same VMU for both discs and the emulator's disc-swap function when asked.

### What is included

- **English script and native interface work for both discs.**
- **Font and alignment repairs**, including Equip's validated live-font fallback,
  Join's matching footer font, other footer work and menu/battle alignment fixes.
- **Story cards, disc prompts, English credits and subtitles.** Retains the
  translated cards, raised movie subtitles and native captions for 18 unique
  voices in the post-credits angel-CG sequence.
- **Battle badge translations.** Audited the complete 169-descriptor primary
  battle atlas and replaced 12 Japanese label groups across 14 descriptors:
  Miss!, Guard, Stone, Poison, Paral., Status, Sleep, Up, Down, Freeze, Stance,
  Magic. Actual generated lettering is integrated, with original native geometry
  and palette. All other atlas descriptors are preserved.
- **Development-profile choices retained:** Zero is unlocked from the start;
  Domina is initially highlighted in master selection. Existing VGA compatibility
  repairs remain.

### Additions beyond translation

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
[feature audit](https://github.com/retro-trans/Black-Matrix-AD/blob/main/docs/releases/v0.9.0/FEATURE_AUDIT.md).
External HD portrait/background packs and personal Steam Deck installers are not
bundled. Automated checks do not replace gameplay, route or hardware testing.

### Validation and testing status

Both DCP packages are applied locally to the original CUE disc sets, rebuilt
in GDI and CUE/BIN format, then re-extracted. All game files match the verified
translation target, boot code outside allowed track-table fields matches,
and CD audio content/sample alignment is preserved. DCP manifests and validation
records document the file-tree identities and actual rebuilt output hashes.
The underlying cumulative build retains its prior scope/parity and badge/font
checks. These binary checks do not constitute gameplay or hardware testing.

**This is not a full-playthrough or complete-human-proofreading claim.** Fresh
gameplay/contrast checks for the latest battle badges, Join and Equip are still
pending. Normal/Latent's older lettering is unchanged. The battle atlas audit
does not establish that all Japanese images throughout the game are translated.
One scrolling-credit staff name retains Japanese because its reading is not
verified; four brief ending calls retain moderate Whisper confidence. Fresh
post-credits timed playback, remaining route/branch checks and physical
Dreamcast hardware testing remain pending.

### Downloads and source

No complete game images are distributed. Downloads contain two DCP packages,
DCP-specific manifest/validation records, checksums, provenance and instructions.
Native translated graphics are already in the patches. No optional HD texture
pack or personal Steam Deck/full-game ZIP is bundled.

The repository contains translation tooling, localized artwork, tests and patch
documentation. Use the `.dcp` downloads with your own supported original discs.

### Translation and acknowledgements

This is a machine translation produced with large language models and then
edited, not a hand translation by a fluent translator. Project direction and
playtesting: **pow**. Codex assisted editing/tooling, Whisper supplied
initial ending transcripts, and ImageGen supplied selected localized artwork.
Thanks to contributors and the original game's creators.

Bug reports, proofreading and playtesting are welcome in this
repository's Issues. Include the disc/version/route and reproduction details;
do not attach game images or personal saves. Structure adapted from the
[SRW-Z v0.9.90 release](https://github.com/retro-trans/SRW-Z/releases/tag/v0.9.90).

The patch is free. Do not sell it or anything made with it.
