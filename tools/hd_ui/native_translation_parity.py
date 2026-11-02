"""Port audited HD-only English content to isolated native discs, not HD art."""
import json
import shutil
import struct
import numpy as np
from PIL import Image,ImageDraw
import native_readable_font as previous
import native_button_font as buttons
import native_sword_fix as base
import native_units_alias as aliases
import vertical_attack_icon as icon
import interface_redraw as pack
import deployment_heading_pack as deployment
import ui_upscale
import pvr_atlas
import noto_font
import inject

ROOT=base.ROOT
SOURCE=previous.OUT
OUT=ROOT/'build/reusable-atlas-noto-ui-r35-native-ui-v4'
HASHES={'SYSTEM.DAT':'4c35206fe964e97c831a0f6419f0a225298b1ab3c881b846ed31468e9cdc9653',
        'SYSTEM.disc2.DAT':'6bd0c80cef9ef4ca6810051a956be75dc4f9e045d84fb1d60afd61eb9eed5c59'}
CHAR_SHA='5ec8e1f70bb80abdf5aba6084249a5048bd7292c707ee6bd2992493733a749dd'
LABELS={54:'Manual',55:'Adjust',56:'Max',64:'OK',65:'Exit',69:'Reset'}


def encode(source,texture,rect,art):
    if source[texture:texture+4]!=b'PVRT' or source[texture+8:texture+10]!=b'\x00\x01':
        raise ValueError('not ARGB1555 twiddled UI')
    width,height=rect[2]-rect[0],rect[3]-rect[1]
    low=art.convert('RGBA').resize((width,height),Image.Resampling.LANCZOS)
    result=[]
    for y in range(height):
        for x in range(width):
            r,g,b,a=low.getpixel((x,y));r,g,b=(c*a//255 for c in (r,g,b))
            word=0x8000|(r*31//255)<<10|(g*31//255)<<5|b*31//255 if a>=64 else 0
            offset=texture+16+2*pvr_atlas.pixel_index(x+rect[0],y+rect[1])
            result.append((offset,struct.pack('<H',word)))
    return result


def system_updates(source):
    rows=pack.descriptors(source,icon.TEXTURE)
    original=pack.descriptors((base.SOURCE/'SYSTEM.DAT').read_bytes(),icon.TEXTURE)
    result=[]
    for index,text in LABELS.items():
        if rows[index]!=original[index]:raise ValueError('caption geometry changed')
        rect=rows[index]
        result+=encode(source,icon.TEXTURE,rect,buttons.caption(text,rect[2]-rect[0]))
    return result


def char_updates(source):
    if pack.sha(source)!=CHAR_SHA:raise ValueError('unknown CHAR archive')
    result=[];matches=[]
    for name,native,meta in ui_upscale.pages(source,'CHAR'):
        if name!=deployment.NAME:continue
        high=deployment.render(native,noto_font.default_font())
        rects=[(x,y,x+16,y+16) for _,x,y,_ in deployment.TILES]
        rects += [r for _,r,_ in deployment.ACTIONS]+[deployment.THINKING]
        for rect in rects:
            art=high.crop(tuple(v*4 for v in rect))
            result+=encode(source,meta['offset'],rect,art)
        matches.append(dict(texture=meta['offset'],rectangles=rects))
    if not matches:raise ValueError('missing deployment/battle banner atlas')
    return result,matches


def patch(source,pending):
    result=bytearray(source)
    for offset,value in pending:result[offset:offset+2]=value
    return bytes(result)


def read_file(track,name):
    with track.open('rb') as f:return inject._extent(f,*inject.find(f,name))


def preview(system,char):
    sheet=Image.new('RGB',(900,260),'#151515');draw=ImageDraw.Draw(sheet)
    atlas=pvr_atlas.decode(system,icon.TEXTURE);rows=pack.descriptors(system,icon.TEXTURE)
    for i,(index,text) in enumerate(LABELS.items()):
        tile=atlas.crop(rows[index]);tile=tile.resize((tile.width*3,tile.height*3),Image.Resampling.NEAREST)
        x,y=i%3*300,i//3*72;sheet.paste(tile,(x,y),tile);draw.text((x,y+48),text,fill='white')
    # Assemble the heading with the same tile overlap offsets as the game.
    atlas=pvr_atlas.decode(char,0x1350);heading=Image.new('RGBA',(deployment.WIDTH,16))
    for _,x,y,offset in deployment.TILES:heading.alpha_composite(atlas.crop((x,y,x+16,y+16)),(offset,0))
    heading=heading.resize((496,64),Image.Resampling.NEAREST);sheet.paste(heading,(0,160),heading)
    for i,rect in enumerate([deployment.THINKING]+[r for _,r,_ in deployment.ACTIONS]):
        tile=atlas.crop(rect);tile=tile.resize((tile.width*3,48),Image.Resampling.NEAREST)
        sheet.paste(tile,(510+i*130,160),tile)
    sheet.save(OUT/'translation-preview.png')


def build():
    if OUT.exists():raise ValueError('output exists; refusing overwrite')
    protected=base.snapshot()
    protected.update({str(p.relative_to(ROOT)):base.digest(p) for p in SOURCE.rglob('*') if p.is_file()})
    for name,sha in HASHES.items():
        if base.digest(SOURCE/name)!=sha:raise ValueError('unknown native source')
    OUT.mkdir();discs=[]
    for number,dirname,system_name in ((1,'disc','SYSTEM.DAT'),(2,'disc2','SYSTEM.disc2.DAT')):
        filename=f'Black-Matrix Advanced (Japan) (Disc {number}) (Track 3).bin'
        old=SOURCE/dirname/filename
        system=read_file(old,'SYSTEM.DAT');char=read_file(old,'CHAR.DAT');exe=read_file(old,'1ST_READ.BIN')
        if system!=(SOURCE/system_name).read_bytes():raise ValueError('SYSTEM disc/archive mismatch')
        pending,matches=char_updates(char)
        targets={'SYSTEM.DAT':patch(system,system_updates(system)),
                 'CHAR.DAT':patch(char,pending),'1ST_READ.BIN':aliases.patch(exe)}
        shutil.copytree(SOURCE/dirname,OUT/dirname);new=OUT/dirname/filename
        raw_words=set();files=[]
        for name,before in (('SYSTEM.DAT',system),('CHAR.DAT',char),('1ST_READ.BIN',exe)):
            after=targets[name]
            changed=np.flatnonzero(np.frombuffer(before,dtype='u1')!=np.frombuffer(after,dtype='u1'))
            with new.open('r+b') as f:
                lba,size=inject.find(f,name)
                for offset in changed:
                    offset=int(offset)
                    raw=(lba-inject.HIGH_DENSITY_LBA+offset//2048)*2352+16+offset%2048
                    f.seek(raw);f.write(after[offset:offset+1]);raw_words.add(raw&~1)
            if read_file(new,name)!=after:raise ValueError('disc readback failed: '+name)
            output=system_name if name=='SYSTEM.DAT' else name.replace('.', '.disc2.',1) if number==2 else name
            (OUT/output).write_bytes(after)
            files.append(dict(file=name,changed_bytes=len(changed),sha256=pack.sha(after)))
        changed=base.verify_track(old,new,sorted(raw_words))
        discs.append(dict(disc=number,files=files,changed_raw_bytes=changed,track_sha256=base.digest(new),
                          unchanged_outside_declared_changes=True,char_references=matches))
    if any(base.digest(ROOT/p)!=sha for p,sha in protected.items()):raise ValueError('protected input changed')
    preview((OUT/'SYSTEM.DAT').read_bytes(),(OUT/'CHAR.DAT').read_bytes())
    report=dict(status='verified-native-only',hd_files_unchanged=True,prior_native_fixes_preserved=True,
                added_sprite_translations=LABELS,banners=['Initial Setup Mode','Thinking','Move','Attack'],
                units_alias='exact 60-cell Units list supported by HD v2; other orders remain outside HD coverage too',
                saves_untouched=True,discs=discs,protected_files=protected,live_game_tested=False)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='protected_files'},indent=2))


if __name__=='__main__':build()
