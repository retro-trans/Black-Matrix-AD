"""Translate the cooking control screen (EVENT.DAT group 34), in place.

Uses the existing two RGB565 atlases and SCL tilemap. Only bitmap text is
replaced: the controller, its button colors/connector lines, and speech bubble
are preserved. UI wording/glossary controls live in script/ui/cooking_help.tsv.
hud.py invokes patch() so every full build includes this screen.
"""
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import pvr_atlas
import terms

ROOT = Path(__file__).resolve().parents[1]
SCL = 0x7FF000
UI = ROOT / 'script' / 'ui' / 'cooking_help.tsv'
FONT = r'C:\Windows\Fonts\verdana.ttf'
TITLE_FONT = r'C:\Windows\Fonts\verdanab.ttf'


def strings(path=UI):
    glossary = terms.load_glossary()
    with Path(path).open(encoding='utf-8-sig') as f:
        rows = csv.DictReader((line for line in f if not line.startswith('#')), delimiter='\t')
        result = {}
        for row in rows:
            source_terms = terms.source_term_counts(row['japanese'], glossary)
            controls = terms.token_counts(row['english'])
            if source_terms != controls:
                raise ValueError('help-screen term controls do not match source: '+row['id'])
            result[row['id']] = terms.expand_text(row['english'], glossary)
    return result


def text_at(screen, xy, text, size=13, color='white', max_width=590, bold=False):
    font = ImageFont.truetype(TITLE_FONT if bold else FONT, size*4)
    box = font.getbbox(text)
    layer = Image.new('RGBA', (box[2]-box[0]+4, box[3]-box[1]+4))
    ImageDraw.Draw(layer).text((-box[0],-box[1]), text, font=font, fill=color)
    # Screen native height is 240, displayed as 480: compensate horizontally
    # for legible English rather than rendering unusually thin letters.
    layer = layer.resize((round(layer.width*1.8/4), round(layer.height/4)), Image.Resampling.LANCZOS)
    if layer.width > max_width or xy[0]+layer.width>screen.width or xy[1]+layer.height>screen.height:
        raise ValueError('cooking-help text does not fit: '+text)
    screen.paste(layer, xy, layer)
    return layer.width


def patch(data, preview_dir=None):
    original_size = len(data)
    screen = pvr_atlas.decode_scl(data, SCL)
    if screen.size != (640,240):
        raise ValueError('cooking-help screen dimensions changed')
    original = screen.copy()
    text = strings()
    draw = ImageDraw.Draw(screen)
    draw.rectangle((95,10,610,50), fill='black')
    text_at(screen,(110,16),text['title'],25,color='#ff4545',bold=True,max_width=240)
    text_at(screen,(320,26),text['subtitle'],16,max_width=280,bold=True)
    draw.rectangle((324,62,620,140), fill='black')
    for key,y,color in [('green',65,'#008c00'),('blue',84,'#0074ef'),
                        ('red',103,'#a63820'),('yellow',122,'#e0c900')]:
        color_word,rest = text[key].split(' ',1)
        w = text_at(screen,(328,y),color_word,13,color=color,bold=True,max_width=110)
        text_at(screen,(328+w+7,y),rest,13,max_width=620-(328+w+7))
    bubble = original.crop((74,166,141,196))
    draw.rectangle((20,149,630,220),fill='black')
    text_at(screen,(30,153),text['step1'],13,max_width=595)
    text_at(screen,(30,179),'2.',13,max_width=40)
    screen.paste(bubble,(74,169))
    text_at(screen,(150,179),text['step2a'],13,max_width=475)
    text_at(screen,(75,204),text['step2b'],13,max_width=550)
    tiles = pvr_atlas.encode_scl(data,SCL,screen)
    assert len(data)==original_size
    if preview_dir is not None:
        dest=Path(preview_dir)
        dest.mkdir(parents=True,exist_ok=True)
        # Preview comes back from the ENCODED game data, not the drawing canvas.
        pvr_atlas.decode_scl(data,SCL).resize((640,480),Image.Resampling.NEAREST).save(dest/'cooking-help-english.png')
    return tiles
