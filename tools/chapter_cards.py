"""Localize the requested Chapter 1 ending and Chapter 2 opening SCL cards.

Native tilemaps and RGB565 atlas allocations remain the same size. The new
opening title uses dark caption panels over the old lettering, keeping the
surrounding original sigil artwork. No engine or animation code is changed.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import cooking
import pvr_atlas

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'script/ui/chapter_cards.tsv'
END_SCL = 0x2DF6800
OPEN_SCL = 0xF60800
FONT = r'C:\Windows\Fonts\georgiab.ttf'
PANELS = ((160, 78, 480, 112), (104, 128, 536, 164))


def caption(screen, text, x, y, height, width, centered=False):
    """Render at display proportions, then reduce to the native half height."""
    font = ImageFont.truetype(FONT, height * 4)
    box = font.getbbox(text)
    layer = Image.new('RGBA', (box[2]-box[0]+4, box[3]-box[1]+4))
    ImageDraw.Draw(layer).text((-box[0], -box[1]), text, font=font, fill='#dedede')
    target_w = round(layer.width / 4)
    target_h = round(layer.height / 8)
    scale = min(1, width / target_w)
    layer = layer.resize((round(target_w*scale), max(1, round(target_h*scale))),
                         Image.Resampling.LANCZOS)
    if centered:
        x -= layer.width // 2
    if x < 0 or x + layer.width > screen.width or y + layer.height > screen.height:
        raise ValueError('chapter caption exceeds screen bounds')
    screen.paste(layer, (x, y), layer)


def patch(data, preview_dir=None):
    text = cooking.strings(UI)
    end = pvr_atlas.decode_scl(data, END_SCL)
    opening = pvr_atlas.decode_scl(data, OPEN_SCL)
    if end.size != (640, 240) or opening.size != (640, 240):
        raise ValueError('chapter card dimensions changed')
    end.paste('black', (0, 0, 640, 240))
    caption(end, text['chapter1'], 44, 20, 48, 340)
    caption(end, text['garden'], 320, 108, 52, 560, centered=True)
    caption(end, text['end'], 520, 199, 48, 100)
    draw = ImageDraw.Draw(opening)
    for panel in PANELS:
        draw.rectangle(panel, fill='#100c0a', outline='#967962', width=1)
    caption(opening, text['chapter2'], 320, 84, 44, 290, centered=True)
    caption(opening, text['prison'], 320, 136, 48, 402, centered=True)
    sizes = []
    for offset, screen, name in [(END_SCL, end, 'chapter1-end-english.png'),
                                  (OPEN_SCL, opening, 'chapter2-open-english.png')]:
        sizes.append(pvr_atlas.encode_scl(data, offset, screen))
        if preview_dir is not None:
            dest = Path(preview_dir)
            dest.mkdir(parents=True, exist_ok=True)
            pvr_atlas.decode_scl(data, offset).resize((640, 480),
                Image.Resampling.NEAREST).save(dest / name)
    return sizes
