"""Build separate checklist test discs; never launch or change a live game."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/hd_ui')]
import awaken_confirm as builder
import s_rank_checklist as patch
import s_rank_rules

OUT=ROOT/'build/s-rank-checklist-v4'
VARIANTS={
    'hd':('reusable-atlas-noto-ui-r35-hd-attack-modes-v1-shop-confirm-v1','s-rank-checklist-hd-v4'),
    'native':('reusable-atlas-noto-ui-r35-native-silver-attack-split-v1-shop-confirm-v1','s-rank-checklist-native-v4'),
    'hd-analog':('analog-movement-hd-v1-shop-confirm-v1','s-rank-checklist-hd-analog-v4'),
    'native-analog':('analog-movement-native-v1-shop-confirm-v1','s-rank-checklist-native-analog-v4'),
}


def rank_signature(data=None):
    result=[]
    for row in s_rank_rules.catalog(data):
        result.append((row['group'],row['limits'],[s['args'] for s in row['rank_writes']]))
    return result


def main():
    # Check the actual translated scenario in each source, not just a loose
    # original file. This catches stale builds with different scoring rules.
    expected=rank_signature();seen=set();reports=[]
    for mode,(source,_) in VARIANTS.items():
        for disc,folder in [(1,'disc'),(2,'disc2')]:
            track=ROOT/'build'/source/folder/f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
            with track.open('rb') as f:
                data=builder.engine.native.inject._extent(f,*builder.engine.native.inject.find(f,'SCENARIO.DAT'))
            digest=hashlib.sha256(data).hexdigest()
            if digest not in seen:
                if rank_signature(data)!=expected:raise ValueError(f'Rank rules differ in {mode} disc {disc}')
                seen.add(digest)
            reports.append(dict(mode=mode,disc=disc,scenario_sha256=digest))
    builder.build(patcher=patch.patch,out=OUT,variants=VARIANTS,status='verified-s-rank-checklist',
                  details=dict(test_build=True,ranked_battle_scripts=55,
                               revision=4,runtime_to_archive_group_offset=1,
                               marks='solid vector check/cross/dash; no font glyphs',
                               hud_labels='uppercase; 14x9 framebuffer glyphs, 11-unit rows; displayed with 2x vertical stretch',
                               faust_groups=[262,339,481],scenario_verification=reports,
                               scoring_and_input_unchanged=True,default_launchers_unchanged=True))
    (OUT/'rules.json').write_text(json.dumps(s_rank_rules.catalog(),indent=2),encoding='utf-8')
    (OUT/'README.txt').write_text(
        'S RANK CHECKLIST - TEST BUILD\n\n'
        'Use Play - HD - S Rank Checklist.cmd. It includes analog movement and\n'
        'the existing instant Status transition. Native textures can be tested\n'
        'by adding -NoHDTextures. Both discs are included; add -Disc2Cards for Disc 2.\n\n'
        'Close your current emulator yourself, then cold-boot this build and\n'
        'continue from your normal in-game VMU save. Do not load an old emulator\n'
        'save state: it restores the old executable into memory. No VMU data\n'
        'was changed by this build. Existing normal launchers stay unchanged.\n\n'
        'Open the battle Turn menu. Check text, marks, panel edges and closing.\n'
        'Green check = currently met; red X = failed/penalty; gray dash = pending.\n'
        'Score now is provisional, not a promise of the final rank.\n'
        'Faust appears only on his three bonus maps. Recruitment conditions\n'
        'appear only on the applicable battle scripts. No generic empty section.\n'
        'cap3/cap2/cap1 denotes the maximum point deduction, not an allowed-use count.\n\n'
        'Code-level tests and byte-exact disc readback are verified. Visual and\n'
        'in-game testing is left to you as requested.\n',encoding='utf-8')


def finalize_labels():
    """Four-byte display-only correction to this unreleased test build.

    The stock formatter hides plus signs. Use 2p/1p instead. Authenticate the
    full executable and track's existing digest before any generated output
    is touched; neither source builds nor textures are edited.
    """
    if OUT.name!='s-rank-checklist-v1':
        raise ValueError('This historical label correction is only for revision 1')
    report=json.loads((OUT/'build-verification.json').read_text(encoding='utf-8'))
    for mode,(src,dst) in VARIANTS.items():
        target=ROOT/'build'/dst
        manifest=json.loads((target/'manifest.json').read_text(encoding='utf-8'))
        for disc,folder in [(1,'disc'),(2,'disc2')]:
            name=f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
            track=target/folder/name
            executable=target/('1ST_READ.BIN' if disc==1 else '1ST_READ.disc2.BIN')
            row=next(r for r in report['variants'] if r['mode']==mode and r['disc']==disc)
            if builder.engine.native.base.digest(track)!=row['track_sha256']:
                raise ValueError('Generated track changed since verification')
            source=(ROOT/'build'/src/executable.name).read_bytes()
            desired=patch.patch(source)
            with track.open('rb') as f:
                lba,size=builder.engine.native.inject.find(f,'1ST_READ.BIN')
                before=builder.engine.native.inject._extent(f,lba,size)
            if before!=executable.read_bytes():raise ValueError('Executable readback differs')
            # Reconstruct the only accepted pre-correction executable.
            old=bytearray(desired)
            string_blob=patch.data_blobs()[patch.STRINGS]
            for new_text,old_text in [(b'2p',b'+2'),(b'1p',b'+1')]:
                position=string_blob.index(new_text)+patch.STRINGS-patch.BASE
                old[position:position+2]=old_text
            if before not in (desired,bytes(old)):raise ValueError('Unexpected trial executable')
            changes={i:b for i,(a,b) in enumerate(zip(before,desired)) if a!=b}
            if len(changes) not in (0,4):raise ValueError('Unexpected correction size')
            with track.open('r+b') as f:
                for off,value in changes.items():
                    f.seek(builder.engine.raw_offset(lba,off));f.write(bytes([value]))
            with track.open('rb') as f:
                if builder.engine.native.inject._extent(f,lba,size)!=desired:raise ValueError('Correction readback failed')
            executable.write_bytes(desired)
            row['track_sha256']=builder.engine.native.base.digest(track)
            row['changed_bytes']=sum(a!=b for a,b in zip(source,desired))
            next(r for r in manifest['variants'] if r['disc']==disc).update(row)
            print(mode+' disc '+str(disc)+' final labels verified',flush=True)
        (target/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    report['bonus_labels']='2p / 1p; stock HUD formatter hides plus signs'
    (OUT/'build-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    if '--finalize-labels' in sys.argv:finalize_labels()
    else:main()
