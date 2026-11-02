# Black Matrix AD: preparing Retro Trans-compatible patches

> **Superseded distribution choice (2026-11-02): use DCP.** The user explicitly
> requested DCP instead of standalone raw-track xdelta. Follow
> `docs/releases/v0.9.0/DCP.md` for the current format and validation model.
> The raw-track protocol instructions below are historical, not the current
> publication route. Keep original and complete translated images local.

This guide prepares a future patch-only distribution. Keep this project private;
documentation, fixes and local builds do not authorize tags, releases, uploads,
visibility changes or publication in the public patch catalog. Perform those
actions only on an explicit user request. No game build or release is performed
by adding these instructions.

Read docs/HANDOFF.md and the selected build/profile's own guide before choosing
inputs. Several native, HD and gameplay trial outputs coexist. Do not assume
the newest folder is the approved release or combine unrelated trial images.

## The patch unit is one exact BIN file

The project uses two Dreamcast discs with CUE descriptors and multiple BIN
tracks. Existing build tooling injects game changes into a Track 3 BIN copy.
The desktop patcher patches exact bytes of a single file; it does not assemble
a disc, parse a CUE, patch an entire folder, extract CHD, or install HD textures.

- Compare the approved output with the original for each disc and track. Make
  a patch for every changed track. Do not assume all other tracks are unchanged
  without comparing their hashes.
- Keep Disc 1 and Disc 2 identities separate, even when the inner executable or
  shared text is similar. Never use a Disc 1 BIN as a Disc 2 source.
- Use a BIN source for a BIN patch. A CUE, CHD, ZIP or extracted 1ST_READ.BIN is
  not interchangeable with the complete Track 3 image. Conversion, if separately
  needed, is outside this app and must produce the exact documented source bytes.
- Preserve the complete original disc sets. Save patched copies into new paths;
  never point an output at an original or an existing translated image.

## Stable identities and variants

Use these values for the first standard release stream:

| Field | Value |
| --- | --- |
| game_id | black-matrix-ad-dreamcast |
| game_name | Black/Matrix AD |
| platform | Dreamcast |
| language | en |
| source_format / target_format | bin / bin |
| edition, Disc 1 native Track 3 | jp-disc1-track3-native |
| edition, Disc 2 native Track 3 | jp-disc2-track3-native |

These IDs are proposed for the first standard release; preserve them once issued.
Use additional stable edition IDs for different byte-level profiles, for example
jp-disc1-track3-hd or jp-disc1-track3-native-analog. Include the disc, track and
profile in the ID. Optional HD textures alone do not create a different BIN
identity if the underlying image bytes are the same.

One pristine source can match several profile entries. The app then asks the
user to select a recognized edition/profile. Do not disguise that choice by
claiming different outputs have the same edition/version. The current route
planner keeps editions separate; it does not automatically switch native/HD,
normal/analog, discs or tracks.

Choose the target numeric version only when the user requests release preparation
and the exact approved outputs are frozen. All entries in one manifest share
that target version. Use original for pristine inputs and an exact issued
numeric version for previous translated inputs. Trial folder labels are not
stable manifest versions. Reusing a version for different bytes is forbidden.

source_commit must be the full commit that actually contains the sources used
to build the target. A HEAD hash that omits relevant local changes is not an
accurate build reference. Resolve that before final release validation, without
silently committing unrelated work or publishing the private source.

## Configure and build locally, when requested

Install Python 3.12+ on Windows x64 and the pinned shared builder:

```powershell
python -m pip install git+https://github.com/retro-trans/retro-trans-tools.git@v0.2.1
```

Copy docs/retro-trans-release.example.json to ignored
build/retro-trans/release-local.json. Replace all SET_* and REPLACE_* values
with the agreed version, actual source commit and exact original/target BIN
paths. The template is intentionally incomplete; it neither assigns a version
nor claims any current output is approved. Paths resolve relative to the local
configuration file; use absolute paths if that is clearer.

The template describes a full patch for each disc's native Track 3. Remove an
entry if that disc is not actually included in the approved release, and state
the reduced scope. Add changed tracks or approved profiles as separate entries
with unique patch asset names and edition IDs.

For incremental upgrades, add an entry for each supported prior image: same
edition/language and final target, source_version set to the previous numeric
version, source pointing to that exact previous BIN. Generate a direct full
patch from the original as well when available. Do not declare an upgrade
connection that has not been generated and decoded successfully.

After reviewing the configuration and disk space, run from the project root:

```powershell
python -m retro_trans.release build build/retro-trans/release-local.json --out build/retro-trans/ready
python -m retro_trans.release validate build/retro-trans/ready
```

The shared builder has no --dry-run switch: it performs real encoding and
verification. Use a NEW output directory; preserve prior ready directories.
Every patch is applied back to its declared source and checked against the
entire desired output's SHA-256. Source/output/patch SHA-256 and byte sizes are
generated together. Inputs remain local and unchanged.

A successful directory contains exactly one BUILD-MANIFEST.json, its referenced
.xdelta files, SHA256SUMS.txt and VALIDATION.json. Do not substitute a local HD
pack manifest or SHA256SUMS file for these protocol files. Keep optional extras
and their own checksums separate.

## Private testing with the desktop app

The app currently has no private-project login, authenticated private-release
download flow or local catalog-import UI. Its Automatic tab uses the public
catalog and public release assets. A local manifest does not enroll this private
project automatically.

For an authorized private test, obtain the verified delta through the project's
authorized private channel. In Apply xdelta, select the exact source Track 3
BIN, the corresponding .xdelta and a new output path. Repeat separately for
each changed track/disc. Manual mode checks xdelta's embedded checksums; also
compare the complete output SHA-256 and byte size to BUILD-MANIFEST.json.

Make a new complete local disc folder for testing. Copy the unchanged tracks
and CUE from the user's own disc set after verifying they are unchanged. Save
the patched track under the original basename in that NEW folder, or update
only the FILE filename references in a copied CUE to match renamed outputs.
Preserve TRACK, INDEX, sector and timing information. Launch the matching CUE,
not a loose BIN, and handle Disc 2 separately. The app does not rewrite CUEs
or manage disc swapping.

HD texture packs remain separate optional assets with their own installation
instructions and checksums. Record which patched BIN profiles they match.
Verify both discs and any offered native/HD/analog variants in the intended
runtime; a successful binary round trip is not a gameplay or visual test.

## Future publication requires an explicit request

Keep the project, private manifests and private URLs out of the public catalog
until authorized. Do not copy credentials into the app or widen the public
catalog job's token to enumerate private projects. If the user wants public
patches while keeping source private, use an explicitly approved public
patch-only repository and only approved metadata/artifacts.

Publish the validated protocol artifacts plus separately reviewed documentation
and extras. Never upload original/translated BINs, complete disc folders, BIOS,
saves or personal full-game install packages. In particular, the Steam Deck
package described in docs/STEAM_DECK.md includes game binaries and is not a
public patch distribution. Source archives need their own content review.

Use a stable tag matching the manifest's numeric version, optionally prefixed
with v. Verify uploaded asset names, sizes and SHA-256 against the validated
local directory before publishing a draft. Do not replace issued patch bytes;
corrections require a new version. GitHub checks protocol asset integrity;
the original-game round trips stay local.

Once explicitly approved and publicly accessible under retro-trans, valid
standard releases can be picked up by the central hourly/manual catalog job.
Private releases cannot be downloaded automatically by the current desktop app.
No automatic publishing workflow is added by this guide.

Protocol reference: [Retro Trans release standard](https://github.com/retro-trans/retro-trans-tools/blob/v0.2.1/docs/RELEASE_STANDARD.md).
