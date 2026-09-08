"""Native and HD Bizin Gothic from one size, baseline and advance model.

No glyph is fitted to another font's ink bounds. The native bitmap is only
the downsampled fallback and stock texture identity for the same outline.
"""
import json
import sys
from PIL import Image, ImageDraw, ImageFont
import font_style
sys.path.insert(0,str(font_style.ROOT/'tools'))
import fontdump
import latin
import vwf

ROOT = font_style.ROOT
OUTPUT = ROOT/'build/bizin-font'
NATIVE = OUTPUT/'FONT.bin'
SIZE = 16
SCALE = 4
BASELINE = 12.5  # Fits the font's -50..+13 HD outline extent in 64 rows.
LEFT = 1


def outline(path=None):
    return ImageFont.truetype(str(path or font_style.default_font()), SIZE*SCALE)


def glyph(character, font=None):
    font = font or outline()
    box = font.getbbox(character,anchor='ls')
    if (box[0]+LEFT*SCALE<0 or box[1]+BASELINE*SCALE<0
            or box[2]+LEFT*SCALE>128 or box[3]+BASELINE*SCALE>64):
        raise ValueError('Bizin outline exceeds its atlas cell: '+repr(character))
    # Draw on a larger canvas first to detect clipping, including descenders.
    canvas = Image.new('L', (256, 128))
    ImageDraw.Draw(canvas).text((LEFT*SCALE, BASELINE*SCALE), character,
                                font=font, fill=255, anchor='ls')
    box = canvas.getbbox()
    if box and (box[2]>128 or box[3]>64):
        raise ValueError('Bizin glyph exceeds its atlas cell: '+repr(character))
    return canvas.crop((0, 0, 128, 64))


def advances(font=None):
    font = font or outline()
    # Existing SH-4 tables have integer pixel advances. At 16px, Bizin's
    # normal half-width Latin advance is exactly 8; wider symbols use 16.
    return {ch: round(font.getlength(ch)/SCALE)
            for ch in {' ':0, **latin.charmap()}}


def build():
    font = outline()
    data = bytearray((ROOT/'extracted/FONT.BIN').read_bytes())
    seen = set()
    for ch, index in latin.charmap().items():
        if index in seen: continue
        seen.add(index)
        mask = glyph(ch,font).resize((32,16),Image.Resampling.LANCZOS)
        record = latin.blank_record()
        for y in range(16):
            for x in range(32):
                if mask.getpixel((x,y))>=110:latin.set_pixel(record,x,y,1)
        start = fontdump.HEADER + index*fontdump.GLYPH
        data[start:start+fontdump.GLYPH] = record
    OUTPUT.mkdir(parents=True,exist_ok=True)
    NATIVE.write_bytes(data)
    metadata = dict(font_sha256=font_style.FONT_SHA256,size=SIZE,
                    baseline=BASELINE,left=LEFT,advance=advances(font),
                    shape='direct rasterization; no per-glyph scaling')
    (OUTPUT/'metrics.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return bytes(data),metadata


def patch_metrics(exe):
    widths = advances()
    seen=set()
    for ch,index in {' ':0, **latin.charmap()}.items():
        # Some SJIS slots alias straight/curly quotes and dash variants.
        # Use the same first character selected by native/HD atlas builders.
        if index in seen:continue
        seen.add(index)
        exe[vwf.ADV_TAB-vwf.LOAD_BASE+index] = widths[ch]
        # Preserve the font's own sidebearings inside the texture. The game
        # must not subtract the old bitmap's leftmost ink column.
        exe[vwf.BEAR_TAB-vwf.LOAD_BASE+index] = 0


def preview():
    font = outline(); adv = advances(font)
    lines = ('a girl who uttered love...', 'you were marched off to the gloomy prison',
             'the turning point', 'ill il li I1l  minimum  filling',
             'Move  Attack  Magic  Items  Status', 'Guard  Evade  Counter  Yes  No')
    image = Image.new('RGB',(1440,len(lines)*80+16),'#080a0b')
    for row,line in enumerate(lines):
        x=8
        for ch in line:
            mask=glyph(ch,font)
            image.paste('#c6e7e7',(x,8+row*80),mask)
            x+=adv[ch]*SCALE
    OUTPUT.mkdir(parents=True,exist_ok=True)
    image.save(OUTPUT/'text-preview.png')


if __name__=='__main__':
    build();preview()
