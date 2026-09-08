"""Translate the Chapter 1 ending graphic in its existing SCL allocation."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import cooking
import pvr_atlas

ROOT = Path(__file__).resolve().parents[1]
SCL = 0x2DF6800
UI = ROOT / 'script/ui/chapter1_end.tsv'
FONT = r'C:\Windows\Fonts\georgiab.ttf'


def draw_text(screen, text, xy, size, max_width):
    font = ImageFont.truetype(FONT, size*4)
    box = font.getbbox(text)
    layer = Image.new('RGBA',(box[2]-box[0]+4,box[3]-box[1]+4))
    ImageDraw.Draw(layer).text((-box[0],-box[1]),text,font=font,fill='#dedede')
    # Native image is 640x240; displayed at 640x480.
    layer = layer.resize((round(layer.width/2),round(layer.height/4)),Image.Resampling.LANCZOS)
    if layer.width>max_width or xy[0]+layer.width>640 or xy[1]+layer.height>240:
        raise ValueError('chapter-card text does not fit: '+text)
    screen.paste(layer,xy,layer)


def patch(data, preview_dir=None):
    original_size = len(data)
    screen = pvr_atlas.decode_scl(data,SCL)
    if screen.size != (640,240):
        raise ValueError('chapter-ending dimensions changed')
    screen.paste('black',(0,0,640,240))
    text = cooking.strings(UI)
    draw_text(screen,text['chapter'],(50,20),22,320)
    draw_text(screen,text['title'],(65,111),17,530)
    draw_text(screen,text['end'],(520,201),21,110)
    tiles = pvr_atlas.encode_scl(data,SCL,screen)
    assert len(data)==original_size
    if preview_dir is not None:
        pvr_atlas.decode_scl(data,SCL).resize((640,480),Image.Resampling.NEAREST).save(
            Path(preview_dir)/'chapter1-end-english.png')
    return tiles
