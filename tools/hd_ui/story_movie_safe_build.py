"""Private cumulative Disc2 story card + raised captions, Disc1 exact copy."""
import argparse
import hashlib
import json
import re
import shutil

import numpy as np
from PIL import Image,ImageOps
import movie_subtitle_safe_area as media
import pvr_atlas
import mode1_sector

prior = media.prior
b = prior.prior.builder
ROOT = prior.ROOT
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-story-subtitle-safe-2026-11-02'
STATUS = 'private-story-subtitle-safe-runtime-pending'
VERSION = '0.1.2'
EXE_SHA = prior.EXE_SHA
TRACK_HASHES = {1:'76ca6c1ae1f22c49167a0cf33afb79c0722ed727839a32d1cc4cd2750bace803',
                2:'29f2d5b655bfa50b36106003b6881a094aa89bfc760efae4e96fd134002ab995'}
ASSET = ROOT/'assets/ui/story-cards/why-father-imagegen-v1.png'
ASSET_SHA = '7ed5e871d317bd77daed0ef72eae7caea20976c3835a6dbfb1466ab3061a716d'
CARD = 0x6435800
CARD_SHA = '443399bfced6dd9a77b5a5c67683a0aac800c5535b8deb77cfce9cd3af13e04a'
TEXTS = ('Why?!','Why, Father?!')


def native_image():
    if media.sha(ASSET.read_bytes())!=ASSET_SHA:raise ValueError('Reviewed ImageGen asset changed')
    with Image.open(ASSET) as image:
        # Game-format conversion only: contain in4:3 black frame, then the
        # existing doubled-Y scanout restores original generated proportions.
        fitted = ImageOps.contain(image.convert('RGB'),(640,480),Image.Resampling.LANCZOS)
        frame = Image.new('RGB',(640,480),'black')
        frame.paste(fitted,((640-fitted.width)//2,(480-fitted.height)//2))
        return frame.resize((640,240),Image.Resampling.LANCZOS)


def patch_card(event):
    cols,rows,_,pages = pvr_atlas.scl_layout(event,CARD)
    end = pages[-1]+16+131072
    if (cols,rows,len(pages))!=(40,15,1) or media.sha(event[CARD:end])!=CARD_SHA:
        raise ValueError('Unknown original Japanese story card')
    for match in re.finditer(b'SCL ',event):
        if match.start()==CARD:continue
        try:other = pvr_atlas.scl_layout(event,match.start())[3]
        except (ValueError,IndexError):continue
        if set(other)&set(pages):raise ValueError('Story page shared by another card')
    after = bytearray(event);image = native_image()
    count = pvr_atlas.encode_scl(after,CARD,image)
    allowed = ((CARD+32,CARD+32+2400),*( (p+16,p+16+131072) for p in pages))
    last = 0
    for lo,hi in sorted(allowed):
        if event[last:lo]!=after[last:lo]:raise ValueError('Out-of-card/header edit')
        last=hi
    if event[last:]!=after[last:]:raise ValueError('Out-of-card edit')
    decoded = pvr_atlas.decode_scl(after,CARD)
    if decoded.tobytes()!=Image.fromarray(b.quantized(image)).tobytes():
        raise ValueError('Packed story card differs from reviewed image conversion')
    if count>256:raise ValueError('Story card exceeded original allocation')
    report = dict(offset=CARD,end=end,texts=TEXTS,tiles=count,capacity=256,
        source_leaf_sha256=CARD_SHA,leaf_sha256=media.sha(after[CARD:end]),
        asset=str(ASSET.relative_to(ROOT)),asset_sha256=ASSET_SHA,
        native_rgb_sha256=media.sha(decoded.tobytes()),all_other_bytes_and_headers_unchanged=True)
    return bytes(after),report,decoded


def overlay(raw,first,plans):
    if not raw or len(raw)%2352:raise ValueError('Expected complete raw sectors')
    before = np.frombuffer(raw,'u1').reshape(-1,2352)
    after = before.copy();last=first+len(after)
    for start,payload in plans:
        if start<0 or len(payload)%2048:raise ValueError('Invalid sector payload')
        plane = np.frombuffer(payload,'u1').reshape(-1,2048)
        lo,hi=max(first,start),min(last,start+len(plane))
        if lo<hi:after[lo-first:hi-first,16:2064]=plane[lo-start:hi-start]
    changed = np.any(after[:,16:2064]!=before[:,16:2064],axis=1)
    indices = np.flatnonzero(changed)
    if len(indices):
        after[indices] = np.frombuffer(mode1_sector.regenerate(after[indices].tobytes()),'u1').reshape(-1,2352)
    return after.tobytes(),[int(i+first) for i in indices]


def copy_track(source,target,expected,plans):
    intervals = sorted((s,s+len(p)//2048) for s,p in plans)
    if any(a[1]>c[0] for a,c in zip(intervals,intervals[1:])):
        raise ValueError('Overlapping replacement extents')
    if any(s<0 or end>source.stat().st_size//2352 for s,end in intervals):
        raise ValueError('Replacement outside disc')
    source_hash,target_hash=hashlib.sha256(),hashlib.sha256();first=0;touched=[]
    with source.open('rb') as src,target.open('xb') as dst:
        while raw:=src.read(4096*2352):
            after,changed = overlay(raw,first,plans)
            dst.write(after);source_hash.update(raw);target_hash.update(after)
            first+=len(raw)//2352;touched.extend(changed)
    if source_hash.hexdigest()!=expected:raise ValueError('Unknown source disc')
    first=0;readback=hashlib.sha256()
    with source.open('rb') as src,target.open('rb') as dst:
        while raw:=src.read(4096*2352):
            after=dst.read(len(raw));wanted,_=overlay(raw,first,plans)
            if after!=wanted:raise ValueError('Whole-track exact scope/parity readback failed')
            readback.update(after);first+=len(raw)//2352
        if dst.read(1):raise ValueError('Track size changed')
    if readback.hexdigest()!=target_hash.hexdigest():raise ValueError('Track digest readback failed')
    return readback.hexdigest(),touched


def build():
    if OUT.exists():raise ValueError('Preserve previous complete pair')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient E: space')
    previous=media.read(SOURCE/'manifest.json')
    if previous['status']!=prior.STATUS or previous['executable_sha256']!=EXE_SHA:
        raise ValueError('Wrong cumulative source pair')
    b.domina.zero.combined.verify_files(SOURCE,previous['files']);b.domina.zero.combined.cue_checks(SOURCE)
    for disc in (1,2):
        row=next(r for r in previous['files'] if r['path']==b.track(SOURCE,disc).relative_to(SOURCE).as_posix())
        if row['sha256']!=TRACK_HASHES[disc]:raise ValueError('Wrong per-disc identity')
    encoded = media.read(media.MEDIA/'manifest.json')
    if (encoded['status']!='verified-raised-disc2-subtitles' or encoded['margin_v']!=media.MARGIN
            or encoded['text_sha256']!=media.TEXT_SHA or len(encoded['clips'])!=11):
        raise ValueError('Movie media verification missing/stale')
    layouts = media.read(media.OUT/'layout-verification.json')
    if layouts['margin_v']!=media.MARGIN or not layouts['all_ink_above_row215']:
        raise ValueError('Subtitle safe-area proof missing')
    source=b.track(SOURCE,2)
    event,event_lba=b.READER.read_file(source,'EVENT.DAT')
    event_after,card,preview = patch_card(event)
    lo,hi=CARD//2048*2048,(card['end']+2047)//2048*2048
    plans=[(event_lba-45000+lo//2048,event_after[lo:hi])]
    replacements={'EVENT.DAT':event_after}
    movie_rows=[]
    for row in encoded['clips']:
        movie=(ROOT/row['path']).read_bytes()
        before,lba=b.READER.read_file(source,row['name'])
        if len(movie)!=len(before) or media.sha(movie)!=row['sha256'] or media.sha(before)!=row['current_sha256']:
            raise ValueError('Changed/misidentified replacement movie')
        if media.elementary(before,192)!=media.elementary(movie,192):raise ValueError('Audio changed')
        plans.append((lba-45000,movie));replacements[row['name']]=movie;movie_rows.append(row)
    OUT.mkdir();files=[]
    for row in previous['files']:
        src,dst=SOURCE/row['path'],OUT/row['path'];dst.parent.mkdir(exist_ok=True)
        if row['path']==b.track(SOURCE,2).relative_to(SOURCE).as_posix():
            digest,touched=copy_track(src,dst,TRACK_HASHES[2],plans)
            files.append(dict(path=row['path'],bytes=dst.stat().st_size,sha256=digest))
        else:
            with src.open('rb') as a,dst.open('xb') as c:shutil.copyfileobj(a,c,4*1024*1024)
            files.append(dict(row))
    target=b.track(OUT,2)
    with source.open('rb') as a,target.open('rb') as c:
        directory=list(b.READER.inject.iso_files(a))
        if directory!=list(b.READER.inject.iso_files(c)) or b.READER.inject._extent(a,45000,32768)!=b.READER.inject._extent(c,45000,32768):
            raise ValueError('Boot/directory changed')
    for name,_,_ in directory:
        actual=b.READER.read_file(target,name)[0]
        expected=replacements[name] if name in replacements else b.READER.read_file(source,name)[0]
        if actual!=expected:raise ValueError('Unexpected game file change '+name)
    b.domina.zero.combined.verify_files(OUT,files);b.domina.zero.combined.cue_checks(OUT)
    b.domina.zero.combined.verify_files(SOURCE,previous['files'])
    exe=(SOURCE/'1ST_READ.BIN').read_bytes()
    if media.sha(exe)!=EXE_SHA:raise ValueError('Executable changed')
    (OUT/'1ST_READ.BIN').write_bytes(exe)
    for old in SOURCE.glob('*-preview.png'):shutil.copy2(old,OUT/old.name)
    preview.resize((640,480),Image.Resampling.NEAREST).save(OUT/'why-father-preview.png')
    shutil.copy2(media.MEDIA/'MS1205/preview.png',OUT/'subtitle-safe-preview.png')
    shutil.copy2(media.OUT/'layout-verification.json',OUT/'subtitle-layout-verification.json')
    (OUT/'Black Matrix AD.m3u').write_text(''.join(f'disc{d}/Black-Matrix Advanced (Japan) (Disc {d}).cue\n' for d in (1,2)))
    report=dict(status=STATUS,build_version=VERSION,files=files,source=str(SOURCE),source_files=previous['files'],
        executable_sha256=EXE_SHA,disc1_exact_source_copy=True,card=card,movies=movie_rows,
        subtitle_margin_v=media.MARGIN,subtitle_layouts_checked=layouts['unique_texts'],
        changed_raw_sectors=touched,only_disc2_target_card_movies_and_sector_parity_changed=True,
        all_code_fonts_scripts_ui_and_other_movies_preserved=True,original_movie_audio_and_frames_preserved=True,
        disc1_working_prologue_timing_preserved=True,saves_and_profile_configuration_unchanged=True,
        renderer_launch_only_settings=b.renderer_settings(),private_local_only=True,
        gameplay_verified=False,physical_hardware_verified=False)
    media.save(OUT/'manifest.json',report)
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(
        'PRIVATE cumulative build0.1.2: Why?! / Why, Father?! story card and safer movie subtitles.\n'
        'Disc1 is an exact copy of preceding Results and Party build, including its working prologue.\n'
        'Disc2: one ImageGen-translated EVENT card and11 captioned movies; subtitle margin10 ->28.\n'
        'All68 unique text layouts checked for safe placement; words and cue times unchanged.\n'
        'Movie frame counts/rates/durations/geometry and native ADX audio/PES/decoded PCM preserved.\n'
        'All previous gameplay/font/UI/artwork fixes retained; no code or save/profile writes.\n'
        'Use project Play - Disc 2 - Story and Subtitle Fix.cmd after closing Flycast.\n'
        'Same original E: VMUs (latest old saves Port A Slot2); never open with another Flycast.\n'
        'Packed card and decoded movie previews included. Fresh gameplay/hardware still pending.\n'
        'Originals and previous builds preserved; full game binaries must remain private/local on E:.\n')
    print('New private complete pair verified:',OUT,flush=True)


def launch(disc):b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.build:build()
    if a.launch:launch(a.launch)
