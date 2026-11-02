"""Isolated m6x11 native trial: Latin bitmap records and matching advances only."""
import json
import argparse
import shutil
from PIL import ImageFont
import native_font_trial as trial

native=trial.native
ROOT=native.ROOT
SOURCE=ROOT/'build/reusable-atlas-noto-ui-r35-native-shop-menu-labels-v1'
OUT=ROOT/'build/reusable-atlas-noto-ui-r35-native-m6x11-v1'
FACE=trial.OUT/'fonts/m6x11.ttf'
FALLBACK='‘’“”—–…'
FALLBACK_INDICES={native.latin.charmap()[ch] for ch in FALLBACK}
EM=16
FONT_ID='m6x11'
FONT_NAME='m6x11 by Daniel Linssen'


def font_and_widths():
    _,before=native.build_font()
    after=bytearray(before)
    face=ImageFont.truetype(str(FACE),EM)
    widths=native.noto_font.advances()
    # En and em dash share one game glyph; the first mapping owns its width.
    seen={}
    for ch,index in {' ':0,**native.latin.charmap()}.items():
        if index in seen:
            widths[ch]=widths[seen[index]]
            continue
        seen[index]=ch
        if index in FALLBACK_INDICES:continue
        if not trial.supported(FACE,ch):raise ValueError('Unexpected missing glyph: '+ch)
        widths[ch]=max(1,round(face.getlength(ch)))
        if ch==' ':continue
        mask=native.glyph(ch,face)
        record=native.latin.blank_record()
        for y in range(16):
            for x in range(32):
                if mask.getpixel((x,y)):native.latin.set_pixel(record,x,y,1)
        start=native.fontdump.HEADER+index*native.fontdump.GLYPH
        after[start:start+native.fontdump.GLYPH]=record
    return before,bytes(after),widths


def patch_system(data):
    old,new,_=font_and_widths()
    off=native.FONT_OFFSET
    if data[off:off+len(old)]!=old:raise ValueError('Source must contain current Tahoma font')
    return data[:off]+new+data[off+len(old):]


def patch_exe(data):
    _,_,widths=font_and_widths()
    vwf=native.noto_font.vwf
    old=native.noto_font.game_advances()
    result=bytearray(data)
    seen=set()
    for ch,index in {' ':0,**native.latin.charmap()}.items():
        if index in seen:continue
        seen.add(index)
        off=vwf.ADV_TAB-vwf.LOAD_BASE+index
        bearing=vwf.BEAR_TAB-vwf.LOAD_BASE+index
        if data[off]!=old[ch] or data[bearing]!=0:
            raise ValueError('Unexpected source metrics: '+repr(ch))
        result[off]=widths[ch]*native.noto_font.DISPLAY_X
    return bytes(result)


def raw_offset(lba,offset):
    return (lba-native.inject.HIGH_DENSITY_LBA+offset//2048)*2352+16+offset%2048


def verify_track(old,new,changes):
    if old.stat().st_size!=new.stat().st_size:raise ValueError('Track size changed')
    with old.open('rb') as a,new.open('rb') as b:
        pos=0
        while source:=a.read(4*1024*1024):
            expected=bytearray(source)
            for off,value in changes.items():
                if pos<=off<pos+len(source):expected[off-pos]=value
            if b.read(len(source))!=expected:raise ValueError('Unexpected raw disc change')
            pos+=len(source)


def build(refresh=False):
    if OUT.exists() and not refresh:raise ValueError('Output exists; refusing overwrite')
    if refresh and not OUT.is_dir():raise ValueError('No trial to refresh')
    protected={str(p.relative_to(ROOT)):native.base.digest(p) for p in SOURCE.rglob('*') if p.is_file()}
    protected.update({str(p.relative_to(ROOT)):native.base.digest(p) for p in
                      (ROOT/'build/stock-atlas-run/data/textures/T20101M').glob('*.png')})
    OUT.mkdir(exist_ok=refresh)
    (OUT/'manifest.json').write_text(json.dumps(dict(status='building-native-'+FONT_ID)),encoding='utf-8')
    for path in SOURCE.iterdir():
        if path.is_file() and path.suffix!='.json':shutil.copy2(path,OUT/path.name)
    discs=[]
    for number,folder in ((1,'disc'),(2,'disc2')):
        if not refresh:shutil.copytree(SOURCE/folder,OUT/folder)
        name=f'Black-Matrix Advanced (Japan) (Disc {number}) (Track 3).bin'
        old,new=SOURCE/folder/name,OUT/folder/name
        changes={};writes={};files=[]
        for filename,patch in (('SYSTEM.DAT',patch_system),('1ST_READ.BIN',patch_exe)):
            with old.open('rb') as f:
                lba,size=native.inject.find(f,filename)
                before=native.inject._extent(f,lba,size)
            loose=filename if number==1 else filename.replace('.', '.disc2.',1)
            if before!=(SOURCE/loose).read_bytes():raise ValueError('Loose file/disc mismatch')
            after=patch(before)
            with new.open('rb') as f:current=native.inject._extent(f,lba,size)
            for i,(a,b) in enumerate(zip(current,after)):
                if a!=b:writes[raw_offset(lba,i)]=b
            for i,(a,b) in enumerate(zip(before,after)):
                if a!=b:changes[raw_offset(lba,i)]=b
            (OUT/loose).write_bytes(after)
            files.append((filename,lba,size,after))
        with new.open('r+b') as f:
            for off,value in sorted(writes.items()):f.seek(off);f.write(bytes([value]))
        verify_track(old,new,changes)
        with new.open('rb') as f:
            for filename,lba,size,expected in files:
                if native.inject._extent(f,lba,size)!=expected:raise ValueError('Readback mismatch')
        discs.append(dict(disc=number,changed_bytes=len(changes),track_sha256=native.base.digest(new)))
        print('Verified disc '+str(number),flush=True)
    for path,digest in protected.items():
        if native.base.digest(ROOT/path)!=digest:raise ValueError('Protected file changed: '+path)
    _,font,widths=font_and_widths()
    (OUT/'FONT.bin').write_bytes(font)
    shutil.copy2(trial.OUT/'fonts/ATTRIBUTION.md',OUT/'FONT-ATTRIBUTION.md')
    report=dict(status='verified-native-'+FONT_ID,font=FONT_NAME,font_sha256=native.base.digest(FACE),
        em=EM,baseline=12,left=1,advance=[dict(character=c,width=w) for c,w in widths.items()],display_x_compensation=2,
        fallback=FALLBACK,fallback_font='Tahoma 12' if FALLBACK else None,discs=discs,
        source_build=str(SOURCE),source_and_hd_unchanged=True,live_game_tested=False,
        changes='Only mapped Latin bitmap records and Latin advance bytes; no engine code changes')
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true')
    build(parser.parse_args().refresh)
