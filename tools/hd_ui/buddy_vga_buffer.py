"""Private VGA packet-budget candidate; keep rendering/timing/font unchanged.

The native SDK setup receives opaque/translucent packet budgets160000/96000.
VGA expands tiled backgrounds from240 to480 lines, but those budgets stayed
unchanged. Tail-call the SAME native allocator with doubled budgets ONLY for
the VGA cable. The allocator owns/reserves the larger buffers inside its
existing8MB arena; this does not move a pointer into unallocated memory.

This is a candidate, not a runtime/hardware-verification claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import numpy as np
import buddy_native_fallback as legacy
import sh4asm
import mode1_sector

ROOT=legacy.ROOT
BASE=0x8c010000
HELPER=0x8c0f4890
END=0x8c0f4900
CALL_POINTER=0x284
ALLOCATOR=0x8c0a3032
OPAQUE=160000
TRANSLUCENT=96000
SOURCE=ROOT/'build/disc1-reconstructed-vga-v1/disc1'
OUT=Path('M:/Black-Matrix-AD-private-tests/disc1-vga-buffer-v1')
EXE_SHA=legacy.EXE_SHA
SOURCE_SHA=legacy.SHA


def helper():
    a=sh4asm.Asm(HELPER)
    a.long_('gpio',0xff800030);a.long_('native',ALLOCATOR)
    a.mov_l_pc('gpio',0);a.mov_w_at(0,0)
    for _ in range(4):a._w(0x4009)
    a._w(0xc903);a.tst(0,0);a.bf('call_native')
    a.shll(4);a.shll(6)
    a.label('call_native');a.mov_l_pc('native',0);a.jmp(0);a.nop()
    data=a.assemble()
    if HELPER+len(data)>END:raise ValueError('Allocator hook exceeds guarded cable-helper tail')
    return data


def patch(exe,captures):
    if hashlib.sha256(exe).hexdigest()!=EXE_SHA:raise ValueError('Unknown v13 executable')
    if struct.unpack_from('<III',exe,0x27c)!=(TRANSLUCENT,OPAQUE,ALLOCATOR):
        raise ValueError('Original packet budgets/call changed')
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    lo,hi=HELPER-BASE,END-BASE
    if any(exe[lo:hi]) or any(original[lo:hi]):raise ValueError('Hook tail occupied')
    for ram in captures:
        if len(ram)!=16777216 or ram[0x10000:0x11000]!=exe[:4096]:
            raise ValueError('Unauthenticated live reservation guard')
        if any(ram[HELPER-0x8c000000:END-0x8c000000]):raise ValueError('Live hook tail occupied')
    result=bytearray(exe)
    struct.pack_into('<I',result,CALL_POINTER,HELPER)
    result[lo:lo+len(helper())]=helper()
    spans=[(CALL_POINTER,CALL_POINTER+4),(lo,lo+len(helper()))]
    delta=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if any(not any(a<=i<z for a,z in spans) for i in delta):raise ValueError('Unrelated executable change')
    return bytes(result),delta,spans


def build():
    if OUT.exists():raise ValueError('Preserve existing candidate')
    if shutil.disk_usage(OUT.anchor).free<2*1024**3:raise ValueError('Insufficient candidate space')
    track=SOURCE/'Black-Matrix Advanced (Japan) (Disc 1) (Track 3).bin'
    prior=legacy.footer.prior
    exe,lba=prior.read_file(track,'1ST_READ.BIN')
    guards=[ROOT/'build/disc1-buddy-diagnostic-v1/buddy-20261101-222702-01-ram.bin',
            Path('M:/Black-Matrix-AD-private-tests/buddy-tv-20261102/user-success-ram.bin')]
    after,delta,spans=patch(exe,[p.read_bytes() for p in guards])
    changes,touched=legacy.sectors.sector_changes(track,lba,after,delta)
    OUT.mkdir();folder=OUT/'disc1';folder.mkdir();target=folder/track.name
    print('Building isolated VGA packet-budget candidate; delivered discs unchanged.',flush=True)
    digest=prior.copy_track(track,target,SOURCE_SHA,changes)
    with track.open('rb') as f:
        directory=list(prior.inject.iso_files(f));boot=prior.inject._extent(f,45000,32768)
    with target.open('rb') as f:
        if list(prior.inject.iso_files(f))!=directory or prior.inject._extent(f,45000,32768)!=boot:
            raise ValueError('Boot or directory changed')
        for sector in touched:
            f.seek(sector*2352);raw=f.read(2352)
            if mode1_sector.regenerate(raw)!=raw:raise ValueError('Sector parity invalid')
    print('Verifying every game payload and unchanged companion.',flush=True)
    for name,_,_ in directory:
        old,_=prior.read_file(track,name);new,_=prior.read_file(target,name)
        if new!=(after if name=='1ST_READ.BIN' else old):raise ValueError('Unexpected payload: '+name)
    for p in SOURCE.iterdir():
        if p.is_file() and p!=track:
            shutil.copy2(p,folder/p.name)
            if p.read_bytes()!=(folder/p.name).read_bytes():raise ValueError('Companion changed')
    report=dict(status='sector-verified-runtime-pending',disc=1,source_track_sha256=SOURCE_SHA,
        track_sha256=digest,executable_sha256=hashlib.sha256(after).hexdigest(),
        changed_executable_bytes=len(delta),allowed_spans=spans,helper_bytes=len(helper()),
        parity_repaired_sectors=touched,opaque_budget=dict(native=OPAQUE,vga=OPAQUE*2),
        translucent_budget=dict(native=TRANSLUCENT,vga=TRANSLUCENT*2),
        native_allocator_and_arena_retained=True,framebuffer_and_geometry_unchanged=True,
        all_fonts_and_other_game_payloads_unchanged=True,native_footer_candidate_not_included=True,
        original_and_delivered_discs_unchanged=True,private_local_only=True,
        buddy_runtime_verified=False,physical_hardware_verified=False,
        reservation_guard_captures=[str(p) for p in guards])
    (OUT/'1ST_READ.BIN').write_bytes(after)
    with (OUT/'manifest.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');args=p.parse_args()
    if args.build:build()
    else:print('VGA allocator helper bytes:',len(helper()))
