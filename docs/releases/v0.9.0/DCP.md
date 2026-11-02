# v0.9.0 DCP packaging change

2026-11-02. Pow requested DCP instead of standalone raw-track xdelta. Keep the
release private and at v0.9.0; credit pow. This changes the distribution format,
not the frozen 0.1.13 translated game files. Do not move the issued v0.9.0 tag
or overwrite any old patch bytes. Existing raw-track assets are withdrawn only
after the new DCP assets have been uploaded and verified; their exact local
copies and publication receipts remain available for recovery.

## Build and prove locally

`tools/prepare_dcp_release.py` previews the frozen input identities by default.
`--freeze` copies and fingerprints the DCP adapter and authenticated UDP 2.1.8
engine into `build/dcp-v0.9.0/toolchain` on E:. `--build` performs the local DCP
build and four apply/rebuild/re-extract routes, without operating an emulator.
Upstream commit: `8b352f959bcc56ab39174c9e311b7ab7f0d522a2`.

Use the official Universal Dreamcast Patcher automatic builder to create native
per-file deltas. DCP's standard internal delta codec is distinct from offering
a standalone raw-track patch. Game-filesystem content is distributed only as
deltas. The standard `bootsector/IP.BIN` member is a 32 KiB custom boot header,
needed to preserve the translated build's EXISTING VGA flag. Authenticate it
against the frozen target: its only original-to-target byte difference is
offset 0x3d, ASCII 0 to 1. It is not uploaded as a loose game binary. No new
region/VGA/title/IP edits are introduced by packaging. The rebuilder may update
its track-table entries; all other target header bytes remain invariant.

Each DCP ZIP comment carries Retro Trans source/target game-file-tree hashes,
disc identity, original source version, target version and boot-code invariant.
This adds no manifest to the game's filesystem and remains compatible with
ordinary Universal Dreamcast Patcher. Wrong disc/source-version metadata must
fail in the DCP-enabled Retro Trans path.

Verify BOTH discs using original CUE input to GDI AND CUE/BIN output. Re-extract
the rebuilt discs, compare every game file with the frozen translated input,
check boot code except allowed TOC fields, and require identical CDDA content
and sample alignment. Record actual raw output hashes separately: rebuilding
may change raw tracks and silent padding without changing game files/audio.
GDI/CHD input and CHD output support comes from the patcher but is not separately
claimed tested for these release packages. Physical/gameplay tests remain pending.

## Publish without ambiguity

Use distinct DCP-specific asset names. The old v1 `BUILD-MANIFEST.json` describes
raw-track xdelta and must not remain as the active manifest next to DCP-only
downloads. DCP is not represented as a fictitious standard v1 patch edge.
Use `DCP-MANIFEST-v0.9.0.json`, `DCP-VALIDATION-v0.9.0.json` and separate checksum/
provenance/instruction files. Do not add this private release to the public catalog.

Freeze the packaging source in a new main-branch commit, separately identifying
the immutable translation-source commit. Preserve the dirty local working tree
and index. Upload and authenticated-download verify every DCP/document asset
before withdrawing the old exact allowlisted assets. Update README and release
body to use DCP/whole-disc-descriptor instructions. No complete images, extracted
archives, engine binaries, BIOS, saves or personal install packages are uploaded.

The two DCPs are immutable once issued. A change to translated game-file content
requires a new version, not a repackaging overwrite. Source/tag history and prior
local raw-track artifacts remain preserved as historical evidence.
