"""Private cumulative static story-card localization; no runtime edits."""
import argparse
import hashlib
import json
import re
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageOps

import mode_label_readability as prior
import pvr_atlas
from story_movie_safe_build import copy_track

ROOT = prior.ROOT
b = prior.b
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-story-cards-english-2026-11-02'
STATUS = 'private-story-cards-english-runtime-pending'
VERSION = '0.1.7'
EXE_SHA = prior.EXE_SHA
TRACK_HASHES = {1:'3783db572fb82610f0b81d9aad9d802cc529d99b62e9fffc560608e36d8de6b1',
                2:'a1ab97e9b08e8aefb975a0776709a3b378ead8dea5a912e521bf2941bd0e4a73'}
ASSETS = ROOT/'assets/ui/story-cards'
TEXT = ASSETS/'story-cards-english-v1.en.json'
PROMPTS = ASSETS/'story-cards-english-v1.prompts.json'
PROVENANCE = ASSETS/'story-cards-english-v1.provenance.json'
AUDIT = ROOT/'build/story-card-audit-2026-11-02/inventory.json'
REVIEW = ROOT/'build/story-card-english-review-2026-11-02'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, data):
    # Existing shared launcher uses the Windows default text codec. Keep build
    # metadata ASCII-escaped, so English em dashes cannot break loading on GBK.
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True)+'\n', encoding='utf-8')


def inventory():
    text, audit = read(TEXT), read(AUDIT)
    targets = {}
    for asset in text['assets']:
        for offset in asset['offsets']:
            off = int(offset, 16)
            if off in targets:
                raise ValueError('Duplicate target')
            targets[off] = asset
    if len(text['assets']) != 29 or len(targets) != 37 or len(audit['candidates']) != 66:
        raise ValueError('Reviewed inventory changed')
    candidates = []
    for row in audit['candidates']:
        item = dict(row)
        if row['disc'] == 2 and row['offset'] in targets:
            item.update(classification='Japanese; replace', asset_id=targets[row['offset']]['id'])
        elif row['disc'] == 2 and row['offset'] == int(text['unchanged_punctuation_only'], 16):
            item['classification'] = 'Punctuation only; preserve'
        else:
            item['classification'] = 'Existing English; preserve'
        candidates.append(item)
    if sum(r['classification'].startswith('Japanese') for r in candidates) != len(targets):
        raise ValueError('Unaudited target')
    return text, audit, targets, candidates


def native_image(path):
    # Format conversion only, no lettering redraw. Existing game doubles Y.
    with Image.open(path) as im:
        fitted = ImageOps.contain(im.convert('RGB'), (640,480), Image.Resampling.LANCZOS)
        frame = Image.new('RGB', (640,480), 'black')
        frame.paste(fitted, ((640-fitted.width)//2, (480-fitted.height)//2))
        return frame.resize((640,240), Image.Resampling.LANCZOS)


def contacts(items, folder, prefix):
    folder.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(items), 9):
        group = items[start:start+9]
        sheet = Image.new('RGB', (1920,510*((len(group)+2)//3)), '#202020')
        draw = ImageDraw.Draw(sheet)
        for i, (name, im) in enumerate(group):
            x, y = i%3*640, i//3*510
            draw.text((x+8,y+8), name, fill='white')
            sheet.paste(im.resize((640,480), Image.Resampling.NEAREST), (x,y+30))
        sheet.save(folder/f'{prefix}-{start//9:02}.png')


def preview_assets():
    text, _, _, _ = inventory()
    REVIEW.mkdir(parents=True, exist_ok=True)
    items = []
    for asset in text['assets']:
        path = ASSETS/'english-v1'/f"{asset['id']}.png"
        if path.exists():
            im = native_image(path)
            im.save(REVIEW/f"{asset['id']}-native.png")
            items.append((asset['id'], im))
    contacts(items, REVIEW, 'native-contact')
    print('Native format previews:', len(items), REVIEW, flush=True)


def patch_cards(event):
    text, audit, targets, candidates = inventory()
    source_row = next(r for r in audit['scanned'] if r['disc']==2 and r['archive']=='EVENT.DAT')
    if b.sha(event) != source_row['sha256']:
        raise ValueError('Unknown/reapplied cumulative EVENT source')
    provenance = read(PROVENANCE)
    if provenance['status'] != 'reviewed-production-imagegen-assets':
        raise ValueError('ImageGen review incomplete')
    if provenance['text_sha256'] != b.sha(TEXT.read_bytes()) or provenance['prompts_sha256'] != b.sha(PROMPTS.read_bytes()):
        raise ValueError('Reviewed wording/prompts changed')
    if len(provenance['assets']) != 29:
        raise ValueError('ImageGen assets incomplete')
    assets = {r['id']:r for r in provenance['assets']}
    images = {}
    for asset in text['assets']:
        ident = asset['id']; row = assets[ident]
        path = ROOT/row['path']
        if b.sha(path.read_bytes()) != row['sha256']:
            raise ValueError('Reviewed ImageGen pixels changed: '+ident)
        images[ident] = native_image(path)
    audited = {r['offset']:r for r in candidates if r['disc']==2 and r['offset'] in targets}
    # Verify every leaf/layout first; no output bytes modified until all guards pass.
    layouts = {}
    for off, asset in targets.items():
        cols, rows, _, pages = pvr_atlas.scl_layout(event,off)
        end = pages[-1]+16+131072
        if (cols,rows,len(pages)) != (40,15,1) or end != audited[off]['end']:
            raise ValueError('Unexpected source card geometry')
        if b.sha(event[off:end]) != audited[off]['leaf_sha256']:
            raise ValueError('Unexpected source card identity')
        layouts[off] = (end,pages)
    owners = {}
    for match in re.finditer(b'SCL ',event):
        try:
            pages = pvr_atlas.scl_layout(event, match.start())[3]
        except (ValueError,IndexError,OverflowError):
            continue
        for page in pages:
            owners.setdefault(page,set()).add(match.start())
    for off, (_, pages) in layouts.items():
        if any(owners[p] != {off} for p in pages):
            raise ValueError('Target atlas shared by another image')
    after = bytearray(event); allowed = []; reports = []; previews = []
    for off, asset in sorted(targets.items()):
        end, pages = layouts[off]; image = images[asset['id']]
        count = pvr_atlas.encode_scl(after,off,image)
        allowed.extend([(off+32,off+32+2400), *((p+16,p+16+131072) for p in pages)])
        decoded = pvr_atlas.decode_scl(after,off)
        if decoded.tobytes() != Image.fromarray(b.quantized(image)).tobytes():
            raise ValueError('Packed card differs from ImageGen format conversion')
        reports.append(dict(offset=off,end=end,id=asset['id'],lines=asset['lines'],tiles=count,capacity=256,
            source_leaf_sha256=audited[off]['leaf_sha256'],leaf_sha256=b.sha(after[off:end]),
            native_rgb_sha256=b.sha(decoded.tobytes()),asset_sha256=assets[asset['id']]['sha256']))
        previews.append((f"{off:08x} {asset['id']}",decoded))
    last = 0
    for lo,hi in sorted(allowed):
        if lo < last or event[last:lo] != after[last:lo]:
            raise ValueError('Out-of-card/header/directory edit')
        last = hi
    if event[last:] != after[last:]:
        raise ValueError('Out-of-card tail edit')
    # Independently read EVERY candidate, not only replacement cards.
    for row in candidates:
        if row['disc']==2 and row['offset'] not in targets:
            if event[row['offset']:row['end']] != after[row['offset']:row['end']]:
                raise ValueError('Existing English or punctuation card changed')
    return bytes(after), reports, previews, allowed


def sector_plans(event_after, event_lba, reports):
    intervals = sorted((r['offset']//2048*2048, (r['end']+2047)//2048*2048) for r in reports)
    merged = []
    for lo,hi in intervals:
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0],max(hi,merged[-1][1]))
        else:
            merged.append((lo,hi))
    if any(hi>len(event_after) for _,hi in merged):
        raise ValueError('Extent beyond EVENT')
    return [(event_lba-45000+lo//2048,event_after[lo:hi]) for lo,hi in merged]


def build():
    if OUT.exists():
        raise ValueError('Preserve previous complete pair')
    if shutil.disk_usage(OUT.anchor).free < 3*1024**3:
        raise ValueError('Insufficient E: space')
    previous = read(SOURCE/'manifest.json')
    if previous['status'] != prior.STATUS or previous['executable_sha256'] != EXE_SHA:
        raise ValueError('Wrong cumulative source')
    b.domina.zero.combined.verify_files(SOURCE,previous['files'])
    b.domina.zero.combined.cue_checks(SOURCE)
    for disc in (1,2):
        row = next(r for r in previous['files'] if r['path']==b.track(SOURCE,disc).relative_to(SOURCE).as_posix())
        if row['sha256'] != TRACK_HASHES[disc]:
            raise ValueError('Wrong per-disc track identity')
    source = b.track(SOURCE,2)
    event,lba = b.READER.read_file(source,'EVENT.DAT')
    after, cards, previews, allowed = patch_cards(event)
    plans = sector_plans(after,lba,cards)
    print('Dry-run verified:37 cards/29 images; only original maps/atlas payloads change.',flush=True)
    print('Copying private cumulative pair; full raw readback/parity follows.',flush=True)
    OUT.mkdir(); files = []; touched = []
    for row in previous['files']:
        src,dst = SOURCE/row['path'],OUT/row['path']
        dst.parent.mkdir(exist_ok=True)
        if row['path']==source.relative_to(SOURCE).as_posix():
            digest,touched = copy_track(src,dst,TRACK_HASHES[2],plans)
            files.append(dict(path=row['path'],bytes=dst.stat().st_size,sha256=digest))
        else:
            with src.open('rb') as a,dst.open('xb') as c:
                shutil.copyfileobj(a,c,4*1024*1024)
            files.append(dict(row))
    target = b.track(OUT,2)
    with source.open('rb') as a,target.open('rb') as c:
        directory = list(b.READER.inject.iso_files(a))
        if directory != list(b.READER.inject.iso_files(c)) or b.READER.inject._extent(a,45000,32768) != b.READER.inject._extent(c,45000,32768):
            raise ValueError('Boot/directory changed')
    for name,_,_ in directory:
        actual = b.READER.read_file(target,name)[0]
        expected = after if name=='EVENT.DAT' else b.READER.read_file(source,name)[0]
        if actual != expected:
            raise ValueError('Unexpected ISO payload change: '+name)
        print('Verified payload',name,flush=True)
    b.domina.zero.combined.verify_files(OUT,files)
    b.domina.zero.combined.cue_checks(OUT)
    b.domina.zero.combined.verify_files(SOURCE,previous['files'])
    exe = (SOURCE/'1ST_READ.BIN').read_bytes()
    if b.sha(exe) != EXE_SHA:
        raise ValueError('Executable changed')
    (OUT/'1ST_READ.BIN').write_bytes(exe)
    for old in SOURCE.glob('*-preview.png'):
        shutil.copy2(old,OUT/old.name)
    contacts(previews,OUT/'story-card-previews','packed')
    text,audit,_,coverage = inventory()
    save(OUT/'story-card-coverage.json',dict(scope=audit['scope'],candidates=coverage,
        existing_english=28,newly_english=37,punctuation_only=1,unique_new_assets=29,
        excluded_decode_errors='Two copies of SYSTEM 0x1ad3c0 use32px tiles; manually decoded mask has no text.',
        not_a_global_all_text_or_movie_frame_audit=True))
    shutil.copy2(TEXT,OUT/TEXT.name)
    shutil.copy2(PROVENANCE,OUT/PROVENANCE.name)
    (OUT/'Black Matrix AD.m3u').write_text(''.join(f'disc{d}/Black-Matrix Advanced (Japan) (Disc {d}).cue\n' for d in (1,2)))
    report = dict(status=STATUS,build_version=VERSION,files=files,source=str(SOURCE),source_files=previous['files'],
        executable_sha256=EXE_SHA,disc1_exact_source_copy=True,cards=cards,
        source_event_sha256=b.sha(event),event_sha256=b.sha(after),allowed_event_spans=allowed,
        changed_raw_sectors=touched,all_other_event_bytes_headers_and_candidates_unchanged=True,
        every_iso_payload_and_raw_sector_readback_verified=True,all_movies_byte_exact=True,
        all_previous_gameplay_font_ui_fixes_preserved=True,saves_and_profile_configuration_unchanged=True,
        renderer_launch_only_settings=b.renderer_settings(),private_local_only=True,
        gameplay_verified=False,physical_hardware_verified=False)
    save(OUT/'manifest.json',report)
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(
        'PRIVATE cumulative0.1.7:37 remaining Japanese static white-on-black story cards translated.\n'
        '29 actual built-in ImageGen English assets; route wording/stammers/endings preserved.\n'
        'Both-disc audit:66 cards;28 already English preserved,37 translated,1 punctuation-only preserved.\n'
        'Disc1 is an EXACT copy of0.1.6; Disc2 changes ONLY37 EVENT maps/atlases and sector parity.\n'
        'All movies/audio/subtitles, code/fonts/scripts/UI and previous fixes remain byte exact.\n'
        'Static monochrome SCL family audit only, not a claim that every game text/movie frame is English.\n'
        'Use project Play - Disc 2 - English Story Cards.cmd (or Disc1) after closing Flycast.\n'
        'SAME original E: VMUs, latest old saves Port A Slot2; no save/card/config writes.\n'
        'Packed readback contact sheets included. Fresh game/hardware display still pending.\n'
        'Separate Equip oversized font/topic-list alignment remain pending.\n'
        'No emulator launch/restart/input, publication, upload, tag or release performed.\n'
        'Originals/previous builds preserved; complete binaries must stay private/local on E:.\n')
    print('New private complete pair verified:',OUT,flush=True)


def launch(disc):
    b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--launch',type=int,choices=(1,2))
    args = parser.parse_args()
    if args.preview:
        preview_assets()
    elif args.plan:
        event = b.READER.read_file(b.track(SOURCE,2),'EVENT.DAT')[0]
        print(json.dumps(patch_cards(event)[1],indent=2))
    elif args.build:
        build()
    elif args.launch:
        launch(args.launch)
