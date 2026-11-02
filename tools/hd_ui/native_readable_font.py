"""Pixel-aligned native Latin font; isolated from all HD assets and metrics."""
import argparse
import json
import shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageChops
import native_button_font as buttons
import native_sword_fix as base
import noto_font
import latin
import fontdump
import inject

ROOT=base.ROOT
SOURCE=buttons.OUT
OUT=ROOT/'build/reusable-atlas-noto-ui-r35-native-ui-v3'
REVIEW=ROOT/'build/native-readable-font-review'
FACE=Path('C:/Windows/Fonts/tahoma.ttf')
SIZE,BASELINE,LEFT=12,12,1
FONT_OFFSET=0x424e0
HASHES={'SYSTEM.DAT':'1d071b744ea74c66441a6e7076557e6d7fa3984e27be2e80389e099540594235',
        'SYSTEM.disc2.DAT':'6feba29ac5b3df6faabc3818a6a84950f20a2cf46f5c547b84b48185cdf2291c'}


def glyph(ch,face=None):
    # Direct monochrome rasterization uses the font's pixel-grid hinting.
    # No supersampling/threshold reduction, bold dilation or per-glyph scaling.
    face=face or ImageFont.truetype(str(FACE),SIZE)
    probe=Image.new('1',(96,64));draw=ImageDraw.Draw(probe)
    draw.text((32+LEFT,32+BASELINE),ch,font=face,fill=1,anchor='ls')
    box=probe.getbbox()
    if box and (box[0]<32 or box[1]<32 or box[2]>64 or box[3]>48):
        raise ValueError('glyph outside native cell: '+repr(ch))
    return probe.crop((32,32,64,48)).convert('L')


def build_font():
    before=noto_font.NATIVE.read_bytes();after=bytearray(before)
    seen=set();face=ImageFont.truetype(str(FACE),SIZE)
    for ch,index in latin.charmap().items():
        if index in seen:continue
        seen.add(index);mask=glyph(ch,face);record=latin.blank_record()
        for y in range(16):
            for x in range(32):
                if mask.getpixel((x,y)):latin.set_pixel(record,x,y,1)
        start=fontdump.HEADER+index*fontdump.GLYPH
        after[start:start+fontdump.GLYPH]=record
    return before,bytes(after)


def sites():
    return [FONT_OFFSET+fontdump.HEADER+idx*fontdump.GLYPH+i
            for idx in sorted(set(latin.charmap().values())) for i in range(0,fontdump.GLYPH,2)]


def patch_system(source):
    old,new=build_font()
    if source[FONT_OFFSET:FONT_OFFSET+len(old)] not in (old,new):
        raise ValueError('unknown embedded font')
    result=bytearray(source);result[FONT_OFFSET:FONT_OFFSET+len(old)]=new
    return bytes(result)


def decode(data,ch):
    out=Image.new('L',(32,16));index=latin.charmap().get(ch)
    if index is not None:
        for y in range(16):
            for x in range(32):out.putpixel((x,y),255 if fontdump.pixel(data,0,index,x,y) else 0)
    return out


def preview():
    REVIEW.mkdir(parents=True,exist_ok=True)
    old,new=build_font();advances=noto_font.advances()
    sheet=Image.new('RGB',(1000,440),'#111414');draw=ImageDraw.Draw(sheet)
    for row,(data,label) in enumerate(((old,'Current native'),(new,'Tahoma 12 - pixel-aligned native'))):
        draw.text((12,row*220+8),label,fill='white')
        for line,text in enumerate(('Stick   Jailwear   Empty','Clothes issued to prisoners.','Il1  O0  mw rn  gypq  0123456789')):
            mask=Image.new('L',(246,16));x=0
            for ch in text:
                cell=decode(data,ch)
                if x+32>mask.width:raise ValueError('preview width')
                mask.paste(ImageChops.lighter(mask.crop((x,0,x+32,16)),cell),(x,0))
                x+=advances[ch]
            mask=mask.resize((984,64),Image.Resampling.NEAREST)
            sheet.paste('#b5dada',(8,row*220+24+line*64),mask)
    sheet.save(REVIEW/'comparison.png')
    print('Preview: '+str(REVIEW/'comparison.png'))


def build():
    if OUT.exists():raise ValueError('output exists; refusing overwrite')
    protected=base.snapshot()
    protected.update({str(p.relative_to(ROOT)):base.digest(p) for p in SOURCE.rglob('*') if p.is_file()})
    systems={}
    for name,sha in HASHES.items():
        if base.digest(SOURCE/name)!=sha:raise ValueError('unknown native source')
        systems[name]=patch_system((SOURCE/name).read_bytes())
    OUT.mkdir();discs=[]
    for number,dirname,name in ((1,'disc','SYSTEM.DAT'),(2,'disc2','SYSTEM.disc2.DAT')):
        shutil.copytree(SOURCE/dirname,OUT/dirname)
        filename=f'Black-Matrix Advanced (Japan) (Disc {number}) (Track 3).bin'
        old,new=SOURCE/dirname/filename,OUT/dirname/filename
        with old.open('rb') as f:
            lba,size=inject.find(f,'SYSTEM.DAT')
            if inject._extent(f,lba,size)!=(SOURCE/name).read_bytes():raise ValueError('disc/archive mismatch')
        raw=[(lba-inject.HIGH_DENSITY_LBA+o//2048)*2352+16+o%2048 for o in sites()]
        with new.open('r+b') as f:
            for offset,archive_offset in zip(raw,sites()):
                f.seek(offset);f.write(systems[name][archive_offset:archive_offset+2])
        with new.open('rb') as f:
            if inject._extent(f,lba,size)!=systems[name]:raise ValueError('disc readback failed')
        changed=base.verify_track(old,new,raw)
        (OUT/name).write_bytes(systems[name])
        discs.append(dict(disc=number,changed_raw_bytes=changed,only_latin_font_records_changed=True,
                          track_sha256=base.digest(new),system_sha256=base.digest(OUT/name)))
    if any(base.digest(ROOT/p)!=sha for p,sha in protected.items()):raise ValueError('protected inputs changed')
    _,font=build_font();(OUT/'FONT.bin').write_bytes(font)
    report=dict(status='verified-native-only',font='Tahoma',font_source=str(FACE),font_sha256=base.digest(FACE),
                size=SIZE,baseline=BASELINE,left=LEFT,rendering='direct monochrome pixel-grid hinted',
                metrics='existing Noto advances and bearings unchanged; no executable change',
                japanese_glyphs_unchanged=True,hd_files_unchanged=True,prior_native_fixes_preserved=True,
                discs=discs,protected_files=protected,live_game_tested=False)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='protected_files'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--preview',action='store_true')
    if p.parse_args().preview:preview()
    else:build()
