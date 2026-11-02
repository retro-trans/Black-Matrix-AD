English translation of **Black/Matrix AD** for **Dreamcast**, with separate
**DCP packages** for the Japanese **Disc 1** and **Disc 2**.

**v0.9.0 is a private experimental prerelease**, based on the frozen internal
cumulative 0.1.13 build. The release version is 0.9.0; historical local version
labels and in-game artwork are not being relabelled by an extra game rebuild.
All complete game images remain local.

### Apply

Download through your authorized GitHub account. Use **Apply Patch** in
[Universal Dreamcast Patcher 2.1.8](https://github.com/DerekPascarella/UniversalDreamcastPatcher/releases/tag/2.1.8),
or the **DCP** tab in a DCP-enabled
[Retro Trans](https://github.com/retro-trans/retro-trans-tools) build.
The public Automatic catalog does not download this private release.
You need your own original Japanese disc set, with its companion tracks.

| Your original disc | DCP package |
| --- | --- |
| Disc 1 | `Black-Matrix-AD-Disc1-English-v0.9.0.dcp` |
| Disc 2 | `Black-Matrix-AD-Disc2-English-v0.9.0.dcp` |

Select the source **CUE**, **GDI** or **CHD**, the matching DCP, and a **new output
folder**. Keep the original CUE/GDI companion tracks together. Choose GDI or
CUE/BIN output, apply, and boot the rebuilt descriptor. Do not select a loose
Track 3 BIN or overwrite originals. Allow at least 12 GB of temporary/output space.
The discs are not interchangeable, and these packages do not upgrade local test
builds. Keep checksum verification enabled.

Each DCP contains native per-game-file deltas and the standard 32 KiB custom
boot header retaining the existing VGA flag, not complete disc images or archives. A
DCP-enabled Retro Trans build also verifies the source/target game-file-tree
metadata, boot invariants and audio. DCP rebuilds the layout, so raw track hashes
can differ from the earlier Track 3 release despite identical translated files.
GDI/CHD inputs and CHD output are patcher features, not separately verified routes
for this release; local tests use original CUE input to GDI and CUE/BIN output.

**Boot fresh and load an in-game VMU save.** Old save states may retain old code
or graphics. Keep your original VMUs/profile and backups; no saves, BIOS,
emulator configuration or personal full-game install package is distributed.
Use the same VMU for both discs and the emulator's disc-swap function when asked.

### What is included

- **Cumulative English translation and interface work**, as already integrated
  into the frozen two-disc build. Working-tree changes not built into those
  exact outputs are not automatically included.
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
  Domina is first in master selection. Existing VGA compatibility repairs remain.

### Validation and testing status

Both DCP packages are applied locally to the original CUE disc sets, rebuilt
in GDI and CUE/BIN format, then re-extracted. All game files match the frozen
0.1.13 translated build, boot code outside allowed track-table fields matches,
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

The existing tag remains the immutable translation source snapshot; current main
adds DCP packaging sources. The DCP manifest identifies both commits. Provenance
lists the local cumulative inputs; the tag alone is not a complete historical
rebuild recipe. The earlier standalone raw-track assets are superseded by DCP,
with translated game-file content unchanged. Use the `.dcp` downloads with your
own supported original discs. Keep the repository/release
private; no public patch catalog addition or visibility change is authorized.

### Translation and acknowledgements

This is a machine translation produced with large language models and then
edited, not a hand translation by a fluent translator. Project direction and
playtesting: **pow**. Codex assisted editing/tooling, Whisper supplied
initial ending transcripts, and ImageGen supplied selected localized artwork.
Thanks to contributors and the original game's creators.

Bug reports, proofreading and playtesting are welcome in this private
repository's Issues. Include the disc/version/route and reproduction details;
do not attach game images or personal saves. Structure adapted from the
[SRW-Z v0.9.90 release](https://github.com/retro-trans/SRW-Z/releases/tag/v0.9.90).

The patch is free. Do not sell it or anything made with it.
