English translation of **Black/Matrix AD** for **Dreamcast**, with separate
patches for the Japanese **Disc 1** and **Disc 2** raw Track 3 BIN files.

**v0.9.0 is a private experimental prerelease**, based on the frozen internal
cumulative 0.1.13 build. The release version is 0.9.0; historical local version
labels and in-game artwork are not being relabelled by an extra game rebuild.
All complete game images remain local.

### Apply

Download through your authorized GitHub account, then use **Apply xdelta** in
[Retro Trans](https://github.com/retro-trans/retro-trans-tools), DeltaPatcher or
xdelta3. The public Automatic catalog does not download this private release.
You need your own exact Japanese disc dumps.

| Your source file | Patch |
| --- | --- |
| Original Japanese Disc 1, raw Track 3 BIN | `Black-Matrix-AD-Disc1-Native-v0.9.0-from-original.xdelta` |
| Original Japanese Disc 2, raw Track 3 BIN | `Black-Matrix-AD-Disc2-Native-v0.9.0-from-original.xdelta` |

The discs are not interchangeable. These are full patches from original files;
there are no upgrade patches from local test builds. Check `README-v0.9.0.txt`
and `BUILD-MANIFEST.json` for source sizes/hashes. Keep checksum verification on.
The CUE, CHD, merged BIN and extracted executable are not substitute sources.

Create a new output folder before running, for example:

```text
xdelta3 -d -s "Black-Matrix Advanced (Japan) (Disc 1) (Track 3).bin" "Black-Matrix-AD-Disc1-Native-v0.9.0-from-original.xdelta" "patched-disc1/Black-Matrix Advanced (Japan) (Disc 1) (Track 3).bin"
```

Repeat with Disc 2's source/patch. Copy each disc's unchanged Track 1, Track 2
and CUE from your own original set into its new folder; retain the original
basenames and CUE timing. Boot the **matching CUE**, not a loose BIN. Originals
must not be overwritten. Converting a CHD is outside this patch procedure and
must yield the exact documented source bytes.

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

Both full patches are decoded locally from their exact original source files
and verified against each complete target's size and SHA-256. The protocol
manifest, validation report and checksums record those identities. Companion
tracks/CUEs are independently compared, and the local cumulative build passed
whole-track change-scope/parity and every-ISO-payload checks. The latest badge
tests and existing Join/Equip checks passed; the release provenance separates
binary verification from gameplay evidence.

**This is not a full-playthrough or complete-human-proofreading claim.** Fresh
gameplay/contrast checks for the latest battle badges, Join and Equip are still
pending. Normal/Latent's older lettering is unchanged. The battle atlas audit
does not establish that all Japanese images throughout the game are translated.
One scrolling-credit staff name retains Japanese because its reading is not
verified; four brief ending calls retain moderate Whisper confidence. Fresh
post-credits timed playback, remaining route/branch checks and physical
Dreamcast hardware testing remain pending.

### Downloads and source

No complete game images are distributed. Downloads contain two patches, one
build manifest, validation records, checksums, provenance and instructions.
Native translated graphics are already in the patches. No optional HD texture
pack or personal Steam Deck/full-game ZIP is bundled.

The tag records the selected patch tooling and release sources. Provenance
lists the local cumulative inputs separately; the tag alone is not a complete
recipe to regenerate every historical translated input. Use the `.xdelta`
downloads with your own supported original discs. Keep the repository/release
private; no public patch catalog addition or visibility change is authorized.

### Translation and acknowledgements

This is a machine translation produced with large language models and then
edited, not a hand translation by a fluent translator. Project direction and
playtesting: **binhlt0402**. Codex assisted editing/tooling, Whisper supplied
initial ending transcripts, and ImageGen supplied selected localized artwork.
Thanks to contributors and the original game's creators.

Bug reports, proofreading and playtesting are welcome in this private
repository's Issues. Include the disc/version/route and reproduction details;
do not attach game images or personal saves. Structure adapted from the
[SRW-Z v0.9.90 release](https://github.com/retro-trans/SRW-Z/releases/tag/v0.9.90).

The patch is free. Do not sell it or anything made with it.
