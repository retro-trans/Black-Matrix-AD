"""Private0.1.12: add Join to the existing full-detail footer renderer."""
import argparse
import json
import shutil
import struct

import equip_font_build as prior
import equip_fallback_font as equip
import footer_remaining_font as captions

ROOT=prior.ROOT
b=prior.b
f=equip.footer
BASE=equip.BASE
SOURCE=prior.OUT
OUT=ROOT/'output/patched-discs-join-font-2026-11-02'
VERSION='0.1.12'
STATUS='private-join-font-runtime-pending'
ROW,ROW_END=0x8c0f24f0,0x8c0f2500
INDEX,RECT=67,(64,192,96,208)
EXE_HASHES={1:'36a0406e62480bbfd4055242d4080f0458261514a142f5eabf0de2a9824e349d',
            2:'3fae78887206bb798e856339c368b8fd6a86d53e4ff1b7918877dfd74307a147'}
save=prior.save


def row():
    gids=bytes(f.prior.latin.charmap()[c] for c in 'Join')
    return bytes([INDEX])+gids+bytes(7-len(gids))+struct.pack('<4H',*RECT)


def main():return f.main(extra_table=0x8c0f30c0,extra_count=4,equip_gate=equip.GATE,single_caption=(INDEX,ROW))


def patch_exe(before,disc):
    if disc not in EXE_HASHES or b.sha(before)!=EXE_HASHES[disc]:raise ValueError('Unknown0.1.11 executable')
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes();ram=equip.CAPTURE.read_bytes()
    if b.sha(ram)!=equip.CAPTURE_SHA:raise ValueError('Unknown read-only padding capture')
    old=f.main(extra_table=0x8c0f30c0,extra_count=4,equip_gate=equip.GATE);new=main()
    if len(new)>f.MAIN_END-f.MAIN or ROW%16 or len(row())!=ROW_END-ROW:
        raise ValueError('Join code/table overflow')
    if equip.PEN+len(equip.pen())>ROW:raise ValueError('Join table overlaps Equip helper')
    result=bytearray(before);allowed=set()
    for addr,expected,payload in ((f.MAIN,old+bytes(len(new)-len(old)),new),(ROW,bytes(16),row())):
        lo=addr-BASE;hi=lo+len(expected)
        if before[lo:hi]!=expected or any(original[lo:hi]):raise ValueError(f'Unknown/occupied reservation {addr:x}')
        if addr==ROW and any(ram[addr-0x8c000000:ROW_END-0x8c000000]):raise ValueError('Captured Join padding occupied')
        result[lo:hi]=payload;allowed.update(range(lo,hi))
    delta=[i for i,(a,c) in enumerate(zip(before,result)) if a!=c]
    if not delta or not set(delta)<=allowed or len(before)!=len(result):raise ValueError('Out-of-scope Join edit')
    return bytes(result),delta


def prepare():
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    if manifest['status']!=prior.STATUS or manifest['build_version']!='0.1.11':raise ValueError('Wrong cumulative source')
    exes={};deltas={}
    for disc in (1,2):
        before=b.READER.read_file(b.track(SOURCE,disc),'1ST_READ.BIN')[0]
        if before!=(SOURCE/('1ST_READ.disc1.BIN' if disc==1 else '1ST_READ.BIN')).read_bytes():raise ValueError('Loose EXE mismatch')
        system=b.READER.read_file(b.track(SOURCE,disc),'SYSTEM.DAT')[0]
        if captions.native.pack.descriptors(system,0x21890)[INDEX]!=RECT:raise ValueError('Join sprite UV changed')
        exes[disc],deltas[disc]=patch_exe(before,disc)
    report=dict(build_version=VERSION,status=STATUS,source=str(SOURCE),label='Join',sprite_index=INDEX,sprite_uv=RECT,
        source_disc_executable_sha256=EXE_HASHES,disc_executable_sha256={d:b.sha(x) for d,x in exes.items()},
        changed_executable_bytes={d:len(x) for d,x in deltas.items()},footer_helper_bytes=len(main()),row_address=hex(ROW),
        same_live_font_size_advances_baseline_uv_bias_and_gold_as_other_footers=True,
        existing_fourteen_footer_outputs_unchanged=True,equip_fix_retained=True,
        original_icon_position_and_action_unchanged=True,font_pixels_and_all_archives_unchanged=True,
        new_texture_allocations=0,native_fallback_and_live_donor_validation_retained=True,
        private_local_only=True,saves_profiles_and_emulator_untouched=True,
        gameplay_verified=False,physical_hardware_verified=False)
    return manifest,exes,report


def build():
    manifest,exes,report=prepare()
    if OUT.exists():raise ValueError('Preserve previous output')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient E: space')
    b.domina.zero.combined.verify_files(SOURCE,manifest['files']);b.domina.zero.combined.cue_checks(SOURCE)
    print('Authenticated0.1.12: Join caption only; all prior cumulative fixes retained.',flush=True)
    OUT.mkdir();files=[];touched={}
    for item in manifest['files']:
        src,dst=SOURCE/item['path'],OUT/item['path'];dst.parent.mkdir(exist_ok=True)
        disc=next((d for d in (1,2) if src==b.track(SOURCE,d)),None)
        if disc:
            _,lba=b.READER.read_file(src,'1ST_READ.BIN');data=exes[disc]
            digest,sectors=prior.prior.prior.prior.copy_track(src,dst,item['sha256'],[(lba-45000,data+bytes((-len(data))%2048))])
            touched[disc]=sectors;files.append(dict(path=item['path'],bytes=dst.stat().st_size,sha256=digest))
            print('Whole-track exact-change/parity readback verified Disc',disc,flush=True)
        else:
            shutil.copy2(src,dst);files.append(dict(item))
    for disc in (1,2):
        src,dst=b.track(SOURCE,disc),b.track(OUT,disc)
        with src.open('rb') as a,dst.open('rb') as c:
            directory=list(b.READER.inject.iso_files(a))
            if directory!=list(b.READER.inject.iso_files(c)) or b.READER.inject._extent(a,45000,32768)!=b.READER.inject._extent(c,45000,32768):raise ValueError('Boot/directory changed')
        for name,_,_ in directory:
            wanted=exes[disc] if name=='1ST_READ.BIN' else b.READER.read_file(src,name)[0]
            if b.READER.read_file(dst,name)[0]!=wanted:raise ValueError('Unexpected payload change '+name)
        print('All ISO payloads verified Disc',disc,flush=True)
    b.domina.zero.combined.verify_files(OUT,files);b.domina.zero.combined.cue_checks(OUT)
    for path in SOURCE.iterdir():
        if path.is_dir() and path.name not in ('disc1','disc2'):shutil.copytree(path,OUT/path.name)
        elif path.is_file() and path.name not in ('manifest.json','SHA256SUMS','README.txt','1ST_READ.BIN','1ST_READ.disc1.BIN'):shutil.copy2(path,OUT/path.name)
    (OUT/'1ST_READ.BIN').write_bytes(exes[2]);(OUT/'1ST_READ.disc1.BIN').write_bytes(exes[1])
    save(OUT/'join-font-verification.json',report)
    save(OUT/'manifest.json',dict(manifest,status=STATUS,build_version=VERSION,files=files,source=str(SOURCE),source_files=manifest['files'],
        executable_sha256=b.sha(exes[2]),disc_executable_sha256=report['disc_executable_sha256'],changed_raw_sectors=touched,join=report,
        unresolved=['Fresh Join caption gameplay/physical-hardware appearance remains pending.',*manifest.get('unresolved',[])]))
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(
        'PRIVATE local cumulative0.1.12 - Join footer font\n'
        'Join now uses the same full-detail live font, size, spacing, baseline, sampling and gold as Equip/Magic/Exit.\n'
        'Original A icon, caption anchor, actions and safe disabled/fade/no-donor fallback retained.\n'
        'No new texture allocation or image/font pixel changes. All prior fixes including Equip list and ending subtitles retained.\n'
        'Only guarded EXE code/table and sector parity change; all archives/audio/movies/scripts/art unchanged.\n'
        'Use Play - Disc 2 - Join Font Fix.cmd (or Disc1). Same original E: VMUs, latest old save PortA Slot2.\n'
        'No emulator launch/input/restart, save/card/profile changes, M: writes or original-disc modification.\n'
        'Offline verification complete; fresh gameplay/physical-hardware appearance pending.\n'
        'Complete binaries must remain private/local. No upload, publication, tag, release or public catalog edit.\n')
    print('Private0.1.12 Join font pair ready:',OUT,flush=True)


def launch(disc):b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.build:build()
    elif a.launch:launch(a.launch)
    else:print(json.dumps(prepare()[2],indent=2))
