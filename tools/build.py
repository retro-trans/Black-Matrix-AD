"""Build the whole patch, in the one order that is correct.

The steps are not independent.  tools/vwf.py bakes an advance and a bearing
for every glyph into the executable, and those have to describe the font that
will actually be on the disc.  Building the executable before redrawing the
font gives a pen that still spaces the narrow Latin glyphs as if they were
full-width, which looks like wide gaps between letters and a tiny word space.
That is easy to do by hand and hard to spot, so the order lives here:

    1. latin.py    redraw the Latin glyphs      -> FONT.vwf.bin, SYSTEM.vwf.dat
    2. vwf.py      assemble the VWF patch       -> 1ST_READ.vwf.bin
                   (reads FONT.vwf.bin for its metrics)
    3. uistr.py    optional UI string edits     -> 1ST_READ.vwf.bin
    4. glossary.py enforce canonical terminology
    5. scriptpack.py repack translated script  -> SCENARIO.vwf.dat
    6. hud.py      localize the free-action HUD     -> EVENT.vwf.dat
    7. inject.py   write all files into the disc copy

    python tools/build.py                    # build and inject
    python tools/build.py --no-inject        # build only
    python tools/build.py --font georgia.ttf --size 12

The disc copy in build/disc is patched in place; the images in the project
root are never touched.
"""

import glob
import io
import os
import struct
import subprocess
import sys

import patchline

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
TRACK = os.path.join(BUILD, "disc",
                     "Black-Matrix Advanced (Japan) (Disc 1) (Track 3).bin")

# Help lines on the config screen, patched in place so there is English on a
# screen that can be reached in half a minute.  Each must fit its record.
UI_STRINGS = [
    # A VWF hook special-case places the last three cells on row two.
    (0x83D3E, "YesNo "),
    (0x882D6, "Type slower"),
    (0x882EE, "Normal speed"),
    (0x88308, "Type faster"),
    # Partner-selection confirmation prompts. These records are fixed-size.
    (0x891B6, "Him?"),
    (0x891C4, "Her?"),
    (0x89334, "Is this OK?"),
    # Three fixed five-cell rows; keep each label within its own slot.
    (0x88B62, "Save Load Setup"),
    (0x89854, "Save Load Setup"),
]

# Fixed-size executable messages with live fields in their trailing words.
# Preserve those fields verbatim while translating only the static prefix.
UI_PREFIX_STRINGS = [
    # AP shortage warning; the final two words render the current/required AP.
    (0x88C82, 2, "AP: LOW! "),
]

# The name-entry save structure reserves seven u16 character slots per name.
# Keep full spellings wherever they fit and use unambiguous seven-letter screen
# forms for the two longer names. Dialogue still uses the glossary spellings.
SYSTEM_NAME_SLOTS = 7
SYSTEM_NAMES = [
    (0x1CD9B0, "Abel"),
    (0x1CD9C0, "Domina"),
    (0x1CD9D0, "Prica"),
    (0x1CD9E0, "Courreg"),
    (0x1CD9F0, "Michett"),
    (0x1CDA00, "Prague"),
    (0x1CDA10, "Zero"),
]

SCRIPT_FILES = [os.path.relpath(path, ROOT)
                for path in sorted(glob.glob(os.path.join(
                    ROOT, "script", "en", "*.en.tsv")))]
GLOSSARY = os.path.join("script", "glossary.tsv")


def run(*args):
    cmd = [sys.executable] + list(args)
    r = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    out = r.stdout.decode("utf-8", "replace").rstrip()
    if out:
        print("\n".join("    " + l for l in out.splitlines()))
    if r.returncode:
        raise SystemExit("failed: %s" % " ".join(args))


def patch_system_names():
    path = os.path.join(BUILD, "SYSTEM.vwf.dat")
    data = bytearray(open(path, "rb").read())
    for offset, name in SYSTEM_NAMES:
        if len(name) > SYSTEM_NAME_SLOTS:
            raise ValueError("default name %r exceeds the seven-character field" % name)
        struct.pack_into("<H", data, offset, len(name))
        words = [patchline.to_sjis(ch) for ch in name]
        words += [patchline.SPACE] * (SYSTEM_NAME_SLOTS - len(words))
        data[offset + 2:offset + 2 + SYSTEM_NAME_SLOTS * 2] = b"".join(
            struct.pack("<H", word) for word in words)
    open(path, "wb").write(bytes(data))
    print("    patched Latin default names: %s" %
          ", ".join(name for offset, name in SYSTEM_NAMES))


def main(argv):
    # Child tools report Japanese source text when a translation fails.  Keep
    # diagnostics printable even when the host console defaults to a legacy
    # Windows code page such as GBK.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    font = argv[argv.index("--font") + 1] if "--font" in argv else None
    size = argv[argv.index("--size") + 1] if "--size" in argv else None
    wide = argv[argv.index("--wide") + 1] if "--wide" in argv else None
    max_width = argv[argv.index('--max-width')+1] if '--max-width' in argv else None

    print("1. redrawing the Latin glyphs")
    args = ["tools/latin.py", "install"]
    if font:
        args += ["--font", font]
    if size:
        args += ["--size", size]
    if wide:
        args += ["--wide", wide]
    if max_width:
        args += ['--max-width', max_width]
    run(*args)
    patch_system_names()

    print("2. assembling the VWF patch")
    run("tools/vwf.py", "build")

    print("3. UI strings")
    for off, text in UI_STRINGS:
        run("tools/uistr.py", "put", hex(off), text)
    for off, preserve, text in UI_PREFIX_STRINGS:
        run("tools/uistr.py", "put-prefix", hex(off), str(preserve), text)
    run('tools/mainmenu.py')

    print("4. checking canonical terminology")
    run("tools/glossary.py", "check", GLOSSARY, *SCRIPT_FILES)

    print("5. repacking translated scripts")
    run("tools/scriptpack.py", "--expand", *SCRIPT_FILES)

    print("6. localizing the free-action HUD")
    run("tools/hud.py", "install")

    if "--no-inject" in argv:
        print("\nnot injecting (--no-inject)")
        return 0

    if not os.path.exists(TRACK):
        raise SystemExit("no disc copy at %s - copy the images into build/disc"
                         % TRACK)

    print("7. injecting into the disc copy")
    run("tools/inject.py", "put", TRACK, "1ST_READ.BIN",
        os.path.join(BUILD, "1ST_READ.vwf.bin"))
    run("tools/inject.py", "put", TRACK, "SYSTEM.DAT",
        os.path.join(BUILD, "SYSTEM.vwf.dat"))
    run("tools/inject.py", "put", TRACK, "EVENT.DAT",
        os.path.join(BUILD, "EVENT.vwf.dat"))

    scenario = os.path.join(BUILD, "SCENARIO.vwf.dat")
    if os.path.exists(scenario):
        run("tools/inject.py", "relocate", TRACK, "SCENARIO.DAT", scenario)

    print("\ndone. to look at it:")
    print("    powershell -ExecutionPolicy Bypass -File tools\\runcfg.ps1"
          " -Out build\\shot.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
