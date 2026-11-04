English translation of **Black/Matrix AD** for **Dreamcast**.

**v0.9.1 is a stable VGA and Redream compatibility update.** It includes the
English translation and all bundled interface and gameplay additions for both
discs. You need your own Japanese discs; no game images are distributed.

### What's new

- Fixes the half-height picture seen in Redream's VGA mode and corrects VGA
  presentation for the logo and movies. The correction keeps the native
  internal framebuffer and uses VGA line doubling instead of forcing an
  incompatible internal resolution.
- Integrates the VGA correction by **Rolly (SEGA-SKY)** without replacing the
  translated executable with an untranslated one. See the
  [original VGA patch](https://segasky.itch.io/black-matrix-ad-vga-patch-for-sega-dreamcast).
  **Do not apply that separate patch on top of this release.**
- Retains the translation, fonts, subtitles, original audio, controls and
  gameplay additions. Only video-related executable bytes change from v0.9.0.
- Adds small **v0.9.0 → v0.9.1 upgrade DCPs**, alongside full English DCPs for
  original Japanese discs. Both routes produce the same game files.

### Choose your download

| Your starting disc | Download |
| --- | --- |
| Original Japanese Disc 1 | `Black-Matrix-AD-Disc1-English-v0.9.1.dcp` |
| Original Japanese Disc 2 | `Black-Matrix-AD-Disc2-English-v0.9.1.dcp` |
| Already English-patched v0.9.0 | `Black-Matrix-AD-v0.9.0-to-v0.9.1-Upgrade-DCP.zip` — extract and select the matching disc's DCP |

Do not mix full and upgrade patches. An upgrade requires the released English
v0.9.0 game files, not the Japanese original, a different local build or a disc
already modified with another VGA patch. If verification rejects the source,
use a full patch with your original Japanese disc instead; do not bypass checks.
If you already installed the working VGA candidate, its game files are unchanged
in this release; no additional patch needs to be stacked onto it.

### Apply

Use **[Retro Trans 0.5.20 for Windows](https://github.com/retro-trans/retro-trans-tools/releases/tag/v0.5.20)**
or a newer DCP-enabled build. Download and extract `Retro-Trans-Windows.zip`, then
run `Retro-Trans.exe`.

**Original Japanese discs:** In **Automatic**, click **Refresh catalog**, select
the original Disc 1 or Disc 2 **CUE**, and choose v0.9.1. The matching full DCP is
downloaded and checked when you click **Patch**. Keep all three companion BIN
tracks beside the CUE. Initial Automatic recognition uses the published original
raw-track fingerprints; renamed tracks work if the descriptor refers to them.

**Upgrading English v0.9.0:** Download the upgrade ZIP above, extract it, and use
the **DCP** tab. Select your existing English disc's CUE or GDI, its matching
upgrade DCP, and a **new output folder**. Upgrades are manual, not Automatic.

For either route, select GDI or CUE/BIN output and boot the rebuilt descriptor.
Keep every companion track together. Never overwrite the original or select a
loose Track 3 BIN. Allow at least **12 GB** of free temporary/output space.
Keep checksum verification enabled.

Manual full-patch application also works in the DCP tab or **Apply Patch** in
[Universal Dreamcast Patcher 2.1.8](https://github.com/DerekPascarella/UniversalDreamcastPatcher/releases/tag/2.1.8).
CHD input/output is a patcher feature, not a separately tested route for this
release. Use manual DCP for alternate layouts not recognized by Automatic.

**Cold-boot the new disc and load an in-game VMU save.** Old emulator save states
can retain the previous executable. Preserve your VMUs and emulator profile;
no saves, BIOS, configuration or personal full-game packages are included.
Use the same VMU for both discs and the emulator's disc-swap function when asked.

### Additions beyond translation

- **Analog-stick movement and menu navigation**, including diagonals and normal
  held-button repeat. This uses the game's digital D-pad paths; the physical
  D-pad takes priority on each axis.
- **Faster battle Status opening and closing**, with rows appearing/disappearing
  together and a shorter opening fade. A residual pre-open pause can remain.
- **An in-battle S-rank checklist** in the battle system menu's **Turn** panel:
  Turn, CT, Blood, provisional score/target, battle-specific limits, penalties
  and relevant objectives. It reads the original scoring rules; it does not
  change scoring or guarantee a rank.
- **Checklist sprite-allocation safeguards**, reserving only the current
  battle's needed sprites and guarding empty allocations.
- **Latin-first name entry**, with English keyboard controls and all three
  original character pages still selectable.
- **Zero available from the start**, and **Domina initially highlighted** in
  master selection. The cursor default does not confirm a choice or force a route.
- **Captions for 18 unique voice clips in the post-credits scene**, retaining
  the original voices and character/master-dependent branches.
- **Native font, readability and layout improvements**, including footer labels,
  variable-width text/sampling fixes, item-list/selector alignment and raised
  movie subtitles. Localized native artwork is embedded; no HD pack is required.
- **Integrated VGA presentation correction**, retaining the cable-aware drawing
  packet-buffer allocation safeguard used by character-selection screens.

### Validation and compatibility

Both full DCPs and both upgrade DCPs are applied locally and rebuilt in **GDI and
CUE/BIN** format. The complete target game-file trees, boot invariants and CD
audio content/sample alignment are checked. Full and upgrade outputs agree.
The stable packages retain the exact game payloads of the tested VGA candidate.

The checked logo and opening movie display at full height in **Redream 1.5.0
VGA**. Flycast cold boots cover both discs in VGA and Disc 1 in composite;
composite timing is retained. **pow confirmed that VGA and Redream work.**
This report does not specify a console model, adapter or PAL/NTSC hardware setup.

A full route/ending playthrough, all movies, disc swapping and PAL/physical-console
adapter coverage are not claimed. Existing translation limitations remain:
Normal/Latent's older lettering, one unverified staff-name reading in the credits,
four brief ending calls with moderate transcription confidence, and pending
fresh timed post-credits playback. Please report issues with disc, scene,
emulator/version or console/adapter details and a screenshot.

### Credits and downloads

Project direction and playtesting: **pow**. VGA correction: **Rolly (SEGA-SKY)**.
Translation/editing and tooling were assisted by large language models including
Codex; this is machine-produced text edited afterward, not a hand translation by
a fluent translator. Whisper supplied initial ending transcripts and ImageGen
supplied selected localized artwork. Thanks to the original creators and testers.

Downloads include only DCP patches, the upgrade ZIP, instructions, checksums,
Automatic metadata and validation records. No complete images or standalone game
executables are included. The patch is free; do not sell it or anything made with it.
