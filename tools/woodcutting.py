"""Localize EVENT.DAT group 33's woodcutting controls using its existing tiles."""
from pathlib import Path
from PIL import Image, ImageDraw

import cooking
import pvr_atlas

SCL = 0x7BE000
UI = cooking.ROOT / 'script/ui/woodcutting_help.tsv'


def patch(data, preview_dir=None):
    size = len(data)
    screen = pvr_atlas.decode_scl(data, SCL)
    if screen.size != (640,240):
        raise ValueError('woodcutting-help dimensions changed')
    text = cooking.strings(UI)
    draw = ImageDraw.Draw(screen)
    draw.rectangle((30,10,625,54), fill='black')
    cooking.text_at(screen,(45,20),text['title'],22,color='#ffd24a',bold=True,max_width=300)
    cooking.text_at(screen,(365,30),text['subtitle'],16,bold=True,max_width=260)
    # Retain the controller and colored lines, whose rightmost X is 359.
    draw.rectangle((365,75,625,151), fill='black')
    for key,y,color in [('unused',78,'#a63820'),('unused',97,'#a63820'),
                        ('swing',115,'white'),('unused',134,'#a63820')]:
        cooking.text_at(screen,(367,y),text[key],13,color=color,max_width=260)
    draw.rectangle((30,173,625,215), fill='black')
    cooking.text_at(screen,(45,179),text['step1'],13,max_width=580)
    cooking.text_at(screen,(45,197),text['step2'],13,max_width=580)
    tiles = pvr_atlas.encode_scl(data,SCL,screen)
    assert len(data)==size
    if preview_dir is not None:
        dest=Path(preview_dir)
        dest.mkdir(parents=True,exist_ok=True)
        pvr_atlas.decode_scl(data,SCL).resize((640,480),Image.Resampling.NEAREST).save(dest/'woodcutting-help-english.png')
    return tiles
