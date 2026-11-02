"""Private VGA v13 sampling candidate: half-source-texel V bias, no font edits.

The actual GPU result still requires a fresh cold-launch screenshot. Native
SH4/packet/sampling-model checks must never be described as visual proof.
"""
import argparse
import json
import shutil
import numpy as np
import skies_vga_optical_baseline as previous
import skies_vga_item_alignment as item
import skies_vga_sharp_footer as footer
import mode1_sector

ROOT=previous.ROOT
prior=previous.prior
SOURCE=previous.OUT
SOURCE_SHA='e2417ca1a98fa8b9c73e7a20e523257578e46c259fed16c252d24260b14fe45d'
EXE_SHA=previous.EXE_SHA
SYSTEM_SHA='7c283705aa68f156e79521163ea4a98f5de8ca07aa4042400c9fdbe23f1aeeb7'
OUT=ROOT/'build/skies-vga-compat-v13-sampling'
STATUS='verified-skies-vga-sampling-candidate'
CAPTURE=ROOT/'build/skies-think-alignment-probe-20261101/ram.bin'
CAPTURE_SHA='5271c780602595e04a802241398861c7ca563918bb22f97ed1640a57b20ead5b'


def uv_hook():
    g=item.geometry
    return g.full.uv_hook(native_quad=g.size.QUAD,sample=g.size.font.SAMPLE,
        compact_selector=True,geometry_helper=item.HELPER,star_slot=g.SLOT,vertical_texel_center=True)


def patch_exe(exe):
    if prior.sha(exe)!=EXE_SHA:raise ValueError('Unknown VGA v12 executable')
    result=bytearray(exe);spans=[]
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes();capture=CAPTURE.read_bytes()
    if prior.sha(capture)!=CAPTURE_SHA:raise ValueError('Sampling capture differs')
    for addr,end,old,new in (
        (item.geometry.full.UV,item.geometry.full.END,item.uv_hook(item.HELPER),uv_hook()),
        (footer.GEOMETRY,footer.GEOMETRY_END,footer.geometry(),footer.geometry(vertical_texel_center=True))):
        lo=addr-prior.atlas.BASE;hi=end-prior.atlas.BASE
        if addr+len(new)>end or len(new)<len(old):raise ValueError('Sampling arena exceeded')
        if exe[lo:lo+len(old)]!=old or any(exe[lo+len(old):hi]):raise ValueError('Sampling code/padding differs')
        if any(original[lo:hi]):raise ValueError('Original arena occupied')
        if any(capture[addr-0x8c000000+len(old):end-0x8c000000]):raise ValueError('Live extension occupied')
        result[lo:lo+len(new)]=new;spans.append((lo,lo+len(new)))
    delta=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if not delta or any(not any(a<=i<b for a,b in spans) for i in delta):raise ValueError('Out-of-sampling edit')
    return bytes(result),delta,spans


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v12 source differs')
    print('Source track authenticated.',flush=True)
    exe,lba=prior.read_file(source,'1ST_READ.BIN');after,delta,spans=patch_exe(exe)
    if prior.sha(prior.read_file(source,'SYSTEM.DAT')[0])!=SYSTEM_SHA:raise ValueError('V12 font differs')
    report=dict(status=STATUS if build else 'planned-skies-vga-sampling-candidate',disc=2,
        source_sha256=SOURCE_SHA,source=str(SOURCE.relative_to(ROOT)),source_executable_sha256=EXE_SHA,
        executable_sha256=prior.sha(after),system_sha256=SYSTEM_SHA,changed_executable_bytes=len(delta),
        allowed_executable_spans=spans,capture_sha256=CAPTURE_SHA,
        canonical_uv_helper_bytes=len(uv_hook()),footer_geometry_bytes=len(footer.geometry(vertical_texel_center=True)),
        vertical_uv_bias_fixed_point=1,vertical_uv_bias_source_texels=.5,
        horizontal_uv_and_sample_spans_unchanged=True,all_glyph_pixels_and_font_allocations_unchanged=True,
        geometry_spacing_icons_star_and_native_fallback_unchanged=True,
        dialogue_header_and_direct_footer_sampling_consistent=True,
        item_alignment_and_vga_timing_retained=True,same_existing_save_folder=True,
        in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous sampling build')
    changes,touched=item.sectors.sector_changes(source,lba,after,delta)
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir();target=folder/source.name
    print('Writing private candidate and verifying exact raw changes.',flush=True)
    report['track_sha256']=prior.copy_track(source,target,SOURCE_SHA,changes)
    report.update(changed_raw_bytes=len(changes),parity_repaired_sectors=touched)
    with source.open('rb') as stream:
        directory=list(prior.inject.iso_files(stream));boot=prior.inject._extent(stream,45000,32768)
    with target.open('rb') as stream:
        if list(prior.inject.iso_files(stream))!=directory or prior.inject._extent(stream,45000,32768)!=boot:
            raise ValueError('Boot or directory changed')
        for sector in touched:
            stream.seek(sector*2352);raw=stream.read(2352)
            if mode1_sector.regenerate(raw)!=raw:raise ValueError('Output sector parity invalid')
    print('Checking every game payload and companion.',flush=True)
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
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');run(p.parse_args().build)
