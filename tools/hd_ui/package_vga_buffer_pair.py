"""Private local corrected pair; no originals, previous deliveries or apps edited."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import buddy_vga_buffer as fix
import mode1_sector

ROOT=fix.ROOT
OUT=Path('M:/Black Matrix AD - Patched Discs - 2026-11-02')
DISC2=ROOT/'build/skies-vga-compat-v13-sampling/disc2'
DISC2_SHA='ca993fae518de922b52757d0bf5f709968a74db94b84bb707595c6affe97eb58'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(4*1024*1024):h.update(chunk)
    return h.hexdigest()


def run():
    if OUT.exists():raise ValueError('Preserve previous pair')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient pair space')
    master=json.loads((fix.OUT/'manifest.json').read_text())
    runtime=json.loads((fix.OUT/'buddy-runtime-verification.json').read_text())
    if (not runtime['user_confirmed_buddy_selection_works'] or runtime['fb']!=[640,480] or
        runtime['budgets']!=[320000,192000] or runtime['bios_vector']!='0x8c001000' or
        runtime['executable_sha256']!=master['executable_sha256']):
        raise ValueError('Candidate runtime evidence does not match')
    old_pair=json.loads((ROOT/'output/patched-discs-2026-11-01/manifest.json').read_text())
    originals=old_pair['original_track3_sha256']
    for name,sha in originals.items():
        if Path(name).name!=name or digest(ROOT/name)!=sha:raise ValueError('Original image changed')
    OUT.mkdir();files=[]
    # Disc1 is the exact master used in the successful user test.
    one=OUT/'disc1';one.mkdir()
    for p in (fix.OUT/'disc1').iterdir():
        if not p.is_file():continue
        sha=digest(p)
        if '(Track 3)' in p.name and sha!=master['track_sha256']:raise ValueError('Disc1 master changed')
        target=one/p.name
        with p.open('rb') as inp,target.open('xb') as dest:shutil.copyfileobj(inp,dest,4*1024*1024)
        if digest(target)!=sha:raise ValueError('Disc1 copy mismatch')
        files.append(dict(path=target.relative_to(OUT).as_posix(),bytes=target.stat().st_size,sha256=sha))
    print('Packaged verified Disc1 runtime master.',flush=True)
    # Disc2 retains every disc-specific file and archive from its own v13 master.
    prior=fix.legacy.footer.prior
    track=DISC2/'Black-Matrix Advanced (Japan) (Disc 2) (Track 3).bin'
    exe,lba=prior.read_file(track,'1ST_READ.BIN')
    guard=(ROOT/'build/skies-v13-sampling-verified-20261101/ram.bin').read_bytes()
    after,delta,spans=fix.patch(exe,[guard])
    if hashlib.sha256(after).hexdigest()!=master['executable_sha256']:
        raise ValueError('Shared executable differs between discs')
    changes,touched=fix.legacy.sectors.sector_changes(track,lba,after,delta)
    two=OUT/'disc2';two.mkdir();target=two/track.name
    sha=prior.copy_track(track,target,DISC2_SHA,changes)
    with track.open('rb') as f:
        directory=list(prior.inject.iso_files(f));boot=prior.inject._extent(f,45000,32768)
    with target.open('rb') as f:
        if list(prior.inject.iso_files(f))!=directory or prior.inject._extent(f,45000,32768)!=boot:
            raise ValueError('Disc2 boot/directory changed')
        for sector in touched:
            f.seek(sector*2352);raw=f.read(2352)
            if mode1_sector.regenerate(raw)!=raw:raise ValueError('Disc2 parity error')
    for name,_,_ in directory:
        before,_=prior.read_file(track,name);actual,_=prior.read_file(target,name)
        if actual!=(after if name=='1ST_READ.BIN' else before):raise ValueError('Disc2 payload changed: '+name)
    files.append(dict(path=target.relative_to(OUT).as_posix(),bytes=target.stat().st_size,sha256=sha))
    for p in DISC2.iterdir():
        if p.is_file() and p!=track:
            shutil.copy2(p,two/p.name)
            h=digest(p)
            if digest(two/p.name)!=h:raise ValueError('Disc2 companion mismatch')
            files.append(dict(path=(two/p.name).relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=h))
    print('Built and independently readback-verified Disc2.',flush=True)
    cues=[]
    for disc in (1,2):
        cue=OUT/f'disc{disc}/Black-Matrix Advanced (Japan) (Disc {disc}).cue'
        names=re.findall(r'^FILE "([^"]+)" BINARY$',cue.read_text(),re.M)
        if len(names)!=3 or any(not (cue.parent/n).is_file() for n in names):raise ValueError('Incomplete CUE')
        cues.append(cue.relative_to(OUT).as_posix())
    for row in files:
        if digest(OUT/row['path'])!=row['sha256']:raise ValueError('Final pair hash mismatch')
    for name,h in originals.items():
        if digest(ROOT/name)!=h:raise ValueError('Original changed during pair build')
    if digest(track)!=DISC2_SHA:raise ValueError('Disc2 source changed')
    report=dict(status='verified-private-vga-buffer-disc-pair',discs_completed=[1,2],
        files=sorted(files,key=lambda row:row['path']),original_track3_sha256=originals,
        originals_and_previous_deliveries_unchanged=True,private_local_only=True,published=False,
        executable_sha256=master['executable_sha256'],changed_executable_bytes=35,
        disc2_source_track_sha256=DISC2_SHA,disc2_parity_repaired_sectors=touched,
        disc1_user_confirmed_buddy_selection_in_vga=True,disc2_updated_build_gameplay_verified=False,
        disc_swap_verified=False,physical_hardware_verified=False,
        vga_budgets_doubled_by_native_allocator=True,tv_budgets_unchanged=True,
        font_geometry_translation_and_video_timing_unchanged=True,
        user_emulator_and_saves_unchanged=True,
        inherited_known_original_bitmap_retained=old_pair.get('known_original_bitmap_retained'))
    with (OUT/'manifest.json').open('x') as f:json.dump(report,f,indent=2)
    with (OUT/'SHA256SUMS').open('x',encoding='utf-8') as f:
        f.write(''.join(row['sha256']+'  '+row['path']+'\n' for row in report['files']))
    with (OUT/'Black Matrix AD.m3u').open('x',encoding='utf-8') as f:f.write('\n'.join(cues)+'\n')
    for inp,name in [(fix.OUT/'manifest.json','disc1-build-manifest.json'),
                     (fix.OUT/'buddy-runtime-verification.json','disc1-buddy-verification.json')]:
        shutil.copy2(inp,OUT/name)
    readme='''# Private patched Black/Matrix AD disc pair — 2026-11-02

Open Black Matrix AD.m3u, or the .cue inside the desired disc folder.
Keep every .bin beside its matching .cue. These complete game images are LOCAL
ONLY; do not upload, publish or distribute this folder.

VGA crash correction: use the existing native allocator to double the drawing
packet budgets only for VGA. Fonts, translations, layout and video timing are
unchanged. Non-VGA retains its original budgets. No emulator or saves included.

Disc1 cold-boots in VGA; user confirmed buddy selection now works. Captured
RAM confirms the corrected executable/budgets and intact BIOS vector.
Disc2 has the identical shared correction, with complete per-disc payload,
sector and checksum verification. The updated Disc2 has NOT yet had a fresh
gameplay/disc-swap test. Physical Dreamcast hardware is not verified.

Existing translation-coverage limitations are inherited, including the original
Japanese master-selection background prompt; this fix does not translate art.
Original discs and the previous delivery were preserved. See manifest.json and
SHA256SUMS for exact identities. This is not a public patch release.
'''
    with (OUT/'README.md').open('x',encoding='utf-8') as f:f.write(readme)
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2),flush=True)
    print('Private corrected pair:',OUT,flush=True)


if __name__=='__main__':run()
