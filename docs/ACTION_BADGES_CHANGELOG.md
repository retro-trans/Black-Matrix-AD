# Private cumulative 0.1.13 — English battle badges

2026-11-02. User requested that the bottom-left Magic label be added to the
game and that similar Japanese battle badges be found and translated.

Completed local pair: `output/patched-discs-action-badges-2026-11-02`, derived
from complete 0.1.12 Join build. Builder: `tools/hd_ui/action_badges_english.py`.
Use `Play - Disc 2 - English Action Badges.cmd` (or Disc 1).

## Audit and translation

All 169 descriptors of CHAR.DAT texture 0x1350 were inspected. Twelve remaining
Japanese label groups occupied 14 descriptors. These are now Miss!, Guard,
Stone, Poison, Paral., Status, Sleep, Up, Down, Freeze, Stance, and Magic.
Stance spans descriptors 104–106; all other groups have one descriptor.
Stone is the existing compact petrification condition term; Paral. explicitly
abbreviates paralysis, not the verb Paralyze. Stance matches the defensive
response menu/help context. Independent accuracy review 12/12, independent
editorial review of actual packed labels 12/12, main final proof 12/12.

This is a complete audit of this primary battle atlas, NOT a whole-game claim.
Normal/Latent lettering, Move, Attack, Thinking, English components, digits,
icons, turn letters, effects and all other 155 descriptors remain unchanged.

## Actual artwork, not a reference

Built-in ImageGen produced the actual replacement lettering. Selected output
and exact final prompt are saved at:

- `assets/ui/battle-labels/action-badges-v1/generated-lettering.png`
- `assets/ui/battle-labels/action-badges-v1/prompt.txt`
- English mapping/review: `assets/ui/battle-labels/action-badges-v1/labels.en.json`

Asset SHA256: `3a04fe2944bdfc2081e1dd716e0f8c24451c41d90ff97a91e98c725478f64a65`.
The generated alpha, not old font masks, contributes the packed pixels. One
common 512×256 to 73×43 conversion and threshold 96 apply to every word;
there is no per-word scaling. Transparent RGB is ignored. Ink is cropped and
centered into original native rectangles with original palette peak and a
one-pixel lower-right black shadow. Native one-bit alpha is retained. No full
outline or opaque backing box. Initial too-small conversion lost strokes and
was rejected; final preparation is `build/action-badge-prepared-v2-2026-11-02`.

Actual packed before/after preview (4× nearest, NOT a gameplay screenshot):
`output/patched-discs-action-badges-2026-11-02/action-badges-packed-preview.png`.
Stone has a dense final e; Miss! keeps its original dark red. Fresh in-game
legibility/contrast and physical-hardware verification remain pending, status
`private-action-badges-runtime-pending`. No live game was operated.

## Exact change scope and verification

Source CHAR.DAT SHA256:
`eb0176d000002d84f8288fae6e36ccb2335aa6faae169643a27f7224faa19edf`.
New CHAR.DAT SHA256 (both discs):
`71747341a17c0468dc6c8e560bcb0b814bba9c86ab8d48af344f34f4c72297dc`.
Only 5,981 CHAR bytes differ. Archive size, headers, descriptors, other pixels,
all executable code, scripts, audio, movies and prior fixes remain exact.

Whole-track exact-change/parity verification, every ISO payload, boot/directory,
companion file and CUE checks passed for both discs. Eight new regression tests
pass after delivery, including actual embedded CHAR/EXE, asset provenance,
all 155 unchanged descriptors, split Stance, alpha, palette, source guards and
mocked launch. Existing Join/Equip regression suite also ran successfully
(20 tests). Manifests remain ASCII-escaped for the GBK-default launcher.

Disc 1 Track 3 SHA256:
`4eb243d79a6052e4b0a643b06c23e088acb00382ccf617538a5f087b5968c268`.
Disc 2 Track 3 SHA256:
`fc652c477c7a61227a332267cfe2d4153068953cf0f3710717702f759222130e`.
Sixteen raw sectors differ per disc:

- D1: 66853, 66854, 66875–66878, 66880–66884, 66886–66888, 66903, 66904.
- D2: 114743, 114744, 114765–114768, 114770–114774, 114776–114778, 114793, 114794.

Executable identities are UNCHANGED from 0.1.12 and still differ per disc:

- D1: `cb786acf096f4eaca0554138e3e142b495b71cfd45c7ac05ae27aaaa950d4a7e`.
- D2: `14cb5d84b9cd595b7a964958021bd43da4701c401f133b2802909cc88b16e066`.

Loose `1ST_READ.BIN` is D2, `1ST_READ.disc1.BIN` is D1. Join, Equip fallback,
English credits, story cards, movie safe areas and post-credits captions retained.

## Safety and handoff

Close Flycast before using the new launcher. It retains the SAME original
E: VGA-v2/play profile/VMUs, latest old save Port A Slot 2 and frozen 1440
launch-only settings. Existing Flycast is refused. No emulator launch/input/
restart or save/card/config/profile writes were performed; launches were mocked.
Original discs and earlier builds preserved. E: project outputs only, no M:
writes. Complete binaries remain private/local: no upload, tag, release,
publication, visibility or public patch catalog changes.
