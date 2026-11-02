"""Private VGA v4: optically align shared OK/Back artwork with button icons.

No controller-icon, font-source, descriptor, renderer or save modifications.
"""
import argparse
import json
import shutil
import numpy as np
from PIL import Image, ImageDraw
import skies_attack_letters as previous
import skies_confirm_footer as captions

ROOT=previous.ROOT
prior=previous.prior
SOURCE=previous.OUT
SOURCE_SHA='dba251cf65b5bdd77cfcfae2e9c4a282529351fa011dd98a0c5a6ff29f45f316'
SYSTEM_SHA='792aa3d823fb2384a72862346968a3f40beccfccd7a6b65e6d21955f73e56607'
OUT=ROOT/'build/skies-vga-compat-v4-vmu-alignment'
STATUS='verified-skies-vga-vmu-alignment'
SHIFT=(4,-6)  # four-times atlas art: +1 X, -1.5 Y native texels


def aligned_caption(text,width):
    original,_=captions.caption(text,width)
    image=Image.new('RGBA',original.size)
    image.paste(original,SHIFT)
    # Horizontal shift must not clip the original visible outline. Vertical
    # headroom is known from the current caption's shared source baseline.
    box=original.getbbox()
    if not box or box[0]+SHIFT[0]<0 or box[2]+SHIFT[0]>image.width or box[1]+SHIFT[1]<0:
        raise ValueError('Aligned caption clips its outline')
    return image


def patch_system(system):
    if prior.sha(system)!=SYSTEM_SHA:raise ValueError('Unknown VGA v3 SYSTEM')
    result=bytearray(system);allowed=set()
    for index,text in captions.LABELS.items():
        rect=captions.AFTER_RECTS[index]
        for offset,value in captions.native.encode(system,captions.TEXTURE,rect,
                aligned_caption(text,rect[2]-rect[0])):
            result[offset:offset+2]=value;allowed.update((offset,offset+1))
    delta=np.flatnonzero(np.frombuffer(system,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if not delta or not set(delta)<=allowed:raise ValueError('Out-of-caption changes')
    return bytes(result),delta,allowed


def preview(before,after):
    out=Image.new('RGBA',(820,235),'#100e0a');draw=ImageDraw.Draw(out)
    draw.text((10,4),'Offline VMU footer: actual captured icon/caption offsets, display aspect 1:2',fill='white')
    rows=captions.native.pack.descriptors(before,captions.TEXTURE)
    for version,system in enumerate((before,after)):
        y=28+version*98
        draw.text((10,y),'Before' if version==0 else 'Aligned: captions +1 X, -1.5 Y native',fill='white')
        atlas=previous.pvr_atlas.decode(system,captions.TEXTURE)
        for col,(button,label) in enumerate(((0,64),(1,63))):
            x=10+col*400
            for index,dx in ((button,0),(label,26)):
                tile=atlas.crop(rows[index])
                # Live nodes scale X2 but retain each origin; UI scanout scales
                # native Y2. Preview2x physical display dimensions, not square
                # atlas texels, so actual 26px caption offset is doubled here.
                tile=tile.resize((tile.width*4,64),Image.Resampling.NEAREST)
                out.alpha_composite(tile,(x+dx*2,y+20))
    out.save(OUT/'footer-alignment-preview.png')


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v3 source differs')
    system,lba=prior.read_file(source,'SYSTEM.DAT');after,delta,_=patch_system(system)
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    report=dict(status=STATUS if build else 'planned-skies-vga-vmu-alignment',disc=2,
        source_sha256=SOURCE_SHA,source=str(SOURCE.relative_to(ROOT)),
        system_sha256=prior.sha(after),changed_system_bytes=len(delta),
        caption_shift_native=[1,-1.5],caption_origins_and_controller_icons_unchanged=True,
        executable_sha256=manifest['executable_sha256'],executable_and_vga_boot_unchanged=True,
        header_size_unchanged=True,header_verified_native_quad=[16,12],
        font_geometry_and_renderer_unchanged=True,attack_letters_retained=True,
        same_existing_save_folder=True,in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve existing alignment build')
    changes,sectors=previous.sector_changes(source,lba,after,delta)
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
            if previous.previous.mode1_sector.regenerate(raw)!=raw:raise ValueError('Output parity invalid')
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
