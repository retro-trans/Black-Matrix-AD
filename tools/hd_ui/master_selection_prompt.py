"""Translate the Disc1 master-selection bitmap in a NEW private disc pair.

Only one central native prompt panel changes. Copy changed screen tiles to
unused positions in the SAME three PVR pages; preserve every other descriptor,
all existing tile pixels, all headers, runtime code and archive allocations.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import struct

import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import name_entry_english as names
import pvr_atlas
import shared_disc2

ROOT=names.ROOT
SOURCE=names.OUT
OUT=Path('M:/Black-Matrix-AD-private-tests/english-selection-v2')
REVIEW=Path('M:/Black-Matrix-AD-private-tests/master-prompt-inspection')
LEAF_SHA='1c66c8274ba85e6de2aef82d73672f80af02ab507f84ce1204e46260f286158a'
OFFSET=0x1ce000
LENGTH=397312
RECT=(32,99,608,139)
FONT=Path('C:/Windows/Fonts/arialbi.ttf')
FONT_SHA='267a411525980d648f10a7222a6ff1ebe4d4feeefbf9b3100cae2b5cfab5594a'


def text():
    with (ROOT/'script/ui/master_selection.tsv').open(encoding='utf-8') as f:
        rows=list(csv.DictReader((s for s in f if not s.startswith('#')),delimiter='\t'))
    if len(rows)!=1 or rows[0]['japanese']!='ご主人様を選択して下さい':raise ValueError('Unknown prompt catalog')
    return rows[0]['english']


def artwork(source):
    if names.sha(source[OFFSET:OFFSET+LENGTH])!=LEAF_SHA:raise ValueError('Unknown source background')
    if names.sha(FONT.read_bytes())!=FONT_SHA:raise ValueError('Unknown prompt font')
    original=pvr_atlas.decode_scl(source,OFFSET)
    if original.size!=(640,240):raise ValueError('Unknown prompt dimensions')
    # Match display proportions: bitmap rows are doubled by the native game.
    # This is a code-rendered native UI panel, not a reconstructed background.
    x,y,xx,yy=RECT;scale=4
    panel=Image.new('RGBA',((xx-x)*scale,(yy-y)*scale))
    draw=ImageDraw.Draw(panel)
    for row in range(panel.height):
        t=abs(row/(panel.height-1)*2-1)
        draw.line((0,row,panel.width,row),fill=(int(39-16*t),int(18-5*t),int(17-4*t),255))
    draw.rectangle((0,0,panel.width-1,panel.height-1),outline='#806353',width=scale)
    face=ImageFont.truetype(str(FONT),48*scale)
    caption=text();stroke=scale
    box=face.getbbox(caption,stroke_width=stroke)
    w,h=box[2]-box[0]+12*scale,box[3]-box[1]+12*scale
    ink=Image.new('RGBA',(w,h));d=ImageDraw.Draw(ink)
    d.text((6*scale-box[0],6*scale-box[1]),caption,font=face,
           fill='#990d05',stroke_width=stroke,stroke_fill='#fff1d4')
    glow=ink.getchannel('A').filter(ImageFilter.GaussianBlur(1.5*scale))
    layer=Image.new('RGBA',ink.size,'#dac8b5');layer.putalpha(glow);layer.alpha_composite(ink)
    layer=layer.resize((layer.width,(layer.height+1)//2),Image.Resampling.LANCZOS)
    if layer.width>panel.width-16*scale or layer.height>panel.height-4*scale:
        raise ValueError('Full prompt does not fit the existing screen band')
    panel.alpha_composite(layer,((panel.width-layer.width)//2,(panel.height-layer.height)//2))
    low=original.copy()
    low.paste(panel.convert('RGB').resize((xx-x,yy-y),Image.Resampling.LANCZOS),(x,y))
    return original,low


def patch(source):
    original,screen=artwork(source)
    cols,rows,descriptors,pages=pvr_atlas.scl_layout(source,OFFSET)
    if (cols,rows,len(pages))!=(40,15,3):raise ValueError('Unknown native allocation')
    occupied=set(descriptors)
    all_slots=[ty|tx<<8|page<<16 for page in range(len(pages)) for tx in range(0,256,16) for ty in range(0,256,16)]
    free=iter([d for d in all_slots if d not in occupied])
    result=bytearray(source);spans=[];edits=[]
    for i in range(600):
        x=i%40*16;y=i//40*16
        before=original.crop((x,y,x+16,y+16));after=screen.crop((x,y,x+16,y+16))
        if before.tobytes()==after.tobytes():continue
        try:slot=next(free)
        except StopIteration:raise ValueError('Insufficient unused atlas tiles') from None
        pos=OFFSET+32+i*4;struct.pack_into('<I',result,pos,slot);spans.append((pos,pos+4))
        tx,ty,page=slot>>8&255,slot&255,slot>>16
        for k,(r,g,b) in enumerate(after.getdata()):
            word=((r*31+127)//255)<<11|((g*63+127)//255)<<5|((b*31+127)//255)
            off=pages[page]+16+pvr_atlas.pixel_index(tx+k%16,ty+k//16)*2
            struct.pack_into('<H',result,off,word);spans.append((off,off+2))
        edits.append(dict(screen_tile=i,old_descriptor=descriptors[i],new_descriptor=slot))
    decoded=pvr_atlas.decode_scl(result,OFFSET)
    # RGB565 display round-trip must be exact, even outside the new panel.
    a=np.array(screen,dtype=np.uint32)
    words=((a[:,:,0]*31+127)//255)<<11|((a[:,:,1]*63+127)//255)<<5|((a[:,:,2]*31+127)//255)
    expected=np.stack(((words>>11&31)*255//31,(words>>5&63)*255//63,(words&31)*255//31),axis=-1).astype('u1')
    if decoded.tobytes()!=expected.tobytes():raise ValueError('Native screen readback differs')
    allowed=np.zeros(len(source),dtype=bool)
    for a,z in spans:allowed[a:z]=True
    changes=np.flatnonzero(np.frombuffer(source,'u1')!=np.frombuffer(result,'u1'))
    if not len(changes) or np.any(~allowed[changes]):raise ValueError('Out-of-scope archive writes')
    return bytes(result),decoded,dict(text=text(),rect=RECT,member=[4],source_member_sha256=LEAF_SHA,
        font_sha256=FONT_SHA,changed_screen_tiles=len(edits),tile_edits=edits,
        changed_system_bytes=len(changes),all_other_screen_pixels_and_headers_preserved=True,
        executable_and_other_game_files_unchanged=True)


def source_payload(disc,name):
    p=SOURCE/f'disc{disc}'/f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
    return names.budget.legacy.footer.prior.read_file(p,name)


def preview():
    source,_=source_payload(1,'SYSTEM.DAT');after,image,report=patch(source)
    REVIEW.mkdir(exist_ok=True)
    image.resize((960,720),Image.Resampling.NEAREST).save(REVIEW/'choose-your-master-preview.png')
    print(json.dumps({k:v for k,v in report.items() if k!='tile_edits'},indent=2))
    print('DRY RUN ONLY: disc images and running game unchanged.',flush=True)


def build(out=OUT,patcher=patch,status='private-english-selection-runtime-pending'):
    # Other reviewed artwork variants reuse the same strict per-disc mastering
    # and readback checks without changing this panel variant or its defaults.
    OUT=out
    if OUT.exists():raise ValueError('Preserve previous selection build')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient free space')
    previous=json.loads((SOURCE/'manifest.json').read_text());expected={r['path']:r['sha256'] for r in previous['files']}
    before,_=source_payload(1,'SYSTEM.DAT');after,image,art=patcher(before)
    # This new-game screen is Disc1-specific. Never substitute Disc1's SYSTEM
    # into Disc2, whose group4 is a different native resource.
    other,_=source_payload(2,'SYSTEM.DAT')
    if any(names.sha(other[o:o+n])==LEAF_SHA for _,o,n in shared_disc2.leaves(other)):
        raise ValueError('Unexpected second copy of master prompt on Disc2')
    OUT.mkdir();files=[];discs=[];prior=names.budget.legacy.footer.prior
    for disc in (1,2):
        folder=SOURCE/f'disc{disc}';dest=OUT/f'disc{disc}';dest.mkdir()
        track=folder/f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
        target=dest/track.name;key=track.relative_to(SOURCE).as_posix()
        touched=[]
        if disc==1:
            _,lba=source_payload(1,'SYSTEM.DAT')
            delta=np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(after,'u1')).tolist()
            changes,touched=names.budget.legacy.sectors.sector_changes(track,lba,after,delta)
            h=prior.copy_track(track,target,expected[key],changes)
            with track.open('rb') as f:
                directory=list(prior.inject.iso_files(f));boot=prior.inject._extent(f,45000,32768)
            with target.open('rb') as f:
                if list(prior.inject.iso_files(f))!=directory or prior.inject._extent(f,45000,32768)!=boot:
                    raise ValueError('Boot or directory changed')
                for sector in touched:
                    f.seek(sector*2352);raw=f.read(2352)
                    if names.mode1_sector.regenerate(raw)!=raw:raise ValueError('Invalid sector parity')
            for name,_,_ in directory:
                old,_=prior.read_file(track,name);actual,_=prior.read_file(target,name)
                if actual!=(after if name=='SYSTEM.DAT' else old):raise ValueError('Unexpected payload: '+name)
        else:
            with track.open('rb') as src,target.open('xb') as out:shutil.copyfileobj(src,out,4*1024*1024)
            h=names.pair.digest(target)
            if h!=expected[key]:raise ValueError('Disc2 copy changed')
        files.append(dict(path=target.relative_to(OUT).as_posix(),sha256=h,bytes=target.stat().st_size))
        for p in folder.iterdir():
            if p.is_file() and p!=track:
                dst=dest/p.name
                with p.open('rb') as src,dst.open('xb') as out:shutil.copyfileobj(src,out)
                h=names.pair.digest(dst)
                if h!=expected[p.relative_to(SOURCE).as_posix()]:raise ValueError('Companion changed')
                files.append(dict(path=dst.relative_to(OUT).as_posix(),sha256=h,bytes=dst.stat().st_size))
        exe,_=source_payload(disc,'1ST_READ.BIN')
        discs.append(dict(disc=disc,executable_sha256=names.sha(exe),parity_sectors=touched,
                          master_prompt_changed=disc==1,source_track_sha256=expected[key]))
        print('Disc',disc,'verified.',flush=True)
    for row in files:
        if names.pair.digest(OUT/row['path'])!=row['sha256']:raise ValueError('Final file hash differs')
    for row in previous['files']:
        if names.pair.digest(SOURCE/row['path'])!=row['sha256']:raise ValueError('Previous build changed')
    (OUT/'1ST_READ.BIN').write_bytes((SOURCE/'1ST_READ.BIN').read_bytes())
    image.resize((960,720),Image.Resampling.NEAREST).save(OUT/'choose-your-master-preview.png')
    report=dict(status=status,files=files,discs=discs,artwork=art,
        private_local_only=True,previous_builds_unchanged=True,gameplay_verified=False,
        latin_default_and_name_controls_retained=True,vga_buffer_fix_retained=True,
        physical_hardware_verified=False,disc2_byte_identical_to_name_entry_v1=True)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'Black Matrix AD.m3u').write_text(''.join(f'disc{d}/Black-Matrix Advanced (Japan) (Disc {d}).cue\n' for d in (1,2)))
    print('New private selection pair:',OUT,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');args=p.parse_args()
    if args.build:build()
    else:preview()
