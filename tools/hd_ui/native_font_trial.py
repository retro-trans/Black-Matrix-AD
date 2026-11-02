"""Offline native-font comparison; never patches discs or installed textures."""
import json
import struct
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageChops
import native_readable_font as native

OUT=native.ROOT/'build/native-font-trial-v1'
FONTS=[('Tahoma - current',native.FACE,12),
       ('m6x11',OUT/'fonts/m6x11.ttf',16),
       ('Silver',OUT/'fonts/Silver.ttf',19)]
LINES=['Abel','Cutlass   Jailwear   Empty','Short, single edge.',
       'Withstands impacts.','But we\'re escaped prisoners.',
       'There must already be pursuers','after us.',
       'Il1  O0  rn m  gypq','0123456789  !?  “Wait…”']


def supported(path,ch):
    """Read Windows Unicode BMP cmap format 4; glyph zero means missing."""
    d=Path(path).read_bytes()
    tables={struct.unpack_from('>4sIII',d,12+i*16)[0]:struct.unpack_from('>4sIII',d,12+i*16)[2]
            for i in range(struct.unpack_from('>H',d,4)[0])}
    o=tables[b'cmap'];number=struct.unpack_from('>H',d,o+2)[0]
    for i in range(number):
        platform,encoding,rel=struct.unpack_from('>HHI',d,o+4+i*8);p=o+rel
        if platform not in (0,3) or struct.unpack_from('>H',d,p)[0]!=4:continue
        count=struct.unpack_from('>H',d,p+6)[0]//2
        ends=p+14;starts=ends+2*count+2;deltas=starts+2*count;ranges=deltas+2*count
        for j in range(count):
            end=struct.unpack_from('>H',d,ends+2*j)[0];start=struct.unpack_from('>H',d,starts+2*j)[0]
            if start<=ord(ch)<=end:
                delta=struct.unpack_from('>h',d,deltas+2*j)[0];r=struct.unpack_from('>H',d,ranges+2*j)[0]
                glyph=(ord(ch)+delta)&65535 if r==0 else struct.unpack_from('>H',d,ranges+2*j+r+2*(ord(ch)-start))[0]
                return glyph!=0
    return False


def cell(ch,face):
    return native.glyph(ch,face)


def line(text,face,advances,width=240,missing=()):
    out=Image.new('L',(width+32,16));left=0
    for ch in text:
        mask=cell(ch,ImageFont.truetype(str(native.FACE),12) if ch in missing else face)
        if left+32>out.width:raise ValueError('Preview text exceeds row')
        out.paste(ImageChops.lighter(out.crop((left,0,left+32,16)),mask),(left,0))
        left+=advances[ch]
    if out.getbbox() and out.getbbox()[2]>width:raise ValueError('Visible text exceeds row')
    return out.crop((0,0,width,16))


def main(tuned=False):
    OUT.mkdir(exist_ok=True)
    advances=native.noto_font.advances()
    title=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    sheet=Image.new('RGB',(2220,825),'#100d0a');draw=ImageDraw.Draw(sheet)
    heading='Native font trial - font-matched spacing (proposed), 3x pixel enlargement' if tuned else 'Native font trial - same game spacing, 3x nearest-neighbor enlargement'
    draw.text((24,12),heading,font=title,fill='#eee5d4')
    reports=[]
    for col,(label,path,size) in enumerate(FONTS):
        face=ImageFont.truetype(str(path),size)
        missing=[ch for ch in native.latin.charmap() if not supported(path,ch)]
        spacing=advances
        if tuned and col>0:
            spacing={ch:max(1,round(face.getlength(ch))) for ch in {' ':0,**native.latin.charmap()}}
            for ch in missing:spacing[ch]=advances[ch]
        # Explicitly marked punctuation fallback; never silently render tofu.
        boxes={}
        for ch in native.latin.charmap():
            boxes[ch]=cell(ch,ImageFont.truetype(str(native.FACE),12) if ch in missing else face).getbbox()
        x=col*740+10
        draw.rectangle((x,56,x+720,782),outline='#a56b21',width=2)
        draw.text((x+12,67),label,font=title,fill='#efb84c')
        draw.text((x+12,101),'Native cell: 32 x 16 | '+str(size)+'px font em',font=small,fill='#bcb5a9')
        if missing:draw.text((x+12,122),'Curly quotes / dashes / ellipsis: Tahoma fallback',font=small,fill='#cbae80')
        single=Image.new('RGB',(240,200),'#100d0a')
        for row,text in enumerate(LINES):
            mask=line(text,face,spacing,missing=missing)
            color='#728889' if row==1 else '#c6e7e7'
            sheet.paste(color,(x+1,143+row*67),mask.resize((720,48),Image.Resampling.NEAREST))
            single.paste(color,(0,row*21),mask)
        single.save(OUT/(label.split(' ')[0].lower()+('-tuned' if tuned else '')+'-native.png'))
        reports.append(dict(font=label,file=str(path),font_em=size,native_cell=[32,16],
            baseline=12,left=1,missing_latin_characters=missing,glyphs_checked=len(boxes),
            missing_glyph_fallback='Tahoma 12' if missing else None,
            all_rendered_glyphs_fit=True,spacing='proposed font-matched advances' if tuned and col>0 else 'unchanged game advances',preview_only=True))
    draw.text((20,799),'m6x11: Daniel Linssen | Silver: Poppy Works / Wolfgang Wozniak | Offline test - game files unchanged',font=small,fill='#aaa297')
    sheet.save(OUT/('comparison-tuned.png' if tuned else 'comparison.png'))
    (OUT/('report-tuned.json' if tuned else 'report.json')).write_text(json.dumps(reports,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps([{k:v for k,v in r.items() if k not in ('file',)} for r in reports],indent=2))

if __name__=='__main__':
    main();main(tuned=True)
