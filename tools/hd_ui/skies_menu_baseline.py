"""Private v11: lower admitted 9x7 main-menu text by two native Y pixels.

No font, spacing, dialogue, selectors, artwork, saves or emulator changes.
Default is a read-only plan; --build creates a new verified local disc copy.
"""
import argparse
import json
import shutil
import numpy as np
import skies_size_match as size

prior=size.prior
full=size.full
ROOT=size.ROOT
SOURCE=ROOT/'build/skies-rayblade-font-v10-ui-load-fix'
SOURCE_SHA='a25aa6412c7a236ea6663084ae9d9d5d29becd98bd367043668a74a757b90585'
OUT=ROOT/'build/skies-rayblade-font-v11-menu-baseline'
INSET=2


def patch(exe):
    old=full.uv_hook(native_quad=size.QUAD,sample=size.font.SAMPLE,compact_selector=True)
    new=full.uv_hook(native_quad=size.QUAD,sample=size.font.SAMPLE,compact_selector=True,menu_inset=INSET)
    lo=full.UV-prior.atlas.BASE;hi=lo+len(new)
    if full.UV+len(new)>full.END:raise ValueError('Baseline hook exceeds reserved arena')
    if exe[lo:lo+len(old)]!=old:raise ValueError('Unknown v10 UV hook')
    origin=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    if any(exe[lo+len(old):hi]) or any(origin[lo:hi]):raise ValueError('UV extension storage occupied')
    after=exe[:lo]+new+exe[hi:]
    offsets=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(after,dtype='u1')).tolist()
    if not offsets or any(not lo<=i<hi for i in offsets):raise ValueError('Invalid baseline delta')
    return after,offsets


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source v10 track differs')
    before,lba=prior.read_file(source,'1ST_READ.BIN');after,offsets=patch(before)
    report=dict(status='verified-skies-menu-baseline' if build else 'planned-skies-menu-baseline',
        writes=build,disc=2,source=str(SOURCE.relative_to(ROOT)),source_sha256=SOURCE_SHA,
        menu_inset_native_y=INSET,menu_inset_display_y=INSET*2,menu_grid=[9,7],
        changed_executable_bytes=len(offsets),executable_sha256=prior.sha(after),
        uv_hook_bytes=len(full.uv_hook(native_quad=size.QUAD,sample=size.font.SAMPLE,compact_selector=True,menu_inset=INSET)),
        glyphs_size_spacing_unchanged=True,dialogue_selectors_fallback_unchanged=True,
        native_objective_cards_retained=24,saves_unchanged=True,in_game_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve prior baseline build')
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir()
    changes={(lba-prior.inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i] for i in offsets}
    report['track_sha256']=prior.copy_track(source,folder/source.name,SOURCE_SHA,changes)
    if prior.read_file(folder/source.name,'1ST_READ.BIN')[0]!=after:raise ValueError('Executable readback differs')
    for name in ('SYSTEM.DAT','CHAR.DAT','MAP.DAT','SCENARIO.DAT','PARAMETA.DAT'):
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
