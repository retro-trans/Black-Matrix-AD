"""Show the first 57 cells of a captured help atlas before/after C++ replay.

Uses captured pixels, not a mock-up. Logical cell addresses follow the game's
Morton layout. Requires attack-help-input/output.rgba made for replay.cpp.
"""
import struct
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    b = path.read_bytes()
    w, h = struct.unpack_from('<II', b)
    return Image.frombytes('RGBA', (w,h), b[8:])


def cell_xy(index):
    pixel_offset = (index*256 - 128*(index & 1))*2
    x = sum(((pixel_offset >> (2*i+1)) & 1) << i for i in range(8))
    y = sum(((pixel_offset >> (2*i)) & 1) << i for i in range(8))
    return x, y


def preview():
    folder = ROOT / 'build/hd-ui'
    low = load(folder / 'attack-help-input.rgba')
    high = load(folder / 'attack-help-output.rgba')
    canvas = Image.new('RGB', (980, 520), '#171717')
    draw = ImageDraw.Draw(canvas)
    for panel, (atlas, scale, label) in enumerate([
            (low, 1, 'Captured original'), (high, 4, 'Same capture through revised C++ renderer')]):
        top = panel*260
        draw.text((20,top+10), label, fill='white')
        for row in range(3):
            pen = 20
            for col in range(19):
                x, y = cell_xy(row*19+col)
                old = low.crop((x,y,x+24,y+16))
                box = old.getchannel('A').getbbox()
                if box is None:
                    pen += 24
                    continue
                glyph = atlas.crop(((x+box[0])*scale, y*scale,
                                    (x+box[2])*scale, (y+16)*scale))
                glyph = glyph.resize((glyph.width*4//scale, 64), Image.Resampling.NEAREST)
                canvas.paste(glyph, (pen,top+40+row*68), glyph)
                pen += (box[2]-box[0]+1)*4
    canvas.save(folder / 'attack-help-comparison.png')


if __name__ == '__main__':
    preview()
