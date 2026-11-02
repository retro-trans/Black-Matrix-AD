"""One-variable movie comparison, NOT a repair or translated release.

Copy the exact TV-tested English disc and restore ONLY original PROLOGUE.SFD
raw sectors from the authenticated original Disc1 at the same ISO extent.
Separate TV profile/fresh VMUs. No existing apps, discs, configs or saves edited.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import buddy_tv_control as tv
import name_entry_english as names
import mode1_sector

ROOT=tv.ROOT
OUT=Path('M:/Black-Matrix-AD-private-tests/original-prologue-control-20261102')
SOURCE=ROOT/'output/patched-discs-2026-11-01/disc1'
TRACK='Black-Matrix Advanced (Japan) (Disc 1) (Track 3).bin'
SOURCE_SHA='2f3b7ec03ac689cf728dd6d7f38b50acf84d37bf313899a5ea0641046cecf73e'
ORIGINAL=ROOT/TRACK
ORIGINAL_SHA='7bb9a6d316b9627c01d5b24cd56b83a53352ca6fb08d0787b36b31b419683cd8'
MOVIE='PROLOGUE.SFD'
MOVIE_SHA='0be68894de4ecf64f59acc96fbc951f1956843b4e1cb6507747c4ada2456d923'
ENGLISH_SHA='84f0a94aad61027022856cca027f181abe923f53a2d11215339868a9e1e3abfa'
READER=names.budget.legacy.footer.prior


def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def plan():
    original,olba=READER.read_file(ORIGINAL,MOVIE)
    english,lba=READER.read_file(SOURCE/TRACK,MOVIE)
    if names.sha(original)!=MOVIE_SHA or names.sha(english)!=ENGLISH_SHA:
        raise ValueError('Movie sources differ')
    if lba!=olba or len(original)!=len(english) or len(original)%2048:
        raise ValueError('Movie extent is not identical and sector-aligned')
    return dict(movie=MOVIE,lba=lba,bytes=len(original),first_sector=lba-45000,
                sector_count=len(original)//2048,original_sha256=MOVIE_SHA,supplied_sha256=ENGLISH_SHA)


def overlay(raw,first,original_stream,p):
    count=len(raw)//2352
    lo=max(first,p['first_sector']);hi=min(first+count,p['first_sector']+p['sector_count'])
    if lo>=hi:return raw
    original_stream.seek(lo*2352);replacement=original_stream.read((hi-lo)*2352)
    if len(replacement)!=(hi-lo)*2352:raise ValueError('Original raw extent is incomplete')
    original=np.frombuffer(replacement,'u1').reshape(-1,2352)
    before=np.frombuffer(raw,'u1').reshape(-1,2352)[lo-first:hi-first]
    if not np.array_equal(original[:,:16],before[:,:16]):raise ValueError('Original raw sector headers differ')
    if mode1_sector.regenerate(replacement)!=replacement:raise ValueError('Original movie parity invalid')
    result=bytearray(raw);start=(lo-first)*2352
    result[start:start+len(replacement)]=replacement
    return bytes(result)


def build():
    if OUT.exists():raise ValueError('Preserve existing original-movie control')
    if shutil.disk_usage(OUT.anchor).free<2*1024**3:raise ValueError('Insufficient comparison space')
    p=plan()
    if digest(ORIGINAL)!=ORIGINAL_SHA:raise ValueError('Original Disc1 changed')
    OUT.mkdir();folder=OUT/'disc1';folder.mkdir();target=folder/TRACK
    h=hashlib.sha256();new=hashlib.sha256();sector=0
    with (SOURCE/TRACK).open('rb') as src,ORIGINAL.open('rb') as original,target.open('xb') as dst:
        while raw:=src.read(2352*4096):
            h.update(raw);after=overlay(raw,sector,original,p);dst.write(after);new.update(after)
            sector+=len(raw)//2352
    if h.hexdigest()!=SOURCE_SHA:raise ValueError('TV comparison source changed')
    # Independently compare every raw output byte to its permitted source.
    h=hashlib.sha256();sector=0
    with (SOURCE/TRACK).open('rb') as src,ORIGINAL.open('rb') as original,target.open('rb') as dst:
        while raw:=src.read(2352*4096):
            actual=dst.read(len(raw));h.update(actual)
            if actual!=overlay(raw,sector,original,p):raise ValueError('Raw output outside single movie allowlist')
            sector+=len(raw)//2352
        if dst.read(1):raise ValueError('Unexpected trailing bytes')
    if h.hexdigest()!=new.hexdigest():raise ValueError('Output hash readback differs')
    with (SOURCE/TRACK).open('rb') as src:directory=list(READER.inject.iso_files(src));boot=READER.inject._extent(src,45000,32768)
    with target.open('rb') as dst:
        if list(READER.inject.iso_files(dst))!=directory or READER.inject._extent(dst,45000,32768)!=boot:
            raise ValueError('ISO directory or boot changed')
    for name,_,_ in directory:
        before,_=READER.read_file(SOURCE/TRACK,name);after,_=READER.read_file(target,name)
        if names.sha(after)!=(MOVIE_SHA if name==MOVIE else names.sha(before)):
            raise ValueError('Payload changed: '+name)
    files=[dict(name=TRACK,sha256=new.hexdigest(),bytes=target.stat().st_size)]
    for source in SOURCE.iterdir():
        if source.is_file() and source.name!=TRACK:
            dest=folder/source.name
            with source.open('rb') as src,dest.open('xb') as dst:shutil.copyfileobj(src,dst)
            if digest(dest)!=digest(source):raise ValueError('Companion mismatch')
            files.append(dict(name=source.name,sha256=digest(dest),bytes=dest.stat().st_size))
    exe,_=READER.read_file(target,'1ST_READ.BIN')
    if names.sha(exe)!=tv.EXE_SHA:raise ValueError('Control executable differs from TV baseline')
    (OUT/'1ST_READ.BIN').write_bytes(exe)
    if digest(SOURCE/TRACK)!=SOURCE_SHA or digest(ORIGINAL)!=ORIGINAL_SHA:
        raise ValueError('Input changed during comparison build')
    report=dict(status='original-prologue-comparison-runtime-pending',purpose='diagnostic-only-not-a-fix',
        source_track_sha256=SOURCE_SHA,original_track_sha256=ORIGINAL_SHA,files=files,
        track_sha256=new.hexdigest(),executable_sha256=tv.EXE_SHA,only_iso_file_changed=MOVIE,
        movie=p,exact_raw_movie_allowlist_verified=True,original_sector_parity_retained=True,
        original_and_english_builds_unchanged=True,private_local_only=True,gameplay_verified=False)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    cue=folder/'Black-Matrix Advanced (Japan) (Disc 1).cue'
    tv.prepare(OUT/'play',3,cue,OUT/'1ST_READ.BIN',tv.EXE_SHA)
    print('Original Japanese prologue control ready:',cue,flush=True)


def launch():
    report=json.loads((OUT/'manifest.json').read_text())
    if report['status']!='original-prologue-comparison-runtime-pending':raise ValueError('Unknown comparison')
    for row in report['files']:
        if digest(OUT/'disc1'/row['name'])!=row['sha256']:raise ValueError('Comparison file changed')
    print('Diagnostic only: choose New Game and reach the SAME prologue scene.',flush=True)
    print('This comparison prologue deliberately has original Japanese audio and NO English subtitles.',flush=True)
    tv.launch(OUT/'play',OUT/'disc1/Black-Matrix Advanced (Japan) (Disc 1).cue',OUT/'1ST_READ.BIN')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--launch',action='store_true');a=p.parse_args()
    if a.build:build()
    elif a.launch:launch()
    else:print(json.dumps(plan(),indent=2));print('Dry run: no disc files or profiles modified.')
