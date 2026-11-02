# Bundled feature audit — v0.9.0

Reviewed 2026-11-02 after pow reported omissions in “Additions beyond translation.”
This is a documentation correction, not a new game build or patch version.

The audit reads the extracted executable from each frozen internal 0.1.13
target and first verifies its SHA-256 against `DCP-MANIFEST-v0.9.0.json`:

| Disc | Released `1ST_READ.BIN` SHA-256 |
| --- | --- |
| 1 | `cb786acf096f4eaca0554138e3e142b495b71cfd45c7ac05ae27aaaa950d4a7e` |
| 2 | `14cb5d84b9cd595b7a964958021bd43da4701c401f133b2802909cc88b16e066` |

It then compares the emitted patch instructions, dispatch pointers and data with
both executables. **All 43 checks pass on each disc.** See the metadata-only
[audit results](FEATURE_AUDIT.json). No original scripts or game binaries are
included in this audit.

| Bundled feature | Checked implementation |
| --- | --- |
| Analog-stick digital movement/navigation | Input hook at `8C09FBE0` and helper at `8C0F2600`; original D-pad priority and input-repeat path retained |
| Faster Status opening/closing | Six scoped queue/animation/driver helpers, eight dispatch pointers and both opening-fade operands |
| S-rank checklist | Renderer, scoring reader, original-derived battle rules, row/string tables, drawing helper and vector status marks |
| Checklist allocation safeguards | Map-specific allocation helper at `8C0F2B00`, constructor pointer and renderer empty-allocation guards |
| Latin-first name entry | Initializer/helper, helper pointer and all eight control-label spacing sites; original keyboard tables retained |
| Zero unlock and Domina cursor default | Three native unlock initialization edits and the separate initial-highlight instruction |
| VGA packet-buffer repair | Cable-aware allocation helper at `8C0F4890` and its startup call pointer |

Post-credits caption and native-font/layout scope remains documented in the
existing release notes and the per-feature changelogs. The expanded list does
not imply that these are newly added to v0.9.0: they were already in the issued
game-file content.

## Exclusions and limits

- Historical experiments are not automatically release features. In particular,
  the old single-page pickup expansion is **not** claimed: the frozen executable
  still has the original 15-column operand at file offset `0x3E7D2`.
- External HD portrait/background replacements, alternate font trials,
  emulator-specific configuration and full-game/Steam Deck installers are not
  distributed with these DCPs.
- Analog support maps to digital directions, not variable-speed movement.
  Status retains an unresolved pre-open pause. The checklist is provisional,
  does not change scoring, and is not a guarantee of S rank or a universal
  freeze fix.
- This is static content verification, not fresh gameplay, GPU appearance,
  controller, route, ending-timing or physical Dreamcast testing.
- Both DCP assets, all other issued asset bytes, the v0.9.0 tag and game content
  remain unchanged. Only current README/release documentation is revised.
