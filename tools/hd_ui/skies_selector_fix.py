"""Repair native font format transitions and compact confirmation geometry.

Private v5 derives from v4; only reserved executable hook storage changes.
"""
import json
import shutil
import sys
import numpy as np
import skies_baseline_fix as baseline

font=baseline.font
full=font.full
prior=font.prior
ROOT=font.ROOT
SOURCE=baseline.OUT
SOURCE_SHA='60914f338f026eca0952476a05f7e7c756c43a9db3ef54eb6b0c15c6e977faa4'
OUT=ROOT/'build/skies-rayblade-font-v5-selector'


def patch(exe):
    result=bytearray(exe);allowed=[]
    for start,end,before,after in (
        (full.FILL,full.FILL+256,full.fill_hook(),full.fill_hook(reset_fallback=True)),
        (full.UV,full.END,full.uv_hook(native_quad=font.QUAD,sample=font.SAMPLE),
         full.uv_hook(native_quad=font.QUAD,sample=font.SAMPLE,compact_selector=True))):
        lo=start-prior.atlas.BASE;hi=end-prior.atlas.BASE
        if exe[lo:hi]!=before+bytes(hi-lo-len(before)):
            raise ValueError('Unexpected previous font hook')
        if start+len(after)>end:raise ValueError('Font hook exceeds reservation')
        result[lo:hi]=after+bytes(hi-lo-len(after));allowed.append((lo,hi))
    offsets=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if any(not any(lo<=i<hi for lo,hi in allowed) for i in offsets):
        raise ValueError('Out-of-scope executable edit')
    return bytes(result),offsets


def build():
    if OUT.exists():raise ValueError('Preserve previous selector build')
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source track differs')
    exe,lba=prior.read_file(source,'1ST_READ.BIN');after,offsets=patch(exe)
    changes={(lba-prior.inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i] for i in offsets}
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir()
    sha=prior.copy_track(source,folder/source.name,SOURCE_SHA,changes)
    if prior.read_file(folder/source.name,'1ST_READ.BIN')[0]!=after:raise ValueError('Executable readback differs')
    for name in ('SYSTEM.DAT','MAP.DAT','SCENARIO.DAT'):
        if prior.read_file(source,name)[0]!=prior.read_file(folder/source.name,name)[0]:
            raise ValueError('Unrelated payload differs: '+name)
    companions=[]
    for p in source.parent.iterdir():
        if p.is_file() and p!=source:
            shutil.copy2(p,folder/p.name);digest=prior.digest(p)
            if prior.digest(folder/p.name)!=digest:raise ValueError('Companion differs')
            companions.append(dict(file=p.name,sha256=digest))
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source changed')
    report=dict(status='verified-skies-selector-fallback',disc=2,
        source=str(SOURCE.relative_to(ROOT)),source_sha256=SOURCE_SHA,track_sha256=sha,
        executable_sha256=prior.sha(after),changed_executable_bytes=len(offsets),
        fill_bytes=len(full.fill_hook(reset_fallback=True)),
        uv_bytes=len(full.uv_hook(native_quad=font.QUAD,sample=font.SAMPLE,compact_selector=True)),
        fallback_pvrt_format='0x0105: twiddled 4bpp palette',
        admitted_pvrt_format='0x0302: VQ ARGB4444',
        selector_shape=[3,2],selector_top=[2,18],selector_height=11,
        source_glyphs_metrics_dialogue_and_archives_unchanged=True,
        native_objective_cards_retained=24,saves_unchanged=True,companions=companions,
        in_game_verified=False)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['build']:build()
    else:print('Fill / UV bytes:',len(full.fill_hook(reset_fallback=True)),len(full.uv_hook(compact_selector=True)))
