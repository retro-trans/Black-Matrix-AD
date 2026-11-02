"""Private cumulative0.1.11: full-detail low-budget Equip list candidate."""
import argparse
import json
import shutil
from pathlib import Path

from PIL import Image,ImageDraw
import ending_subtitle_build as prior
import equip_fallback_font as fix

ROOT=prior.ROOT
b=prior.b
SOURCE=prior.OUT
OUT=ROOT/'output/patched-discs-equip-font-v2-2026-11-02'
VERSION='0.1.11'
STATUS='private-equip-font-runtime-pending'


def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n',encoding='ascii')


def prepare():
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    if manifest['status']!=prior.STATUS or manifest['build_version']!='0.1.9':raise ValueError('Unknown cumulative source')
    exes={}
    for disc in (1,2):
        data=b.READER.read_file(b.track(SOURCE,disc),'1ST_READ.BIN')[0]
        exes[disc],delta=fix.patch_exe(data,disc)
        loose=SOURCE/('1ST_READ.disc1.BIN' if disc==1 else '1ST_READ.BIN')
        if data!=loose.read_bytes():raise ValueError('Loose/embedded source mismatch')
    report=dict(build_version=VERSION,status=STATUS,source=str(SOURCE),
        source_disc_executable_sha256=fix.EXE_HASHES,
        disc_executable_sha256={d:b.sha(data) for d,data in exes.items()},
        changed_executable_bytes=len(delta),blocks={hex(a):len(p) for a,p in fix.blocks().items()},
        capture_sha256=fix.CAPTURE_SHA,exact_context=hex(fix.CONTEXT),grid=[8,5],pitch_flag=1,
        draw_only_font_borrowing=True,donor_revalidated_every_glyph=True,
        transient_stack_node=True,native_fallback_on_failed_guard=True,
        persistent_records_handles_nodes_and_allocators_unchanged=True,
        font_pool_ceiling=448,additional_texture_units=0,native_glyph_quad=[16,12],
        native_row_pitch=14,native_row_inset=2,disabled_tint_and_fades_preserved=True,
        canonical_font_pixels_and_sampling_unchanged=True,
        all_fourteen_existing_footer_packets_identical=True,
        only_executable_payload_and_sector_parity_change=True,
        saves_profiles_and_emulator_untouched=True,private_local_only=True,
        gameplay_verified=False,physical_hardware_verified=False)
    return manifest,exes,report


def preview(exe):
    """Packed-font row-fit projection, explicitly not an emulator screenshot."""
    f=fix.footer
    system=b.READER.read_file(b.track(SOURCE,2),'SYSTEM.DAT')[0]
    pages=[f.previous.ritual.full.decode_vq(system[f.prior.FONT_OFFSET+16+bank*128:
        f.prior.FONT_OFFSET+16+bank*128+8192]) for bank in f.previous.ritual.full.BANKS]
    image=Image.new('RGBA',(700,440),'#17120d');draw=ImageDraw.Draw(image)
    draw.text((14,10),'OFFLINE packed-font projection - fresh gameplay check pending',fill='white')
    draw.text((14,28),'Same font / 28px rows / existing disabled tint preserved',fill='#e9b84b')
    ram=fix.CAPTURE.read_bytes();rec=fix.vwf.LINE_RECORDS+7*400-0x8c000000
    words=[int.from_bytes(ram[rec+4+2*i:rec+6+2*i],'little') for i in range(40)]
    checks=[]
    for row in range(5):
        line=Image.new('RGBA',(320,28));pen=0
        for gid in words[row*8:row*8+8]:
            slot=exe[fix.atlas.FORWARD-fix.BASE+gid];sx=slot%8*16;sy=slot%32//8*32
            glyph=pages[slot//32].crop((sx,sy,sx+16,sy+24))
            line.alpha_composite(glyph,(pen,0));pen+=exe[fix.metrics.SMALL_ADV-fix.BASE+gid]
        box=line.getbbox();checks.append(dict(row=row,max_ink_y=box[3] if box else 0,row_pitch=28))
        if box and box[3]>24:raise ValueError('Equip row overflow')
        y=76+row*64
        draw.rectangle((14,y-4,670,y+54),outline='#ab741e')
        image.alpha_composite(line.resize((640,56),Image.Resampling.NEAREST),(22,y))
    image.convert('RGB').save(OUT/'equip-font-row-fit.png')
    save(OUT/'equip-font-layout-verification.json',dict(method='Actual decoded canonical pages and packed advances; no image synthesis',
        rows=checks,source_record=hex(fix.vwf.LINE_RECORDS+7*400),in_game_verified=False))


def build():
    manifest,exes,report=prepare()
    if OUT.exists():raise ValueError('Preserve existing candidate')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient E: space')
    b.domina.zero.combined.verify_files(SOURCE,manifest['files']);b.domina.zero.combined.cue_checks(SOURCE)
    print('Authenticated0.1.11: both discs change only guarded font code and raw parity.',flush=True)
    OUT.mkdir();files=[];touched={}
    for row in manifest['files']:
        source,target=SOURCE/row['path'],OUT/row['path'];target.parent.mkdir(exist_ok=True)
        disc=next((d for d in (1,2) if source==b.track(SOURCE,d)),None)
        if disc:
            old,lba=b.READER.read_file(source,'1ST_READ.BIN');data=exes[disc]
            plans=[(lba-45000,data+bytes((-len(data))%2048))]
            digest,sectors=prior.prior.prior.copy_track(source,target,row['sha256'],plans)
            touched[disc]=sectors;files.append(dict(path=row['path'],sha256=digest,bytes=target.stat().st_size))
            print('Exact whole-track readback/parity verified Disc',disc,flush=True)
        else:
            with source.open('rb') as a,target.open('xb') as c:shutil.copyfileobj(a,c,4*1024*1024)
            files.append(dict(row))
    for disc in (1,2):
        source,target=b.track(SOURCE,disc),b.track(OUT,disc)
        with source.open('rb') as a,target.open('rb') as c:
            directory=list(b.READER.inject.iso_files(a))
            if directory!=list(b.READER.inject.iso_files(c)) or b.READER.inject._extent(a,45000,32768)!=b.READER.inject._extent(c,45000,32768):
                raise ValueError('Boot/directory changed')
        for name,_,_ in directory:
            expected=exes[disc] if name=='1ST_READ.BIN' else b.READER.read_file(source,name)[0]
            if b.READER.read_file(target,name)[0]!=expected:raise ValueError('Unrelated ISO payload changed '+name)
        print('Every ISO payload verified Disc',disc,flush=True)
    b.domina.zero.combined.verify_files(OUT,files);b.domina.zero.combined.cue_checks(OUT)
    for path in SOURCE.iterdir():
        if path.is_dir() and path.name not in ('disc1','disc2'):shutil.copytree(path,OUT/path.name)
        elif path.is_file() and path.name not in ('manifest.json','SHA256SUMS','README.txt','1ST_READ.BIN','1ST_READ.disc1.BIN'):
            shutil.copy2(path,OUT/path.name)
    (OUT/'1ST_READ.BIN').write_bytes(exes[2]);(OUT/'1ST_READ.disc1.BIN').write_bytes(exes[1])
    preview(exes[2]);save(OUT/'equip-font-verification.json',report)
    result=dict(manifest,status=STATUS,build_version=VERSION,files=files,source=str(SOURCE),source_files=manifest['files'],
        executable_sha256=b.sha(exes[2]),disc_executable_sha256=report['disc_executable_sha256'],
        disc1_exact_source_copy=False,changed_raw_sectors=touched,equip=report,
        unresolved=['Fresh cold-launch Equip page/font appearance and physical hardware testing remain pending.',
            *[s for s in manifest.get('unresolved',[]) if 'Equip' not in s and 'item font' not in s.lower()]])
    save(OUT/'manifest.json',result)
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(
        'PRIVATE local cumulative0.1.11 - Equip font candidate\n'
        'Fixes the oversized low-budget Equip8x5 item list by borrowing a live full-detail font at each draw.\n'
        'Same approved font, sampling, row inset, small advances, disabled tint and fade.\n'
        'No new texture allocation or ownership, no larger pool, no altered admission policy.\n'
        'A transient stack node is used; the original text/node/handle/lifetime remains authoritative.\n'
        'Failed validation retains the existing native fallback safely.\n'
        'Both discs change only guarded executable code and sector parity; all archives/audio/movies unchanged.\n'
        'All0.1.9 changes, including Disc2 automatic post-credits subtitles, retained.\n'
        'Use Play - Disc 2 - Equip Font Fix.cmd (or Disc1 counterpart); same original E: VMUs.\n'
        'Offline code/packet/row-fit/disc verification passed. Fresh gameplay and hardware testing pending.\n'
        'No emulator input/launch, save/card/profile writes, M: output or original-disc modification.\n'
        'No upload, release, tag, publication or public catalog change. Full binaries must stay private/local.\n')
    print('Private0.1.11 pair ready:',OUT,flush=True)


def launch(disc):b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.build:build()
    elif a.launch:launch(a.launch)
    else:print(json.dumps(prepare()[2],indent=2))
