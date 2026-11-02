"""Private v13: optically centre and lower only the Pick VMU header.

No wording, font pixels, glyph sizes, spacing, emulator or save changes.
Default is a read-only plan; --build creates a new private Disc2 copy.
"""
import argparse
import json
import shutil
import numpy as np
import skies_ritual_font as previous

prior=previous.prior
ROOT=previous.ROOT
SOURCE=previous.OUT
SOURCE_SHA='193d26acd0c9839042a92fa33d619e38d40aaf0115ef531e918f85d52cc9e995'
OUT=ROOT/'build/skies-rayblade-font-v13-vmu-header'
TEXT='Pick VMU'
CONTEXT=0x8C1E7780
ORIGIN_X=279


def ink_bounds(exe,system):
    pages=[previous.full.decode_vq(system[prior.FONT_OFFSET+16+b*128:prior.FONT_OFFSET+16+b*128+8192]) for b in previous.full.BANKS]
    pen=0;bounds=[]
    for ch in TEXT:
        glyph=0 if ch==' ' else prior.latin.charmap()[ch]
        slot=exe[prior.atlas.FORWARD-prior.atlas.BASE+glyph]
        x=slot%8*16;y=slot%32//8*32
        box=pages[slot//32].crop((x,y,x+16,y+24)).getbbox()
        if box:bounds.append((pen+box[0],pen+box[2]))
        pen+=exe[previous.size.SMALL_ADV-prior.atlas.BASE+glyph]
    return min(b[0] for b in bounds),max(b[1] for b in bounds)


def patch(exe):
    old=previous.geometry_helper();new=previous.geometry_helper(vmu_origin=ORIGIN_X)
    lo=previous.HELPER-prior.atlas.BASE;hi=lo+len(new)
    if exe[lo:lo+len(old)]!=old:raise ValueError('Unknown v12 geometry helper')
    origin=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    if any(origin[lo:hi]) or any(exe[lo+len(old):hi]):raise ValueError('Helper extension is not unused')
    after=exe[:lo]+new+exe[hi:]
    delta=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(after,dtype='u1')).tolist()
    if not delta or any(not lo<=i<hi for i in delta):raise ValueError('Out-of-scope header edit')
    return after,delta


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source v12 track differs')
    exe,lba=prior.read_file(source,'1ST_READ.BIN');system,_=prior.read_file(source,'SYSTEM.DAT')
    bounds=ink_bounds(exe,system)
    if bounds!=(2,80) or ORIGIN_X+(sum(bounds)/2)!=320:raise ValueError('VMU header ink metrics differ')
    after,delta=patch(exe)
    report=dict(status='verified-skies-vmu-header' if build else 'planned-skies-vmu-header',writes=build,
        disc=2,source=str(SOURCE.relative_to(ROOT)),source_sha256=SOURCE_SHA,text=TEXT,
        context=hex(CONTEXT),grid=[8,1],old_origin_x=204,origin_x=ORIGIN_X,
        ink_bounds=bounds,ink_center_x=320,local_top_y=2,helper_bytes=len(previous.geometry_helper(vmu_origin=ORIGIN_X)),
        changed_executable_bytes=len(delta),executable_sha256=prior.sha(after),
        font_pixels_size_spacing_wording_unchanged=True,native_objective_cards_retained=24,
        saves_unchanged=True,in_game_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous VMU header build')
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir()
    changes={(lba-prior.inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i] for i in delta}
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
