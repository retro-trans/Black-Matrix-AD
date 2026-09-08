# Emulator-only HD text prototype (2026-09-08)

**Current experiment:** the user chose stock Flycast plus a game-side font
atlas. See [stock-font-atlas.md](stock-font-atlas.md). The custom-emulator
workflow below is retained as earlier work and is not used by that prototype.

Branch: `codex/emulator-hd-ui`, based on local translation commit `34a0669`.
The divergent remote commit `db857bb` has NOT been merged. Do not assume its
Bizin font, expanded menus, or revised wrapping are present in this disc.

## Current workflow: external font data (revision 4)

HD font masks and coverage are no longer compiled into Flycast. The generator
writes `build/hd-ui/black-matrix-hd-font.bin`, and `run.ps1` passes its absolute
path via `BLACK_MATRIX_HD_DATA`. Change fonts without compiling:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Repo\Black-Matrix-AD\tools\hd_ui\update_font.ps1" -Font "C:\Windows\Fonts\verdana.ttf"
```

Then save/close the test emulator and use the normal launcher shown below.
Font updates need a restart, NOT a compiler. `run.ps1 -FontPack <path>` selects
an alternative pack. Keep the existing Verdana style by omitting `-Font`.
The update script uses the bundled Python if present, or accepts `-Python`.

This still requires the custom Flycast build with the external loader (a final
one-time rebuild, now completed locally). Stock Flycast cannot read this custom
format. Changes to the matching/rendering algorithm still require recompiling;
changes to font outlines/masks do not. No hot reload is attempted during play.

The binary loader bounds allocation (at most 256 glyphs), validates magic,
version, scale, stride, exact file length, CRC32, glyph bounds and duplicates.
Missing/corrupt packs log a warning and fall back to the original texture path.
The generator replaces the pack atomically. The 60-byte little-endian header
is `8s, version, scale, count, stride, source-SHA256[32], payload-CRC32`; each
8256-byte record is 16 uint32 mask rows followed by 128x64 alpha bytes.

Replay of the user's attack-help capture through the external loader matches
the embedded-data revision 3 output byte for byte (SHA256
`d6c36e13c5cdeca9b61fe69f014c3bf7e65c2811fbed1b0c88f1c6d3f91ec5c1`).
Malformed-pack tests and the full Flycast compile pass. The user's active
session is not restarted or navigated automatically.
Verification also loaded an independently generated Tahoma pack into the same
replay executable: rendered output changed while the Flycast executable hash
stayed identical. The default pack remains Verdana. Python suite: 29 pass,
one optional fixture skipped; C++ glyph/loader/size tests pass.

## How it works

An opt-in Flycast texture-upload hook recognizes exact 32x16-cell glyph masks
from the generated `build/FONT.vwf.bin`. It substitutes newly rasterized TTF
coverage at 4x resolution while retaining game positions, UVs, colors, and
timing. It is NOT screenshot OCR, a font bitmap enlargement, or a game renderer
rewrite. Unknown cells stay nearest-neighbor copies of the original pixels.

The hook is enabled only for game ID `T20101M`, environment variable
`BLACK_MATRIX_HD_FONT=1`, uncompressed/non-mipmapped Pal4 textures, and square
32/64/128/256 textures. Other games and formats use the existing path. CPU palette
conversion is selected consistently in both the cache key and upload paths.
The GPU receives larger textures; emulated RAM/VRAM and disc files are untouched.

Revision 2 fixes a demonstrated matcher defect: opaque-background glyphs were
rejected because the first prototype identified ink solely by nonzero alpha.
Matching now uses the unused rightmost column as the background reference and
requires an exact mask with uniform ink. Coverage preserves opaque backgrounds
for additive blending and interpolates premultiplied color for transparency.
It did NOT resolve the user's reported help screen; its actual cause was the
atlas-size restriction described below.

Revision 3: texture capture `ca542835.png` from the user's attack-help screen
is a 256x256 atlas (transparent black background, opaque cyan ink). Both the
Flycast eligibility check and core matcher excluded that size. They now accept
256x256. Replaying the captured original through the exact C++ matcher replaces
90 glyphs and writes a 1024x1024 atlas. Synthetic tests fill each supported size,
including all 128 glyph cells in a 256 atlas. The revised Flycast compiles;
on-screen verification after restarting into revision 3 is pending.

## Current evidence and limitations

- Flycast compiled and booted the translated disc using Direct3D 11.
- The user's running prototype log records successful 32/64/128 atlas glyph
  replacements. A read-only RAM capture confirms its MFD font matches the
  generated reference exactly.
- The C++ test covers all 88 distinct supported masks, semi-transparent colored
  ink, opaque-black backgrounds, unknown-cell preservation, and no-op guards.
- Text built into non-font artwork, Japanese glyphs, and unsupported texture
  layouts are not enhanced. Antialiased/multicolor source glyphs fall back.
- Current glyph data is tied to this build's Verdana-derived MFD font. After
  merging font changes, regenerate the dictionary from the rebuilt disc font.
- The game still controls its original layout and clipping. This prototype
  does not widen menu slots or increase line capacity.
- Automated tests and replacement logs are not a substitute for checking
  visible dialogue/help, fades, scrolling, and menu transitions in-game.

## Local files and isolation

- Source copy: `build/flycast-hd-src`.
- Build directory: `build/flycast-hd-compile`.
- Runnable isolated profile: `build/hd-ui-run`.
- Generated glyph data/manifest/comparison: `build/hd-ui`.
- Original installation: `D:/Program/FlyCast`, never overwritten.
- Test BIOS and VMUs were copied to the isolated profile. Do not copy test saves
  back over the user's normal saves without explicit approval.

The source copy came from `D:/Repo/Black Matrix AD/flycast-src`, upstream commit
`44e4c7b50df86bf431f0e7b4ea7ed7a3fd7aef45`. It also includes that tree's existing
uncommitted diagnostic changes to option.cpp/.h, sh4_sched.cpp and gdrom_hle.cpp/.h.
Their source tree was left unchanged; Debug.TraceState is off in the test profile.
For redistribution, pin/review those changes and include GPL source/license.
Generated glyph fingerprints contain game data and must remain git-ignored.
There is no dependency on the obsolete `glyphs.generated.h` left in older
ignored build folders.

## Reproduce

Use Python with Pillow. Prepare a separate Flycast source copy under `build/`
with its dependencies; never apply these hooks to the user's regular emulator.

```powershell
python tools/hd_ui/generate.py
python tools/hd_ui/patch_flycast.py build/flycast-hd-src
```

In a Visual Studio x64 developer shell with CMake/Ninja available:

```powershell
cmake -S build/flycast-hd-src -B build/flycast-hd-compile -G Ninja -DCMAKE_BUILD_TYPE=Release -DUSE_DISCORD=OFF -DUSE_DX9=OFF -DUSE_DX11=ON -DUSE_OPENGL=ON -DUSE_VULKAN=OFF -DENABLE_GDB_SERVER=ON -DENABLE_LOG=ON
cmake --build build/flycast-hd-compile --parallel 6
cl /nologo /std:c++17 /EHsc /Itools/hd_ui tests/hd_ui_atlas_test.cpp /Febuild/hd-ui/atlas-test.exe /Fobuild/hd-ui/atlas-test.obj
build/hd-ui/atlas-test.exe
python -m unittest discover -s tests -q
```

To upgrade an earlier isolated prototype or refresh its matcher/loader sources:
`python tools/hd_ui/patch_flycast.py build/flycast-hd-src --upgrade`, then rebuild.
The upgrade checks the known hook and is idempotent. Font changes only require
`update_font.ps1`; do not copy generated data into the emulator source tree.

Save progress and close the existing test emulator before running:

```powershell
./tools/hd_ui/run.ps1 -Visible
```

If PowerShell blocks scripts, use a process-only bypass:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Repo\Black-Matrix-AD\tools\hd_ui\run.ps1" -Visible
```

`-CaptureTextures` temporarily enables Flycast's texture dumping for that run.
Captures are local under `build/hd-ui-run/data/texdump/T20101M`. They contain
game data and must remain ignored. The user handles navigation; do not send
keys or clicks to their emulator. `replay.cpp` can verify a captured atlas with
the production matcher: input/output are little-endian width/height followed
by RGBA bytes. Flip Flycast's PNG vertically before preparing a replay input.

The launcher refreshes only the isolated executable from the compiled build,
and refuses to replace a running instance. `-OriginalText` disables HD text for
comparison. Normal saves, disc assets, and original hardware remain unaffected.
The prepared local profile uses 1920 internal vertical resolution and a 1280x960
window. A new checkout needs its own BIOS, VMU copies, profile, and original disc.

`tools/hd_ui/capture_ram.ps1` can read the isolated emulator's 16 MB game RAM;
it checks the loaded executable anchor before writing an ignored diagnostic
capture. It never writes process memory.
