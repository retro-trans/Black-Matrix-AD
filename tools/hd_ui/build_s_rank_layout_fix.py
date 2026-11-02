"""Guarded rendering-only disc copies, without touching any live game files.

Default: v2 -> v3 four-byte vertical layout correction. --v4: v3 -> v4 solid
vector status marks. Authenticate complete input tracks, apply a code-region
allowlist, and hash/read back complete outputs. No texture/profile/save access.
"""
import hashlib
import json
import struct
from pathlib import Path

import build_s_rank_checklist as full

ROOT=full.ROOT
PATCH=full.patch
OUT=ROOT/'build/s-rank-checklist-v3'
PRIOR=ROOT/'build/s-rank-checklist-v2'
MODES={
    'hd':'reusable-atlas-noto-ui-r35-hd-attack-modes-v1-shop-confirm-v1',
    'native':'reusable-atlas-noto-ui-r35-native-silver-attack-split-v1-shop-confirm-v1',
    'hd-analog':'analog-movement-hd-v1-shop-confirm-v1',
    'native-analog':'analog-movement-native-v1-shop-confirm-v1',
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def copy_verified(source,target,expected=None,changes=None):
    changes=changes or {}
    before=hashlib.sha256();after=hashlib.sha256();position=0
    with source.open('rb') as src,target.open('xb') as dst:
        while chunk:=src.read(4*1024*1024):
            before.update(chunk)
            data=bytearray(chunk)
            for off,value in changes.items():
                if position<=off<position+len(data):data[off-position]=value
            dst.write(data);after.update(data);position+=len(data)
    if expected is not None and before.hexdigest()!=expected:
        raise ValueError('Input differs from verified v2: '+str(source))
    if any(off>=position or off<0 for off in changes):raise ValueError('Out-of-track patch')
    if digest(target)!=after.hexdigest():raise ValueError('Output readback differs: '+str(target))
    return after.hexdigest()


def executables(source,revision=3):
    if revision==4:
        previous=PATCH.patch(source,vector_marks=False)
        desired=PATCH.patch(source,vector_marks=True)
        delta={i:b for i,(a,b) in enumerate(zip(previous,desired)) if a!=b}
        if not delta or any(not PATCH.RENDER-PATCH.BASE<=off<PATCH.RENDER-PATCH.BASE+960 for off in delta):
            raise ValueError('Unexpected non-marker-code change')
        return previous,desired,delta
    desired=PATCH.patch(source,vector_marks=False)
    current=PATCH.GLYPH_HEIGHT,PATCH.ROW_ADVANCE,PATCH.TICK_SLANT
    try:
        PATCH.GLYPH_HEIGHT,PATCH.ROW_ADVANCE,PATCH.TICK_SLANT=18,22,3
        previous=PATCH.patch(source,vector_marks=False)
    finally:
        PATCH.GLYPH_HEIGHT,PATCH.ROW_ADVANCE,PATCH.TICK_SLANT=current
    delta={i:b for i,(a,b) in enumerate(zip(previous,desired)) if a!=b}
    if len(delta)!=4:raise ValueError('Layout correction must change exactly four bytes')
    allowed=[(PATCH.DRAW-PATCH.BASE,PATCH.DRAW-PATCH.BASE+len(PATCH.draw())),
             (PATCH.RENDER-PATCH.BASE,PATCH.RENDER-PATCH.BASE+len(PATCH.render()))]
    if any(not any(lo<=off<hi for lo,hi in allowed) for off in delta):
        raise ValueError('Unexpected non-rendering change')
    return previous,desired,delta


def main(revision=3):
    if revision not in (3,4):raise ValueError('Unsupported revision')
    OUT=ROOT/'build'/f's-rank-checklist-v{revision}'
    PRIOR=ROOT/'build'/f's-rank-checklist-v{revision-1}'
    baseline=json.loads((PRIOR/'build-verification.json').read_text())
    if baseline['status']!='verified-s-rank-checklist' or len(baseline['variants'])!=8:
        raise ValueError('Missing verified v2 baseline')
    destinations=[ROOT/'build'/f's-rank-checklist-{mode}-v{revision}' for mode in MODES]
    if OUT.exists() or any(p.exists() for p in destinations):raise ValueError('Preserve existing outputs')
    OUT.mkdir();reports=[]
    for mode,base in MODES.items():
        prior=ROOT/'build'/f's-rank-checklist-{mode}-v{revision-1}'
        target=ROOT/'build'/f's-rank-checklist-{mode}-v{revision}';target.mkdir()
        print(mode+': copying and verifying rendering-only revision',flush=True)
        for p in prior.iterdir():
            if p.is_file() and p.suffix!='.json' and p.name not in ('1ST_READ.BIN','1ST_READ.disc2.BIN'):
                copy_verified(p,target/p.name)
        variants=[]
        for disc,folder in [(1,'disc'),(2,'disc2')]:
            exe_name='1ST_READ.BIN' if disc==1 else '1ST_READ.disc2.BIN'
            previous,desired,delta=executables((ROOT/'build'/base/exe_name).read_bytes(),revision)
            if (prior/exe_name).read_bytes()!=previous:raise ValueError('Unrecognized v2 executable')
            name=f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
            src=prior/folder/name
            with src.open('rb') as f:
                lba,size=full.builder.engine.native.inject.find(f,'1ST_READ.BIN')
                if full.builder.engine.native.inject._extent(f,lba,size)!=previous:
                    raise ValueError('v2 disc executable differs')
            raw={full.builder.engine.raw_offset(lba,i):v for i,v in delta.items()}
            reference=next(r for r in baseline['variants'] if r['mode']==mode and r['disc']==disc)
            dest=target/folder;dest.mkdir()
            sha=copy_verified(src,dest/name,reference['track_sha256'],raw)
            with (dest/name).open('rb') as f:
                if full.builder.engine.native.inject._extent(f,lba,size)!=desired:
                    raise ValueError('v3 executable readback failed')
            for p in (prior/folder).iterdir():
                if p.name!=name:
                    if not p.is_file():raise ValueError('Unexpected disc subdirectory')
                    copy_verified(p,dest/p.name)
            (target/exe_name).write_bytes(desired)
            row=dict(mode=mode,disc=disc,**{f'changed_bytes_from_v{revision-1}':len(delta)},
                     track_sha256=sha,source_track_sha256=reference['track_sha256'],
                     changes=[dict(executable_offset=i,before=previous[i],after=v) for i,v in delta.items()])
            variants.append(row);reports.append(row)
            print(mode+' disc '+str(disc)+f' verified ({len(delta)} rendering bytes only)',flush=True)
        (target/'manifest.json').write_text(json.dumps(dict(status='verified-s-rank-checklist',revision=revision,variants=variants),indent=2))
    result=dict(status='verified-s-rank-checklist',revision=revision,test_build=True,variants=reports,
                live_game_verified=False,framebuffer=[640,240],display=[640,480],
                glyph_framebuffer=[14,9],row_advance_framebuffer=11,
                panel_framebuffer=[352,192],source_report=str(PRIOR/'build-verification.json'),
                texture_files_accessed=False,save_files_accessed=False,
                preservation=f'Full authenticated v{revision-1} track copy with allowlisted rendering-only changes; other copied files readback-verified.')
    (OUT/'build-verification.json').write_text(json.dumps(result,indent=2))
    (OUT/'README.txt').write_text(f'S RANK CHECKLIST v{revision} - RENDERING FIX\n\n'
        'Use Play - HD - S Rank Checklist.cmd. Cold boot and load an in-game VMU save, not an old emulator save state.\n'
        'Native drawing coordinates are 640x240, displayed at 640x480. Text height and row spacing now account for that stretch.\n'
        'Rendering-only correction. V4 uses solid vector check/cross/dash marks, not font glyphs. No gameplay, score, texture or save changes.\n'
        'Full-track and executable readback verified. In-game check remains with the user.\n')


if __name__=='__main__':
    import sys
    main(4 if '--v4' in sys.argv else 3)
