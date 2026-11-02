"""Isolated candidate: perform native fallback after unwinding footer frame."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import numpy as np
import skies_vga_sharp_footer as footer
import skies_vga_sampling as sampling
import skies_attack_letters as sectors
import mode1_sector
import sh4asm

ROOT=footer.ROOT
BASE=0x8c010000
NATIVE=0x8c0f30b8
END=0x8c0f3100
OUT=ROOT/'build/disc1-buddy-native-fallback-v1'
SOURCE=ROOT/'build/disc1-reconstructed-vga-v1/disc1'
SHA='2f3b7ec03ac689cf728dd6d7f38b50acf84d37bf313899a5ea0641046cecf73e'
EXE_SHA='94606624f94c22b12b7bc5b48da513c222c19941722fbbae0511b2f1d7e20e8b'


def native():
    # Same native call order/arguments, with NO wrapper stack/nonvolatile changes.
    a=sh4asm.Asm(NATIVE)
    for name,address in [('bind',0x8c06c914),('blend',0x8c06c984),
        ('colour',0x8c06c9cc),('geometry',0x8c06cad0),('submit',0x8c0a53c8),('resume',footer.ENTRY_END)]:
        a.long_(name,address)
    for name in ('bind','blend'):
        a.mov_l_pc(name,2);a.jsr(2);a.mov(14,4)
    for name in ('colour','geometry'):
        a.mov(13,5);a.mov_l_pc(name,2);a.jsr(2);a.mov(14,4)
    a.mov_l_pc('submit',2);a.mov(14,4);a.mov_l_atd(44,14,6)
    a.mov_i(4,5);a._w(0xf4fc);a.jsr(2);a.add_i(68,4)
    a.mov_l_pc('resume',2);a.jmp(2);a.nop()
    code=a.assemble()
    if NATIVE+len(code)>END:raise ValueError('Native replay exceeds guarded UV tail')
    return code


def entry():
    a=sh4asm.Asm(footer.ENTRY)
    for name,address in [('helper',footer.MAIN),('native',NATIVE),('resume',footer.ENTRY_END)]:a.long_(name,address)
    a.mov_l_pc('helper',2);a.jsr(2);a.mov(14,4)
    a.mov_l_pc('native',2);a.tst(0,0);a.bt('jump')
    a.mov_l_pc('resume',2)
    a.label('jump');a.jmp(2);a.nop()
    code=a.assemble()
    if len(code)>footer.ENTRY_END-footer.ENTRY:raise ValueError('Entry overflow')
    return code+struct.pack('<H',9)*((footer.ENTRY_END-footer.ENTRY-len(code))//2)


def patch(exe,capture):
    if hashlib.sha256(exe).hexdigest()!=EXE_SHA:raise ValueError('Unknown v13 executable')
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    main=footer.main(defer_fallback=True)
    old=footer.main();lo=footer.MAIN-BASE;hi=footer.MAIN_END-BASE
    if exe[lo:lo+len(old)]!=old or any(exe[lo+len(old):hi]):raise ValueError('Unknown footer guard')
    if len(main)>hi-lo:raise ValueError('Main overflow')
    uv=sampling.uv_hook()
    if sampling.item.geometry.full.UV+len(uv)!=NATIVE:raise ValueError('UV boundary changed')
    lo_native=NATIVE-BASE;end_native=END-BASE
    if any(exe[lo_native:end_native]) or any(original[lo_native:end_native]) or any(capture[NATIVE-0x8c000000:END-0x8c000000]):
        raise ValueError('Native replay reservation occupied')
    a=bytearray(exe);a[lo:hi]=main+bytes(hi-lo-len(main))
    a[footer.ENTRY-BASE:footer.ENTRY_END-BASE]=entry()
    a[lo_native:lo_native+len(native())]=native()
    delta=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(a,dtype='u1')).tolist()
    spans=[(lo,hi),(footer.ENTRY-BASE,footer.ENTRY_END-BASE),(lo_native,end_native)]
    if any(not any(x<=i<y for x,y in spans) for i in delta):raise ValueError('Unrelated executable edit')
    return bytes(a),delta,spans


def build(resume=False):
    if OUT.exists() and not resume:raise ValueError('Preserve previous candidate')
    if (OUT/'manifest.json').exists():raise ValueError('Candidate is already finalized')
    source=SOURCE/'Black-Matrix Advanced (Japan) (Disc 1) (Track 3).bin'
    exe,lba=footer.prior.read_file(source,'1ST_READ.BIN')
    capture=(ROOT/'build/disc1-buddy-diagnostic-v1/buddy-20261101-223719-01-ram.bin').read_bytes()
    after,delta,spans=patch(exe,capture)
    changes,touched=sectors.sector_changes(source,lba,after,delta)
    OUT.mkdir(exist_ok=resume);folder=OUT/'disc1';folder.mkdir(exist_ok=resume)
    target=folder/source.name
    if resume:
        print('Independently rechecking complete candidate after companion-copy space failure.',flush=True)
        if target.stat().st_size!=source.stat().st_size:raise ValueError('Incomplete candidate track')
        h_source=hashlib.sha256();h_target=hashlib.sha256();position=0;found=set()
        with source.open('rb') as inp,target.open('rb') as dest:
            while old:=inp.read(4*1024*1024):
                new=dest.read(len(old));h_source.update(old);h_target.update(new)
                for i in np.flatnonzero(np.frombuffer(old,dtype='u1')!=np.frombuffer(new,dtype='u1')):
                    offset=position+int(i)
                    if changes.get(offset)!=new[i]:raise ValueError('Unexpected candidate sector edit')
                    found.add(offset)
                position+=len(old)
        if h_source.hexdigest()!=SHA or found!=set(changes):raise ValueError('Candidate/source verification failed')
        sha=h_target.hexdigest()
    else:
        print('Writing isolated native-fallback candidate; source and delivered discs preserved.',flush=True)
        sha=footer.prior.copy_track(source,target,SHA,changes)
    if footer.prior.read_file(folder/source.name,'1ST_READ.BIN')[0]!=after:raise ValueError('Executable readback failed')
    for path in SOURCE.iterdir():
        if path.is_file() and path.name!=source.name:
            dest=folder/path.name
            if dest.exists():
                if dest.read_bytes()!=path.read_bytes():raise ValueError('Existing companion differs')
            else:shutil.copy2(path,dest)
            if dest.read_bytes()!=path.read_bytes():raise ValueError('Companion copy failed')
    report=dict(status='sector-verified-candidate-runtime-pending',disc=1,track_sha256=sha,
        source_track_sha256=SHA,executable_sha256=hashlib.sha256(after).hexdigest(),
        native_replay_bytes=len(native()),main_bytes=len(footer.main(defer_fallback=True)),
        changed_executable_bytes=len(delta),allowed_spans=spans,parity_repaired_sectors=touched,
        all_other_raw_bytes_identical=True,original_and_delivered_discs_unchanged=True,
        footer_glyph_path_retained=True,physical_hardware_verified=False)
    (OUT/'1ST_READ.BIN').write_bytes(after)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--resume',action='store_true')
    args=p.parse_args()
    if args.build:build(args.resume)
    else:print('Native replay',len(native()),'entry',len(entry()),'guard',len(footer.main(defer_fallback=True)))
