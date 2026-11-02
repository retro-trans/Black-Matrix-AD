"""Private VGA v5: Skies bitmap lettering for shared Port and Slot labels."""
import argparse
import json
import shutil
import struct
import numpy as np
from PIL import Image,ImageDraw
import skies_vga_vmu_alignment as previous
import skies_attack_letters as badges
import skies_confirm_footer as captions
import config_load_ui
import pvr_atlas
import mode1_sector

ROOT=previous.ROOT
prior=previous.prior
SOURCE=previous.OUT
SOURCE_SHA='6ff9fb6f96aad75b9ad9e56b46d5f9050f19b4a1a840b3c29dac19bb99202e63'
SYSTEM_SHA='7e2e29f4e6c6587804617f5e663be2dcbcb3138f6dab40ec18daa80ea250bdb1'
OUT=ROOT/'build/skies-vga-compat-v5-port-slot'
STATUS='verified-skies-vga-port-slot'
PVX=0x5bbe20
TEXTURE=0x5bc010
LABELS={12:'Port',13:'Slot'}
RECTS={12:(0,192,80,208),13:(0,208,104,224)}


def label(text,width):
    # Same exact corrected Skies masks/size as the clear OK/Back captions,
    # with the previous Port/Slot left inset and a shared header baseline.
    source,metrics=captions.caption(text,width-1)
    art=Image.new('RGBA',(width*4,64));art.paste(source,(4,0))
    return art,metrics


def patch_system(system):
    if prior.sha(system)!=SYSTEM_SHA:raise ValueError('Unknown VGA v4 SYSTEM')
    original=(ROOT/'extracted/SYSTEM.DAT').read_bytes()
    # Disc2's shared resource moved from Disc1's608620 to5BBE20. Verify the
    # original shared header, not the unrelated pixels at the Disc1 address.
    if system[PVX:PVX+48]!=original[0x608620:0x608620+48]:
        raise ValueError('Unknown shared save/load atlas')
    result=bytearray(system);allowed=set();metrics={}
    for index,text in LABELS.items():
        rect=config_load_ui.sprite_rect(system,PVX,index)
        if rect!=RECTS[index]:raise ValueError('Port/Slot descriptor differs')
        if struct.unpack_from('<8H',system,PVX+48+index*16)!=(rect[2]-rect[0],16,*rect,0,0):
            raise ValueError('Port/Slot geometry differs')
        art,metrics[text]=label(text,rect[2]-rect[0])
        for off,value in captions.native.encode(system,TEXTURE,rect,art):
            result[off:off+2]=value;allowed.update((off,off+1))
    delta=np.flatnonzero(np.frombuffer(system,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if not delta or not set(delta)<=allowed:raise ValueError('Out-of-label changes')
    return bytes(result),delta,allowed,metrics


def preview(before,after):
    out=Image.new('RGBA',(680,210),'#100e0a');draw=ImageDraw.Draw(out)
    draw.text((10,5),'Offline Port/Slot preview: native atlas at game display aspect1:2',fill='white')
    for row,data in enumerate((before,after)):
        y=30+row*86;draw.text((10,y),'Before' if row==0 else 'After: same Skies lettering as updated labels',fill='white')
        atlas=pvr_atlas.decode(data,TEXTURE)
        for col,index in enumerate(LABELS):
            tile=atlas.crop(RECTS[index])
            # 2x screen enlargement: native X2, native Y4. No word-specific fit.
            out.alpha_composite(tile.resize((tile.width*2,64),Image.Resampling.NEAREST),(10+col*330,y+18))
    out.save(OUT/'port-slot-preview.png')


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v4 source differs')
    system,lba=prior.read_file(source,'SYSTEM.DAT');after,delta,_,metrics=patch_system(system)
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    report=dict(status=STATUS if build else 'planned-skies-vga-port-slot',disc=2,
        source_sha256=SOURCE_SHA,source=str(SOURCE.relative_to(ROOT)),
        system_sha256=prior.sha(after),changed_system_bytes=len(delta),labels=LABELS,
        rectangles=RECTS,metrics=metrics,color=captions.GOLD,left_inset=1,
        no_outline_squeezing=True,descriptors_and_label_positions_unchanged=True,
        executable_sha256=manifest['executable_sha256'],executable_and_vga_boot_unchanged=True,
        header_size_unchanged=True,font_geometry_and_renderer_unchanged=True,
        footer_alignment_and_attack_letters_retained=True,same_existing_save_folder=True,
        in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous Port/Slot build')
    changes,sectors=badges.sector_changes(source,lba,after,delta)
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir();preview(system,after)
    target=folder/source.name
    report['track_sha256']=prior.copy_track(source,target,SOURCE_SHA,changes)
    report.update(changed_raw_bytes=len(changes),parity_repaired_sectors=sectors)
    with source.open('rb') as stream:
        directory=list(prior.inject.iso_files(stream));boot=prior.inject._extent(stream,45000,32768)
    with target.open('rb') as stream:
        if list(prior.inject.iso_files(stream))!=directory or prior.inject._extent(stream,45000,32768)!=boot:
            raise ValueError('Boot or directory changed')
        for sector in sectors:
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
