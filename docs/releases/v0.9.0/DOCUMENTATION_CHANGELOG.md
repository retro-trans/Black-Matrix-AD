# Release documentation changes

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
