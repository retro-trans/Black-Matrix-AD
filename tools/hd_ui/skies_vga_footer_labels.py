"""Private VGA v7: consistent Skies artwork for seven shared footer captions.

One common height, baseline and90% horizontal metric. Longer labels receive
verified unused atlas space; no per-word size fitting. OK/Back stay unchanged.
"""
import argparse
import json
import shutil
import struct
import numpy as np
from PIL import Image,ImageDraw
import skies_vga_system_alignment as previous
import skies_confirm_footer as captions
import skies_attack_letters as sectors
import pvr_atlas
import mode1_sector

ROOT=previous.ROOT
prior=previous.prior
SOURCE=previous.OUT
SOURCE_SHA='876c7db09fc7be4b004908ab221948f8b9ab7e9c65c0835c6c676f4e86f8a65f'
SYSTEM_SHA='f32ade6569d0dffd07c03328c07d92e3b4387f5cf472c985cca794736dbd0212'
OUT=ROOT/'build/skies-vga-compat-v7-footer-labels'
STATUS='verified-skies-vga-footer-labels'
TEXTURE=0x21890
PVX=0x21000
LABELS={51:'Status',59:'Equip',57:'Magic',61:'Unequip',62:'Discard',97:'Buy',98:'Sell'}
BEFORE_RECTS={51:(0,112,32,128),59:(112,112,144,128),57:(0,192,32,208),
              61:(64,128,104,144),62:(64,144,104,160),97:(152,96,184,112),98:(184,96,216,112)}
RECTS={51:(144,0,200,16),59:(176,160,216,176),57:(152,176,194,192),
       61:(200,0,256,16),62:(120,160,176,176),97:BEFORE_RECTS[97],98:BEFORE_RECTS[98]}
X_SCALE=0.9
LEFT=1
Y_SHIFT=-1.5


def overlap(a,b):return max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3])


def label(text,width):
    source,metrics=captions.caption(text,120)
    if LEFT+metrics['ink_width']*X_SCALE>width-1:
        raise ValueError('Caption does not fit common metrics')
    # Fixed affine transform for EVERY word, not a word-specific fit/resize.
    # Match the existing aligned Back's baseline and horizontal ink gap.
    mask=source.getchannel('A').transform((width*4,64),Image.Transform.AFFINE,
        (1/X_SCALE,0,-LEFT*4/X_SCALE,0,1,-Y_SHIFT*4),Image.Resampling.BICUBIC)
    art=Image.new('RGBA',mask.size,(*captions.GOLD,0));art.putalpha(mask)
    return art,dict(source_ink_width=metrics['ink_width'],horizontal_scale=X_SCALE,
        native_height=12,left=LEFT,top=0.5,gap_source=1)


def patch_system(system):
    if prior.sha(system)!=SYSTEM_SHA:raise ValueError('Unknown VGA v6 SYSTEM')
    rows=captions.native.pack.descriptors(system,TEXTURE)
    atlas=pvr_atlas.decode(system,TEXTURE)
    result=bytearray(system);allowed=set();metrics={}
    for index,text in LABELS.items():
        rect=RECTS[index];old=BEFORE_RECTS[index]
        if rows[index]!=old:raise ValueError('Footer descriptor changed')
        for other,r in rows.items():
            if other!=index and overlap(rect,r):raise ValueError('New caption overlaps an existing sprite')
        for other,r in RECTS.items():
            if other!=index and overlap(rect,r):raise ValueError('New captions overlap each other')
        # Every newly claimed texel must be transparent, even if no existing
        # sprite references it. Preserve all old unused caption pixels.
        for y in range(rect[1],rect[3]):
            for x in range(rect[0],rect[2]):
                if not(old[0]<=x<old[2] and old[1]<=y<old[3]) and atlas.getpixel((x,y))[3]:
                    raise ValueError('New caption space contains unreferenced artwork')
        art,metrics[text]=label(text,rect[2]-rect[0])
        for off,value in captions.native.encode(system,TEXTURE,rect,art):
            result[off:off+2]=value;allowed.update((off,off+1))
        # Width and UV rectangle ONLY. Height/page/flags remain byte-exact.
        descriptor=PVX+48+index*16
        for off,value in ((0,rect[2]-rect[0]),(4,rect[0]),(6,rect[1]),(8,rect[2]),(10,rect[3])):
            struct.pack_into('<H',result,descriptor+off,value);allowed.update((descriptor+off,descriptor+off+1))
    delta=np.flatnonzero(np.frombuffer(system,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if not delta or not set(delta)<=allowed:raise ValueError('Out-of-caption changes')
    return bytes(result),delta,allowed,metrics


def preview(before,after):
    out=Image.new('RGBA',(1190,615),'#100e0a');draw=ImageDraw.Draw(out)
    draw.text((10,5),'Offline footer comparison: captured26px icon/caption offsets, 140px columns, display aspect1:2',fill='white')
    for version,system in enumerate((before,after)):
        y0=30+version*290
        draw.text((10,y0),'Before' if version==0 else 'After: common Skies height/baseline/90% width metrics; Back unchanged',fill='white')
        atlas=pvr_atlas.decode(system,TEXTURE);rows=captions.native.pack.descriptors(system,TEXTURE)
        for row,items in enumerate((((0,51),(2,59),(3,57),(1,63)),
                                    ((0,59),(2,61),(3,62),(1,63)),((0,97),(2,98),(1,63)))):
            y=y0+20+row*84
            for col,(icon,word) in enumerate(items):
                for index,dx in ((icon,0),(word,26)):
                    r=rows[index];tile=atlas.crop(r).resize(((r[2]-r[0])*4,64),Image.Resampling.NEAREST)
                    out.alpha_composite(tile,(10+col*280+dx*2,y))
    out.save(OUT/'footer-labels-preview.png')


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v6 source differs')
    system,lba=prior.read_file(source,'SYSTEM.DAT');after,delta,_,metrics=patch_system(system)
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    report=dict(status=STATUS if build else 'planned-skies-vga-footer-labels',disc=2,
        source_sha256=SOURCE_SHA,source=str(SOURCE.relative_to(ROOT)),
        system_sha256=prior.sha(after),changed_system_bytes=len(delta),labels=LABELS,
        rectangles=RECTS,metrics=metrics,color=captions.GOLD,
        common_metrics_no_per_word_fit=True,caption_origins_and_controller_icons_unchanged=True,
        ok_back_pixels_and_alignment_unchanged=True,descriptor_height_page_flags_unchanged=True,
        executable_sha256=manifest['executable_sha256'],executable_and_vga_boot_unchanged=True,
        earlier_fixes_retained=True,same_existing_save_folder=True,
        in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous footer build')
    changes,touched=sectors.sector_changes(source,lba,after,delta)
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir();preview(system,after);target=folder/source.name
    report['track_sha256']=prior.copy_track(source,target,SOURCE_SHA,changes)
    report.update(changed_raw_bytes=len(changes),parity_repaired_sectors=touched)
    with source.open('rb') as stream:
        directory=list(prior.inject.iso_files(stream));boot=prior.inject._extent(stream,45000,32768)
    with target.open('rb') as stream:
        if list(prior.inject.iso_files(stream))!=directory or prior.inject._extent(stream,45000,32768)!=boot:
            raise ValueError('Boot or directory changed')
        for sector in touched:
            stream.seek(sector*2352);raw=stream.read(2352)
            if mode1_sector.regenerate(raw)!=raw:raise ValueError('Output parity invalid')
    report['files']=[]
    for name,_,_ in directory:
        old,_=prior.read_file(source,name);new,_=prior.read_file(target,name)
        if new!=(after if name=='SYSTEM.DAT' else old):raise ValueError('Unrelated payload changed: '+name)
        report['files'].append(dict(name=name,sha256=prior.sha(new)))
    report['companions']=[]
    for path in source.parent.iterdir():
        if path.is_file() and path!=source:
            shutil.copy2(path,folder/path.name);digest=prior.digest(path)
            if prior.digest(folder/path.name)!=digest:raise ValueError('Companion changed')
            report['companions'].append(dict(file=path.name,sha256=digest))
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true')
    run(parser.parse_args().build)
