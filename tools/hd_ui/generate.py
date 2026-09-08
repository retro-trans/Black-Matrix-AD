"""Generate an emulator-only glyph dictionary from this build's Latin font.

HD coverage comes from freshly rasterized TTF outlines, never enlarged pixels.
The original bitmap's ink bounds anchor the HD outline, retaining game metrics.
Original game glyphs and generated resources remain in the ignored build tree.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import fontdump
import latin
import patchline

SCALE = 4
COMPACT_INK_SCALE = 7 / 8


def native_glyph(data, character):
    index = latin.sjis_to_index(patchline.to_sjis(character))
    low = Image.new('L', (32, 16))
    for y in range(16):
        for x in range(32):
            low.putpixel((x, y), 255 if fontdump.pixel(data, 0, index, x, y) else 0)
    box = low.getbbox()
    if box is None:
        return None
    rows = [sum((1 << x) for x in range(32) if low.getpixel((x, y)))
            for y in range(16)]
    return rows, low


def make_glyph(data, character, font, ink_scale=1.0):
    if not 0 < ink_scale <= 1:
        raise ValueError('ink scale must be greater than zero and at most one')
    native = native_glyph(data, character)
    if native is None:return None
    rows, low = native
    box = low.getbbox()
    # Draw large vector outlines, then fit only to the original ink bounds.
    fbox = font.getbbox(character)
    vector = Image.new('L', (fbox[2]-fbox[0], fbox[3]-fbox[1]))
    ImageDraw.Draw(vector).text((-fbox[0], -fbox[1]), character, font=font, fill=255)
    vector = vector.crop(vector.getbbox())
    high = Image.new('L', (128, 64))
    original_width = (box[2]-box[0])*SCALE
    width = max(1, round(original_width*ink_scale))
    height = max(1, round((box[3]-box[1])*SCALE*ink_scale))
    # Center horizontally within the original ink allocation. Transform all
    # vertical bounds about the SAME line midpoint, preserving the relative
    # cap/x-height, baseline and descenders instead of centering each letter.
    x = box[0]*SCALE + (original_width-width)//2
    y = round(8*SCALE + (box[1]*SCALE-8*SCALE)*ink_scale)
    high.paste(vector.resize((width, height), Image.Resampling.LANCZOS), (x, y))
    return rows, low, high


def generate(source, ttf, output):
    data = source.read_bytes()
    if len(data) != fontdump.FONT_LEN or data[:4] != b'MFD ':
        raise ValueError('expected this build\'s complete MFD font')
    font = ImageFont.truetype(str(ttf), 128)
    entries, seen, previews = [], set(), []
    for character in ''.join(chr(i) for i in range(33, 127)):
        try:
            patchline.to_sjis(character)
        except ValueError:
            continue
        result = make_glyph(data, character, font)
        if result is None:
            continue
        rows, low, high = result
        if tuple(rows) in seen:
            continue
        seen.add(tuple(rows))
        entries.append(struct.pack('<16I', *rows) + high.tobytes())
        previews.append((character, low, high))
    output.mkdir(parents=True, exist_ok=True)
    payload = b''.join(entries)
    header = struct.pack('<8s4I32sI', b'BMHDFNT\0', 1, SCALE, len(entries), 8256,
                         hashlib.sha256(data).digest(), zlib.crc32(payload))
    # Atomic replacement avoids leaving a partial pack after interruption.
    pack_path = output / 'black-matrix-hd-font.bin'
    temporary = pack_path.with_suffix('.bin.tmp')
    temporary.write_bytes(header + payload)
    os.replace(temporary, pack_path)
    metadata = dict(format_version=1, scale=SCALE, glyphs=len(entries),
                    pack_sha256=hashlib.sha256(header+payload).hexdigest(),
                    source_sha256=hashlib.sha256(data).hexdigest(),
                    outline_font=str(ttf.resolve()), source_font=str(source.resolve()))
    (output / 'font-manifest.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    preview = Image.new('RGB', (640, 64*6), '#101010')
    for i, character in enumerate('AaBbgQW012?!'):
        _, low, high = next(p for p in previews if p[0] == character)
        x, y = (i % 2)*320, (i//2)*64
        preview.paste('white', (x, y, x+128, y+64), low.resize((128,64), Image.Resampling.NEAREST))
        preview.paste('white', (x+144, y, x+272, y+64), high)
    preview.save(output / 'glyph-comparison.png')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font', type=Path, default=ROOT / 'build/FONT.vwf.bin')
    p.add_argument('--ttf', type=Path, default=Path('C:/Windows/Fonts/verdana.ttf'))
    p.add_argument('--output', type=Path, default=ROOT / 'build/hd-ui')
    a = p.parse_args()
    generate(a.font, a.ttf, a.output)
