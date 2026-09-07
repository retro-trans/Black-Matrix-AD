"""Localize the free-action command labels stored in EVENT.DAT.

The lower-right action HUD is not made from script strings.  Its labels are
pre-rendered in an ARGB1555, square-twiddled PVR texture at file offset
0x53310.  Replace the complete Japanese command set and keep the archive the
same size so EVENT.DAT can be injected back into its original ISO extent.
The cooking control screen is localized through cooking.py in the same pass.

    python tools/hud.py install
"""

import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

import gfx
import cooking
import woodcutting
import chaptercards


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, "extracted", "EVENT.DAT")
OUTPUT = os.path.join(ROOT, "build", "EVENT.vwf.dat")

PVRT = 0x53310
WIDTH = 256
HEIGHT = 256
FONT = r"C:\Windows\Fonts\arialbd.ttf"
FONT_SIZE = 12

# Corrected texture coordinates.  The game's Morton order is transposed
# relative to gfx.decode_pvr(), hence _pixel_offset() swaps x and y.
LABELS = (
    ((0, 112, 41, 128), "Menu"),
    ((42, 112, 82, 128), "Drop"),
    ((0, 128, 41, 144), "Item"),
    ((42, 128, 82, 144), "Swap"),
    ((0, 144, 41, 160), "Cancel"),
    ((42, 144, 82, 160), "Select"),
    ((0, 160, 41, 176), "Run"),
    ((42, 160, 82, 176), "Eat"),
    ((0, 176, 41, 192), "OK"),
    ((42, 176, 82, 192), "Give"),
    ((0, 192, 41, 208), "Check"),
    ((42, 192, 82, 208), "Use"),
    ((0, 208, 41, 224), "Talk"),
    ((42, 208, 82, 224), "Close"),
    ((0, 224, 41, 240), "Take"),
    ((42, 224, 82, 240), "Put"),
)

# The original atlas uses these neutral ARGB1555 shades for its outlined
# white labels.  Reusing them preserves the existing HUD's colour modulation.
INK = 0xEF7B
LIGHT = 0xCE73
MID = 0xBDEF
SHADOW = 0x8C63
TRANSPARENT = 0x0000


def _pixel_offset(x, y):
    return PVRT + 16 + 2 * gfx.untwiddle_index(y, x)


def _put(data, x, y, value):
    struct.pack_into("<H", data, _pixel_offset(x, y), value)


def _render(text, width, height):
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for size in range(FONT_SIZE, 9, -1):
        font = ImageFont.truetype(FONT, size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=1)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= width and th <= height:
            break
    else:
        raise ValueError("HUD label %r does not fit its %dx%d cell"
                         % (text, width, height))
    x = (width - tw) // 2 - bbox[0]
    y = (height - th) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=255,
              stroke_width=1, stroke_fill=48)
    return mask


def install(source=SOURCE, output=OUTPUT):
    data = bytearray(open(source, "rb").read())
    if data[PVRT:PVRT + 4] != b"PVRT":
        raise ValueError("EVENT.DAT has no PVRT at 0x%X" % PVRT)
    if data[PVRT + 8:PVRT + 10] != b"\x00\x01":
        raise ValueError("HUD texture is no longer ARGB1555/twiddled")
    if struct.unpack_from("<HH", data, PVRT + 12) != (WIDTH, HEIGHT):
        raise ValueError("HUD texture dimensions changed")

    for (x0, y0, x1, y1), text in LABELS:
        for y in range(y0, y1):
            for x in range(x0, x1):
                _put(data, x, y, TRANSPARENT)
        mask = _render(text, x1 - x0, y1 - y0)
        for y in range(y1 - y0):
            for x in range(x1 - x0):
                level = mask.getpixel((x, y))
                if level >= 224:
                    colour = INK
                elif level >= 160:
                    colour = LIGHT
                elif level >= 96:
                    colour = MID
                elif level:
                    colour = SHADOW
                else:
                    continue
                _put(data, x0 + x, y0 + y, colour)

    cooking_tiles = cooking.patch(data, os.path.dirname(output))
    woodcutting_tiles = woodcutting.patch(data, os.path.dirname(output))
    chapter_tiles = chaptercards.patch(data, os.path.dirname(output))
    os.makedirs(os.path.dirname(output), exist_ok=True)
    open(output, "wb").write(data)
    print("wrote %s (%d bytes)" % (output, len(data)))
    print("  localized HUD commands: %s"
          % ", ".join(text for cell, text in LABELS))
    print("  localized cooking instructions (%d tiles, existing atlas capacity 512)" % cooking_tiles)
    print("  localized woodcutting instructions (%d tiles, existing atlas capacity 512)" % woodcutting_tiles)
    print('  localized Chapter 1 ending (%d tiles)' % chapter_tiles)


def main(argv):
    if len(argv) != 2 or argv[1] != "install":
        print(__doc__)
        return 1
    install()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
