# v0.9.1 — VGA and Redream compatibility

2026-11-04. Release requested by pow after confirming VGA and Redream work.

- Integrated Rolly (SEGA-SKY)'s VGA video correction and restored the native
  startup video-call path, fixing the half-height VGA presentation.
- Changed 513 bytes of each English executable; no other game files change from
  v0.9.0. Retained the cable-aware packet-buffer allocation safeguard.
- Retained all translation, artwork, fonts, subtitles, controls and gameplay additions.
- Prepared full DCPs from the Japanese originals and small upgrade DCPs from
  English v0.9.0. Metadata uses numeric release version 0.9.1.
- Reapplied all four packages with the pinned Retro Trans DCP engine, checking
  GDI and CUE/BIN outputs, complete target trees, boot invariants and CD audio.
- Supplied Automatic metadata for both full patches; upgrades are manual DCPs
  inside a separate ZIP so the Automatic inventory remains unambiguous.
- Retained prior SH-4/video-path tests and isolated Redream/Flycast checks.
  Added pow's successful VGA/Redream report without inferring unspecified
  physical-console, adapter or PAL coverage.

The tested VGA candidate's game payloads are unchanged by stable packaging.
No new translation changes, full-gameplay completion or universal hardware
compatibility are claimed. No original game files or complete images are published.

VGA patch credit/source:
https://segasky.itch.io/black-matrix-ad-vga-patch-for-sega-dreamcast
