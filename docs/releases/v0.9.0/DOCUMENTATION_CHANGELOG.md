# Release documentation changes

## 2026-11-03 — mark v0.9.0 as the latest stable release

At pow's request, removed the experimental designation from the current README,
release notes and downloadable instructions, and promoted the existing v0.9.0
release from prerelease to Latest. Refreshed the instructions' checksum. Retained
specific validation and compatibility limits; no new gameplay or hardware testing
is claimed. The two DCP packages, game content and version tag are unchanged.
The local v0.9.1 VGA test and upgrade packages are not published by this change.

## 2026-11-02 — focus public descriptions on the game

At pow's request, removed repository-sanitation/replacement narrative, internal
build-version comparisons and superseded distribution details from the current
README and release notes. Kept installation, features, validation limits, credits
and safety guidance. Historical technical records and issued assets are unchanged.

## 2026-11-02 — complete the bundled enhancements list

At pow's request, replaced the abbreviated “Additions beyond translation” list
in the README and live release notes. Added analog-stick navigation, simultaneous
Status opening/closing, the in-battle S-rank checklist, its map-specific
sprite-allocation safeguards, and Latin-first name entry. Expanded the native
font/layout and VGA packet-buffer descriptions; retained Zero, Domina and ending
captions with their existing limits.

Read-only comparison against both manifest-authenticated frozen release
executables passes 43 checks per disc. Added `FEATURE_AUDIT.md` and metadata-only
`FEATURE_AUDIT.json`. Explicitly excluded unshipped historical pickup expansion,
external HD packs and personal installers. No scoring/balance change, guaranteed
rank, eliminated Status pause, universal freeze cure or new playtest is claimed.
No game rebuild, new tag/version, asset upload/replacement or visibility change.

## 2026-11-02 — Automatic DCP discovery

Added `DCP-AUTOMATIC.json` and its separate supplemental checksum to the
existing v0.9.0 release, retaining all eight issued assets unchanged. Retro Trans
0.5.20 imports these as independent DCP catalog records; both original Japanese
CUE/BIN sets are recognized and the matching DCP downloads on Patch. Updated
README/live release instructions for Automatic, retaining the manual DCP tab
for CHD and alternate layouts. No standalone xdelta or fake binary manifest is
introduced. The game version, DCPs and original translation tag do not change.

## 2026-11-02 — additions beyond translation

At pow's request, added a dedicated section to the public README and release
notes listing the bundled changes beyond translation: Zero's native unlock,
Domina's initial selection highlight, new post-credits voice captions,
readability/layout improvements, and retained VGA compatibility repairs.

Clarified that the Domina change is a cursor default, not a reordered character
table or forced route. Retained the pending fresh ending-playback and physical
hardware checks. This is documentation only: no game rebuild, new version/tag,
patch replacement or change to issued release assets.
