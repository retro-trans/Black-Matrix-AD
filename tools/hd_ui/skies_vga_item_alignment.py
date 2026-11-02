"""Private VGA v11: inset the Items-only 8x9 list, not its icons/selector."""
import argparse
import json
import shutil
import numpy as np
import skies_vga_approved_baseline as previous
import skies_ritual_font as geometry
import skies_attack_letters as sectors
import mode1_sector
import sh4asm

ROOT=previous.ROOT
prior=previous.prior
SOURCE=previous.OUT
SOURCE_SHA='0d8eb8505c89049d2d1ce72e81ceb5983197fa3bf60f7486af11065b9d99708c'
EXE_SHA=previous.EXE_SHA
SYSTEM_SHA='366faaf4f07ca5f37b265f71fab72e825b1be97ee0f9c652df347c685677f307'
OUT=ROOT/'build/skies-vga-compat-v11-item-alignment'
STATUS='verified-skies-vga-item-alignment'
CONTEXT=0x8c1e7a3c
# Unused tail of v9's authenticated FIND reservation, not font/lookup data.
HELPER=0x8c0f2594
HELPER_END=0x8c0f2600
CAPTURE=ROOT/'build/skies-vga-item-selector-probe-20261031-items/ram.bin'
CAPTURE_SHA='675ce6da464548660df7a9aa55f65dcf287edf3ff919e1d7cd01c7c8e357629b'


def item_helper(*,choice_rows=False,battle_rows=False):
    if battle_rows and not choice_rows:raise ValueError('Battle extension must retain cooking choices')
    a=sh4asm.Asm(HELPER)
    for key,value in dict(context=CONTEXT,old=geometry.HELPER,floats=geometry.size.v.FLOAT_TAB).items():
        a.long_(key,value)
    a.mov(4,0);a.cmp_eq_i(geometry.SLOT);a.bt('old')
    a.mov_l_pc('context',0);a.cmp_eq(0,8);a.bf('old')
    if battle_rows:
        # Packed exact column/row pairs fit all three verified layouts into
        # the SAME108-byte reservation. Context and star guards stay intact.
        for name,cols,rows in (('items_grid',8,9),('cook_grid',7,3),('battle_grid',9,8)):
            a.long_(name,cols|(rows<<16))
        a.mov_l_atd(8,8,0)
        for name in ('items_grid','cook_grid'):
            a.mov_l_pc(name,1);a.cmp_eq(1,0);a.bt('matched')
        a.mov_l_pc('battle_grid',1);a.cmp_eq(1,0);a.bf('old')
        a.label('matched')
    elif choice_rows:
        # Same reusable context, but distinct 7x3 Yes/No/Explain shape.
        # Keep the original 8x9 Items guard and all other grids unchanged.
        a.mov_w_atd_r0(8,8);a.cmp_eq_i(8);a.bt('items')
        a.cmp_eq_i(7);a.bf('old')
        a.mov_w_atd_r0(10,8);a.cmp_eq_i(3);a.bf('old')
        a.bra('matched');a.nop()
        a.label('items');a.mov_w_atd_r0(10,8);a.cmp_eq_i(9);a.bf('old')
        a.label('matched')
    else:
        a.mov_w_atd_r0(8,8);a.cmp_eq_i(8);a.bf('old')
        a.mov_w_atd_r0(10,8);a.cmp_eq_i(9);a.bf('old')
    a.mov_i(16,4);a.mov_w_atd_r0(14,8);a.cmp_eq_i(1);a.bf('pitch');a.mov_i(14,4)
    a.label('pitch')
    if choice_rows:a.mov_w_atd_r0(8,8);a.mov(0,5)
    else:a.mov_i(8,5)
    a.mov(9,2);a.mov_i(2,7)
    a.label('row');a.cmp_hs(5,2);a.bf('top');a.sub(5,2);a.add(4,7);a.bra('row');a.nop()
    a.label('top');a.mov_l_pc('floats',1);a.mov(7,0);a.shll2(0);a.mov_l_r0(1,2)
    for off in (16,24):
        if battle_rows:a.mov_l_stored(2,off,12)
        else:a.mov_i(off,0);a.mov_l_str_r0(2,12)
    # Slot was checked before R4 became the row pitch. The old helper must
    # now take its normal 16x12 path, not mistake that pitch for the star.
    a.mov_i(0,4)
    a.label('old');a.mov_l_pc('old',0);a.jmp(0);a.nop()
    code=a.assemble()
    if HELPER+len(code)>HELPER_END:raise ValueError('Item helper exceeds private reservation')
    return code


def uv_hook(helper):
    return geometry.full.uv_hook(native_quad=geometry.size.QUAD,sample=geometry.size.font.SAMPLE,
        compact_selector=True,geometry_helper=helper,star_slot=geometry.SLOT)


def patch_exe(exe):
    if prior.sha(exe)!=EXE_SHA:raise ValueError('Unknown VGA v10 executable')
    old=uv_hook(geometry.HELPER);new=uv_hook(HELPER);code=item_helper()
    lo=HELPER-prior.atlas.BASE;hi=HELPER_END-prior.atlas.BASE
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    capture=CAPTURE.read_bytes()
    if prior.sha(capture)!=CAPTURE_SHA:raise ValueError('Item capture changed')
    if any(exe[lo:hi]) or any(original[lo:hi]) or any(capture[HELPER-0x8c000000:HELPER_END-0x8c000000]):
        raise ValueError('Item helper padding occupied')
    uv=geometry.full.UV-prior.atlas.BASE
    if exe[uv:uv+len(old)]!=old or len(old)!=len(new):raise ValueError('Unknown full-detail UV helper')
    result=bytearray(exe);result[uv:uv+len(new)]=new;result[lo:lo+len(code)]=code
    delta=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    spans=((uv,uv+len(new)),(lo,lo+len(code)))
    if not delta or any(not any(a<=i<b for a,b in spans) for i in delta):raise ValueError('Out-of-helper edit')
    return bytes(result),delta


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v10 source differs')
    exe,lba=prior.read_file(source,'1ST_READ.BIN');after,delta=patch_exe(exe)
    if prior.sha(prior.read_file(source,'SYSTEM.DAT')[0])!=SYSTEM_SHA:raise ValueError('Approved font differs')
    report=dict(status=STATUS if build else 'planned-skies-vga-item-alignment',disc=2,
        source_sha256=SOURCE_SHA,source_executable_sha256=EXE_SHA,
        source=str(SOURCE.relative_to(ROOT)),executable_sha256=prior.sha(after),system_sha256=SYSTEM_SHA,
        changed_executable_bytes=len(delta),helper_bytes=len(item_helper()),aligned_grid=[8,9],
        context=hex(CONTEXT),inset_native_y=2,glyph_quad=[16,12],capture_sha256=CAPTURE_SHA,
        selector_geometry_and_input_unchanged=True,icons_and_other_grids_unchanged=True,
        approved_font_and_metrics_unchanged=True,vga_startup_and_boot_unchanged=True,
        same_existing_save_folder=True,in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous item-alignment build')
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
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source changed')
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true')
    run(parser.parse_args().build)
