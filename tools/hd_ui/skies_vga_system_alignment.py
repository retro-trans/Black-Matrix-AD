"""Private VGA v6: lower admitted Save/Load/Setup text inside its selector rows."""
import argparse
import json
import shutil
import numpy as np
import skies_vga_port_slot as previous
import skies_ritual_font as geometry
import skies_attack_letters as sectors
import mode1_sector

ROOT=previous.ROOT
prior=previous.prior
SOURCE=previous.OUT
SOURCE_SHA='6aeddc17dddb5ee22d989a7611a224069014fa868841630687e7223d80fab207'
EXE_SHA='0ca9097483e4e4dc08e089d22350084bab21402e9722f9dca42d5d907af53f2c'
OUT=ROOT/'build/skies-vga-compat-v6-system-alignment'
STATUS='verified-skies-vga-system-alignment'
CONTEXT=0x8c1e838c


def patch_exe(exe):
    if prior.sha(exe)!=EXE_SHA:raise ValueError('Unknown VGA v5 executable')
    old=geometry.geometry_helper(vmu_origin=279)
    new=geometry.geometry_helper(vmu_origin=279,system_menu_inset=True)
    lo=geometry.HELPER-prior.atlas.BASE;hi=geometry.HELPER_END-prior.atlas.BASE
    if exe[lo:lo+len(old)]!=old or any(exe[lo+len(old):hi]):
        raise ValueError('Unknown geometry helper or occupied extension')
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    if any(original[lo:hi]):raise ValueError('Original helper reservation occupied')
    result=exe[:lo]+new+bytes(hi-lo-len(new))+exe[hi:]
    delta=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if not delta or not all(lo<=i<hi for i in delta):raise ValueError('Out-of-helper edit')
    return result,delta


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v5 source differs')
    exe,lba=prior.read_file(source,'1ST_READ.BIN');after,delta=patch_exe(exe)
    report=dict(status=STATUS if build else 'planned-skies-vga-system-alignment',disc=2,
        source_sha256=SOURCE_SHA,source_executable_sha256=EXE_SHA,
        source=str(SOURCE.relative_to(ROOT)),executable_sha256=prior.sha(after),
        changed_executable_bytes=len(delta),helper_bytes=len(geometry.geometry_helper(vmu_origin=279,system_menu_inset=True)),
        aligned_grid=[5,3],inset_native_y=2,glyph_quad=[16,12],
        selector_geometry_and_input_unchanged=True,all_font_pixels_size_spacing_unchanged=True,
        vga_startup_and_boot_unchanged=True,all_system_art_and_movies_retained=True,
        same_existing_save_folder=True,in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous system-menu build')
    changes,touched=sectors.sector_changes(source,lba,after,delta)
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir();target=folder/source.name
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
        if new!=(after if name=='1ST_READ.BIN' else old):raise ValueError('Unrelated payload changed: '+name)
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
