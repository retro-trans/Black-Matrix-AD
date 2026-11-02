"""Private cumulative W/Whip badge and live-font Remove caption.

Default is an authenticated dry-run. No emulator, profile or save writes.
"""
import argparse
import json
import shutil
import struct

import numpy as np
from PIL import Image,ImageDraw

import story_movie_safe_build as prior
import footer_remaining_font as captions
import skies_vga_sampling as sampling
import pvr_atlas
import mode1_sector
import japanese_audit

ROOT = prior.ROOT
b = prior.b
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-whip-remove-2026-11-02'
STATUS = 'private-whip-remove-font-runtime-pending'
VERSION = '0.1.3'
EXE_SHA = prior.EXE_SHA
TRACK_HASHES = {1:'76ca6c1ae1f22c49167a0cf33afb79c0722ed727839a32d1cc4cd2750bace803',
                2:'37b43ee3d5e682c971c64647deb67c4371013f40e21c4fc2c3776fb2c9247a6e'}
SYSTEM_HASHES = {1:'c1169b4dac101dbb312bc253d7e4887294bafc60ebd22878806ee370e4ca2cc5',
                 2:'72e8e370ceb5294fa3aa3175e363d0ec96807b645d3d8804984d181ac45b8e83'}
ASSET = ROOT/'assets/ui/weapon-badges/whip-w-imagegen-v1.png'
ASSET_SHA = '4be8e0f0432ff85974b2468a46506e30f65d2837ab8557c2eff7375a76ad2f75'
CAPTURE = ROOT/'build/choice-selector-inspection-2026-11-02/ram-25308-1793598874612810900.bin'
CAPTURE_SHA = '79b1670fa875e5e64cc554f2c205fcedcdfae8b6223cd9e1b7e01a7d1bb8f01e'
TEXTURE = 0x21890
WHIP_RECT = (64,16,80,32)
REMOVE_RECT = (64,208,112,224)
# 64 authenticated zero bytes inside the EXISTING UV code reservation.
# The complete current UV helper ends at30b8; no code moves or grows.
TABLE = 0x8c0f30c0
TABLE_END = 0x8c0f3100
f = captions.footer
BASE = captions.BASE


def remove_row():
    ids = bytes(f.prior.latin.charmap()[c] for c in 'Remove')
    return bytes([68])+ids+bytes(7-len(ids))+struct.pack('<4H',*REMOVE_RECT)


def patch_exe(before):
    if b.sha(before)!=EXE_SHA:raise ValueError('Unknown cumulative executable')
    original = (ROOT/'extracted/1ST_READ.BIN').read_bytes()
    ram = CAPTURE.read_bytes()
    if b.sha(ram)!=CAPTURE_SHA:raise ValueError('Unknown read-only capture')
    old = f.main(extra_table=captions.EXTRA)
    new = f.main(extra_table=TABLE,extra_count=4)
    table = b''.join(captions.row(i) for i in (54,56,69))+remove_row()
    uv = sampling.uv_hook()
    uv_lo = sampling.item.geometry.full.UV-BASE
    if before[uv_lo:uv_lo+len(uv)]!=uv or sampling.item.geometry.full.UV+len(uv)>TABLE:
        raise ValueError('Current sampling helper overlaps caption table')
    if len(new)!=len(old) or len(table)!=TABLE_END-TABLE or TABLE%16:
        raise ValueError('Caption code/table overflow or misalignment')
    after = bytearray(before);allowed = set()
    for address,expected,replacement in ((f.MAIN,old,new),(TABLE,bytes(64),table)):
        lo=address-BASE;hi=lo+len(expected)
        if before[lo:hi]!=expected or any(original[lo:hi]):
            raise ValueError('Unknown/occupied original reservation')
        if ram[address-0x8c000000:address-0x8c000000+len(expected)]!=expected:
            raise ValueError('Live reservation differs')
        after[lo:hi]=replacement;allowed.update(range(lo,hi))
    delta = np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(after,'u1')).tolist()
    if not delta or not set(delta)<=allowed or len(before)!=len(after):
        raise ValueError('Out-of-caption executable change')
    return bytes(after),delta


def whip_art():
    if b.sha(ASSET.read_bytes())!=ASSET_SHA:raise ValueError('Changed ImageGen badge')
    with Image.open(ASSET) as image:
        image=image.convert('RGBA')
        alpha=image.getchannel('A')
        box=alpha.point(lambda v:255 if v>=128 else 0).getbbox()
        if box!=(462,233,1313,657):raise ValueError('Unexpected generated badge bounds')
        # Format conversion only: preserve the generated silhouette/alpha,
        # fit the same14x7 native ink footprint as adjacent weapon initials.
        mask=alpha.crop(box).resize((14,7),Image.Resampling.LANCZOS)
        native=Image.new('RGBA',(16,16),(240,168,66,0))
        channel=Image.new('L',(16,16));channel.paste(mask,(1,4));native.putalpha(channel)
        return native


def patch_system(before,disc):
    if disc not in SYSTEM_HASHES or b.sha(before)!=SYSTEM_HASHES[disc]:
        raise ValueError('Unknown per-disc SYSTEM')
    rows=captions.native.pack.descriptors(before,TEXTURE)
    if rows[10]!=WHIP_RECT or rows[68]!=REMOVE_RECT:
        raise ValueError('Badge/Remove descriptors changed')
    original=japanese_audit.archive(disc,'SYSTEM.DAT')
    page=pvr_atlas.decode(before,TEXTURE)
    if page.crop(WHIP_RECT).tobytes()!=pvr_atlas.decode(original,TEXTURE).crop(WHIP_RECT).tobytes():
        raise ValueError('Badge is not the original Japanese sprite')
    after=bytearray(before);allowed=set()
    for offset,word in captions.native.encode(before,TEXTURE,WHIP_RECT,whip_art()):
        after[offset:offset+2]=word;allowed.update((offset,offset+1))
    delta=np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(after,'u1')).tolist()
    if not delta or not set(delta)<=allowed or len(before)!=len(after):
        raise ValueError('Out-of-badge change')
    return bytes(after),delta


def preview(before,after,exe):
    sheet=Image.new('RGB',(640,300),'#10100a');d=ImageDraw.Draw(sheet)
    d.text((12,8),'Offline packed badge + exact live-font masks (not an in-game capture)',fill='white')
    for col,(data,title) in enumerate(((before,'Before: Japanese'),(after,'After: W = Whip'))):
        tile=pvr_atlas.decode(data,TEXTURE).crop(WHIP_RECT).resize((128,256),Image.Resampling.NEAREST)
        sheet.paste(tile,(12+col*170,34),tile);d.text((12+col*170,20),title,fill='white')
    glyphs=prior.prior.current_font()[1]
    for row,text in enumerate(('Remove','Equip','Magic','Exit')):
        mask,_=prior.prior.prior.font.logical_line(text,glyphs,exe)
        art=Image.new('RGBA',mask.size,(255,184,40,0));art.putalpha(mask)
        sheet.paste(art,(352,42+row*58),art)
    return sheet


def plan():
    exe=(SOURCE/'1ST_READ.BIN').read_bytes();patched,delta=patch_exe(exe)
    reports=[]
    for disc in (1,2):
        before,_=b.READER.read_file(b.track(SOURCE,disc),'SYSTEM.DAT')
        after,sd=patch_system(before,disc)
        reports.append(dict(disc=disc,system_sha256=b.sha(after),changed_system_bytes=len(sd)))
    result=dict(status='planned-whip-remove',build_version=VERSION,
        executable_sha256=b.sha(patched),changed_executable_bytes=len(delta),discs=reports,
        caption='Remove',weapon_badge='W = Whip',secondary_table=hex(TABLE),
        caption_count=14,new_nodes_textures_or_allocator_units=0,
        source=str(SOURCE),output=str(OUT),gameplay_verified=False)
    print(json.dumps(result,indent=2),flush=True)
    return result


def build():
    plan()  # Complete authenticated plan before creating output.
    if OUT.exists():raise ValueError('Preserve previous output')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient E: space')
    previous=json.loads((SOURCE/'manifest.json').read_text())
    if previous['status']!=prior.STATUS or previous['executable_sha256']!=EXE_SHA:
        raise ValueError('Unknown cumulative source manifest')
    b.domina.zero.combined.verify_files(SOURCE,previous['files'])
    b.domina.zero.combined.cue_checks(SOURCE)
    exe,ed=patch_exe((SOURCE/'1ST_READ.BIN').read_bytes())
    OUT.mkdir();files=[];reports=[]
    for disc in (1,2):
        source,target=b.track(SOURCE,disc),b.track(OUT,disc);target.parent.mkdir()
        row=next(r for r in previous['files'] if r['path']==source.relative_to(SOURCE).as_posix())
        if row['sha256']!=TRACK_HASHES[disc]:raise ValueError('Wrong disc identity')
        system,lba=b.READER.read_file(source,'SYSTEM.DAT');after,sd=patch_system(system,disc)
        oldexe,elba=b.READER.read_file(source,'1ST_READ.BIN')
        if b.sha(oldexe)!=EXE_SHA:raise ValueError('Disc-specific executable differs')
        changes={};touched=set()
        for addr,payload,delta in ((lba,after,sd),(elba,exe,ed)):
            pending,sectors=b.domina.zero.names.budget.legacy.sectors.sector_changes(source,addr,payload,delta)
            if any(i in changes and changes[i]!=v for i,v in pending.items()):raise ValueError('Overlapping edits')
            changes.update(pending);touched.update(sectors)
        digest=b.READER.copy_track(source,target,TRACK_HASHES[disc],changes)
        with source.open('rb') as a,target.open('rb') as c:
            directory=list(b.READER.inject.iso_files(a))
            if directory!=list(b.READER.inject.iso_files(c)) or b.READER.inject._extent(a,45000,32768)!=b.READER.inject._extent(c,45000,32768):
                raise ValueError('Boot/directory changed')
            for sector in sorted(touched):
                c.seek(sector*2352);raw=c.read(2352)
                if mode1_sector.regenerate(raw)!=raw:raise ValueError('Invalid sector parity')
        for name,_,_ in directory:
            expected={'SYSTEM.DAT':after,'1ST_READ.BIN':exe}.get(name)
            if expected is None:expected=b.READER.read_file(source,name)[0]
            if b.READER.read_file(target,name)[0]!=expected:raise ValueError('Unexpected payload '+name)
        files.append(dict(path=target.relative_to(OUT).as_posix(),bytes=target.stat().st_size,sha256=digest))
        for row in previous['files']:
            if row['path'].startswith(f'disc{disc}/') and not row['path'].endswith('(Track 3).bin'):
                with (SOURCE/row['path']).open('rb') as a,(OUT/row['path']).open('xb') as c:shutil.copyfileobj(a,c,4*1024*1024)
                files.append(dict(row))
        reports.append(dict(disc=disc,track_sha256=digest,source_track_sha256=TRACK_HASHES[disc],
            system_sha256=b.sha(after),changed_system_bytes=len(sd),parity_sectors=sorted(touched)))
        if disc==1:preview(system,after,exe).save(OUT/'whip-remove-preview.png')
        print('Disc',disc,'full payload/sector verification passed.',flush=True)
    b.domina.zero.combined.verify_files(OUT,files);b.domina.zero.combined.cue_checks(OUT)
    b.domina.zero.combined.verify_files(SOURCE,previous['files'])
    (OUT/'1ST_READ.BIN').write_bytes(exe)
    for old in SOURCE.glob('*-preview.png'):shutil.copy2(old,OUT/old.name)
    (OUT/'Black Matrix AD.m3u').write_text(''.join(f'disc{d}/Black-Matrix Advanced (Japan) (Disc {d}).cue\n' for d in (1,2)))
    report=dict(status=STATUS,build_version=VERSION,source=str(SOURCE),source_files=previous['files'],files=files,
        discs=reports,source_executable_sha256=EXE_SHA,executable_sha256=b.sha(exe),
        changed_executable_bytes=len(ed),caption='Remove',weapon_badge='W = Whip',
        imagegen_asset=str(ASSET.relative_to(ROOT)),asset_sha256=ASSET_SHA,secondary_table=hex(TABLE),
        new_nodes_textures_or_allocator_units=0,all_other_iso_payloads_unchanged=True,
        movies_scripts_font_pixels_metrics_gameplay_and_prior_fixes_unchanged=True,
        saves_and_profile_configuration_unchanged=True,private_local_only=True,
        renderer_launch_only_settings=b.renderer_settings(),gameplay_verified=False,physical_hardware_verified=False)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(
        'PRIVATE cumulative0.1.3: W = Whip; Remove matches live Equip/Magic/Exit font.\n'
        'Only one native weapon badge and guarded footer code/table bytes change on both discs.\n'
        'ImageGen silhouette packed into original16x16 badge, original descriptors/icons retained.\n'
        'No new nodes/textures/allocations; existing thirteen captions and fallback guards retained.\n'
        'Working prologue, raised movie subtitles, English story artwork and all previous fixes retained.\n'
        'Use Play - Disc 2 - Whip and Remove.cmd (or Disc1) after closing Flycast.\n'
        'Same original E: VMUs; latest old saves Port A Slot2. No save/profile writes or automatic restart.\n'
        'Offline preview and full binary checks passed; fresh in-game appearance/hardware pending.\n'
        'Separate oversized Equip item-list and topic-list reports are not fixed by this build.\n'
        'Keep complete game binaries private/local. Originals and previous builds preserved.\n')
    print('New private cumulative pair:',OUT,flush=True)


def launch(disc):b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.build:build()
    elif a.launch:launch(a.launch)
    else:plan()
