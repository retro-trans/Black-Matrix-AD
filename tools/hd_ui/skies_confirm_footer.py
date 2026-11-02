"""Private v14: native Skies bitmap lettering for shared OK/Back captions.

Original icon positions and caption origins are unchanged. Back grows from
32 to40 pixels within verified unused atlas space, with no outline squeezing.
"""
import argparse
import json
import shutil
import struct
import sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'build/font-port-deps'))
import skies_vmu_header as previous
import skies_baseline_fix as baseline
import native_translation_parity as native
import pvr_atlas

prior=previous.prior
ROOT=previous.ROOT
SOURCE=previous.OUT
SOURCE_SHA='5665a43295a5042484d81ce996d230a9b61d5bfed51b14e063d49eb40173f237'
SYSTEM_SHA='1fdcf4975c709311bfe906c25c3c902c181e6eef6f244a14bb37d871ab3b39ed'
OUT=ROOT/'build/skies-rayblade-font-v14-confirm-footer'
TEXTURE=0x21890
PVX=0x21000
LABELS={63:'Back',64:'OK'}
BEFORE_RECTS={63:(64,160,96,176),64:(0,208,32,224)}
AFTER_RECTS={63:(64,160,104,176),64:BEFORE_RECTS[64]}
GOLD=(255,184,40)
TOP=2
GAP=1


def caption(text,width):
    _,glyphs,_,_=prior.source_bitmap();glyphs=baseline.corrected(glyphs)
    mask=Image.new('L',(width*4,64));pen=0
    for n,ch in enumerate(text):
        if ch not in glyphs:raise ValueError('Unsupported caption character')
        glyph=glyphs[ch];box=glyph.getbbox()
        if box is None:raise ValueError('Blank caption character')
        # Horizontal trim only; keep the source baseline and curved contours.
        ink=glyph.crop((box[0],0,box[2],24));w=ink.width
        if pen+w>width-1:raise ValueError('Caption does not fit without squeezing')
        mask.paste(ink.resize((w*4,48),Image.Resampling.NEAREST),(pen*4,TOP*4))
        pen+=w+(GAP if n+1<len(text) else 0)
    if not text:raise ValueError('Empty caption')
    image=Image.new('RGBA',mask.size,(*GOLD,0));image.putalpha(mask)
    return image,dict(ink_width=pen,source_height=24,native_height=12,top=TOP,gap=GAP)


def patch(system):
    if prior.sha(system)!=SYSTEM_SHA:raise ValueError('Unknown v13 SYSTEM archive')
    rows=native.pack.descriptors(system,TEXTURE)
    if any(rows[i]!=r for i,r in BEFORE_RECTS.items()):raise ValueError('Caption descriptor differs')
    extra=(96,160,104,176)
    if pvr_atlas.decode(system,TEXTURE).crop(extra).getbbox():raise ValueError('Back extension contains artwork')
    for i,r in rows.items():
        if i!=63 and max(r[0],extra[0])<min(r[2],extra[2]) and max(r[1],extra[1])<min(r[3],extra[3]):
            raise ValueError('Back extension overlaps another sprite')
    result=bytearray(system);allowed=set();metrics={}
    for i,text in LABELS.items():
        r=AFTER_RECTS[i];image,metrics[text]=caption(text,r[2]-r[0])
        for pos,value in native.encode(system,TEXTURE,r,image):
            result[pos:pos+2]=value;allowed.update((pos,pos+1))
    # Width and right UV edge ONLY. Height, top-left, page, flags and origin
    # remain exact; the new40px caption still fits a64px controller column.
    descriptor=PVX+48+63*16
    for off,value in ((0,40),(8,104)):
        struct.pack_into('<H',result,descriptor+off,value)
        allowed.update((descriptor+off,descriptor+off+1))
    delta=np.flatnonzero(np.frombuffer(system,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if not delta or any(i not in allowed for i in delta):raise ValueError('Unexpected footer change')
    return bytes(result),delta,allowed,metrics


def preview(before,after):
    out=Image.new('RGBA',(760,210),(18,14,9,255));draw=ImageDraw.Draw(out)
    for version,data in enumerate((before,after)):
        atlas=pvr_atlas.decode(data,TEXTURE);rows=native.pack.descriptors(data,TEXTURE)
        draw.text((12,version*95+5),'Before' if version==0 else 'After: Skies lettering, clear gold, shared size and baseline',fill='white')
        for col,(button,label) in enumerate(((0,64),(1,63))):
            x=col*340+12;y=version*95+25
            for i,dx in ((button,0),(label,16)):
                tile=atlas.crop(rows[i]).resize(((rows[i][2]-rows[i][0])*4,64),Image.Resampling.NEAREST)
                out.alpha_composite(tile,(x+dx*4,y))
    draw.text((12,197),'Offline native-atlas preview, not a live GPU screenshot',fill='white')
    out.save(OUT/'footer-preview.png')


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source v13 differs')
    system,lba=prior.read_file(source,'SYSTEM.DAT');after,delta,_,metrics=patch(system)
    report=dict(status='verified-skies-confirm-footer' if build else 'planned-skies-confirm-footer',writes=build,
        disc=2,source=str(SOURCE.relative_to(ROOT)),source_sha256=SOURCE_SHA,
        labels=LABELS,before_rectangles=BEFORE_RECTS,rectangles=AFTER_RECTS,metrics=metrics,
        font='Verified Rayblade Skies bitmap, same corrected a/p source as dialogue',color=GOLD,
        no_outline_squeezing=True,only_back_width_and_right_uv_changed=True,
        controller_icons_and_caption_origins_unchanged=True,shared_labels_changed_wherever_used=True,
        changed_system_bytes=len(delta),system_sha256=prior.sha(after),
        native_objective_cards_retained=24,saves_unchanged=True,in_game_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous footer build')
    OUT.mkdir();preview(system,after);folder=OUT/'disc2';folder.mkdir()
    changes={(lba-prior.inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i] for i in delta}
    report['track_sha256']=prior.copy_track(source,folder/source.name,SOURCE_SHA,changes)
    if prior.read_file(folder/source.name,'SYSTEM.DAT')[0]!=after:raise ValueError('SYSTEM readback differs')
    for name in ('1ST_READ.BIN','CHAR.DAT','MAP.DAT','SCENARIO.DAT','PARAMETA.DAT'):
        if prior.read_file(source,name)[0]!=prior.read_file(folder/source.name,name)[0]:raise ValueError('Unrelated archive differs: '+name)
    report['companions']=[]
    for path in source.parent.iterdir():
        if path.is_file() and path!=source:
            shutil.copy2(path,folder/path.name);digest=prior.digest(path)
            if prior.digest(folder/path.name)!=digest:raise ValueError('Companion differs')
            report['companions'].append(dict(file=path.name,sha256=digest))
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source changed')
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');a=p.parse_args();run(a.build)
