"""Combine existing reviewed artwork and user-confirmed prologue timing fix.

NEW complete private pair only. Disc1 changes only PROLOGUE raw sectors from
the authenticated successful timing trial. Disc2 is copied byte-for-byte from
the ImageGen pair. Never re-encode the movie, regenerate artwork or edit inputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

import original_prologue_control as control
import pack_imagegen_master as artwork
import prologue_timing_trial as timing
import run_name_entry_english as runner

ROOT=control.ROOT
SOURCE=artwork.OUT
OUT=ROOT/'output/patched-discs-combined-2026-11-02'
STATUS='private-combined-imagegen-prologue-runtime-pending'
EXE_SHA='c95d17c13a0cc7165f4786578806b02696c08281af64d0c73aa21cd60c171957'
SYSTEM_SHA='7ad637acac86f8aa80cafbf3fc3f970a37ad07a868f7cd6fbf3d45dbeb16c382'
MOVIE_SHA='7d2e9300df4009d39973c3e964d509bdd32084142ddf641d7a0eee0208d61b2c'
TRIAL_TRACK_SHA='51ffbaf117f888f8295868ed0b12129d6c0e19f2096c3189c87a8bf0dbaa0ad5'
READER=control.READER


def verify_files(folder,rows):
    for row in rows:
        path=folder/row['path']
        if path.stat().st_size!=row['bytes'] or control.digest(path)!=row['sha256']:
            raise ValueError('File identity changed: '+str(path))


def cue_checks(folder):
    for disc in (1,2):
        cue=folder/f'disc{disc}/Black-Matrix Advanced (Japan) (Disc {disc}).cue'
        names=re.findall(r'^FILE "([^"]+)" BINARY$',cue.read_text(),re.M)
        if len(names)!=3: raise ValueError('Expected three CUE tracks')
        for name in names:
            if f'(Disc {disc})' not in name or not (cue.parent/name).is_file():
                raise ValueError('Wrong/missing per-disc track')


def validate_payloads(track):
    system,_=READER.read_file(track,'SYSTEM.DAT')
    exe,_=READER.read_file(track,'1ST_READ.BIN')
    if timing.sha(system)!=SYSTEM_SHA or timing.sha(exe)!=EXE_SHA:
        raise ValueError('Latest artwork/code is missing')
    decoded=artwork.master.pvr_atlas.decode_scl(system,artwork.master.OFFSET)
    native,_=artwork.native_image()
    if decoded.tobytes()!=artwork.quantized(native).tobytes():
        raise ValueError('Choose your master screen differs from selected artwork')
    return exe


def build():
    if OUT.exists(): raise ValueError('Preserve previous combined pair')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3: raise ValueError('Insufficient space')
    previous=json.loads((SOURCE/'manifest.json').read_text())
    if previous['status']!=artwork.STATUS: raise ValueError('Unknown ImageGen source')
    verify_files(SOURCE,previous['files']);cue_checks(SOURCE)
    trial=timing.OUT/'disc1'/control.TRACK
    movie=(timing.OUT/'PROLOGUE.SFD').read_bytes()
    if control.digest(trial)!=TRIAL_TRACK_SHA or timing.sha(movie)!=MOVIE_SHA:
        raise ValueError('Successful timing trial changed')
    checked=json.loads((timing.OUT/'media-verification.json').read_text())
    if checked['status']!='passed' or checked['sha256']!=MOVIE_SHA:
        raise ValueError('Timing media verification missing/stale')
    source=SOURCE/'disc1'/control.TRACK
    exe=validate_payloads(source)
    before,lba=READER.read_file(source,'PROLOGUE.SFD')
    actual,trial_lba=READER.read_file(trial,'PROLOGUE.SFD')
    if timing.sha(before)!=control.ENGLISH_SHA or actual!=movie or trial_lba!=lba or len(before)!=len(movie):
        raise ValueError('Movie extent/payload mismatch')
    plan=dict(first_sector=lba-45000,sector_count=len(movie)//2048)
    expected={r['path']:r for r in previous['files']};files=[]
    OUT.mkdir();(OUT/'disc1').mkdir();(OUT/'disc2').mkdir()
    target=OUT/'disc1'/control.TRACK
    h=hashlib.sha256();old_h=hashlib.sha256();sector=0
    with source.open('rb') as src,trial.open('rb') as patch,target.open('xb') as dst:
        while raw:=src.read(2352*4096):
            after=control.overlay(raw,sector,patch,plan)
            dst.write(after);h.update(after);old_h.update(raw);sector+=len(raw)//2352
    key=target.relative_to(OUT).as_posix()
    if old_h.hexdigest()!=expected[key]['sha256']: raise ValueError('Source changed during copy')
    # Re-read the entire track. This also authenticates the precise raw allowlist.
    sector=0
    with source.open('rb') as src,trial.open('rb') as patch,target.open('rb') as dst:
        while raw:=src.read(2352*4096):
            if dst.read(len(raw))!=control.overlay(raw,sector,patch,plan):
                raise ValueError('Raw track readback differs')
            sector+=len(raw)//2352
    files.append(dict(path=key,bytes=target.stat().st_size,sha256=h.hexdigest()))
    with source.open('rb') as f:
        directory=list(READER.inject.iso_files(f));boot=READER.inject._extent(f,45000,32768)
    with target.open('rb') as f:
        if list(READER.inject.iso_files(f))!=directory or READER.inject._extent(f,45000,32768)!=boot:
            raise ValueError('Boot/directory changed')
    for name,_,_ in directory:
        old,_=READER.read_file(source,name);new,_=READER.read_file(target,name)
        if new!=(movie if name=='PROLOGUE.SFD' else old): raise ValueError('Unexpected ISO change: '+name)
    validate_payloads(target)
    for row in previous['files']:
        if row['path']==key: continue
        src=SOURCE/row['path'];dst=OUT/row['path']
        with src.open('rb') as a,dst.open('xb') as b:shutil.copyfileobj(a,b,4*1024*1024)
        files.append(dict(row))
    verify_files(OUT,files);cue_checks(OUT)
    verify_files(SOURCE,previous['files'])
    if control.digest(trial)!=TRIAL_TRACK_SHA: raise ValueError('Successful timing disc changed')
    (OUT/'1ST_READ.BIN').write_bytes(exe)
    preview='choose-your-master-preview.png';shutil.copy2(SOURCE/preview,OUT/preview)
    if control.digest(SOURCE/preview)!=control.digest(OUT/preview): raise ValueError('Preview copy mismatch')
    report=dict(status=STATUS,files=files,discs=[dict(disc=d,executable_sha256=EXE_SHA) for d in (1,2)],
        artwork=previous['artwork'],prologue_sha256=MOVIE_SHA,source=str(SOURCE),
        source_files=previous['files'],timing_trial_track_sha256=TRIAL_TRACK_SHA,
        prologue_timing_trial_user_report='it work',
        combined_build_runtime_verified=False,combined_vga_movie_playback_verified=False,
        original_imagegen_system_and_vga_latin_name_entry_executable_preserved=True,
        only_disc1_prologue_and_associated_raw_sector_parity_changed=True,
        disc2_exact_source_copy=True,previous_builds_unchanged=True,private_local_only=True)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'Black Matrix AD.m3u').write_text(''.join(f'disc{d}/Black-Matrix Advanced (Japan) (Disc {d}).cue\n' for d in (1,2)))
    (OUT/'README.txt').write_text('PRIVATE complete combined English disc pair.\n'
        'Disc 1 includes the selected ImageGen Choose your master screen AND the user-confirmed prologue timing repair.\n'
        'Existing VGA buffer, English name controls, Latin default and font fixes are preserved.\n'
        'Disc 2 is byte-identical to the earlier ImageGen pair. No other movies changed.\n'
        'Use the CUE/M3U here or Play - Disc 1 - Combined English VGA.cmd in the project.\n'
        'Older test launchers still open their older diagnostic discs.\n'
        'Combined new-game/VGA playback, disc swap and hardware tests remain pending.\n'
        'All prior builds, original images, normal emulator and saves are unchanged. Do not upload complete discs.\n')
    runner.prepare(OUT,STATUS)
    print('New combined private pair verified:',OUT,flush=True)


def launch():
    runner.prepare(OUT,STATUS)
    runner.profile.launch(OUT/'play',OUT/'disc1/Black-Matrix Advanced (Japan) (Disc 1).cue',OUT/'1ST_READ.BIN',
        instructions='Combined English VGA build: choose New Game. The prologue timing fix and new Choose your master artwork are both included.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--launch',action='store_true');a=p.parse_args()
    if a.build:build()
    if a.launch:launch()
