"""Private cumulative0.1.9: native, automatic post-credits voice captions."""
import argparse
import json
import shutil
import struct

import credits_english as prior
import ending_caption_native as cap
import ending_voice_subtitles as audio
import mode1_sector
import sh4dis
from PIL import Image,ImageDraw

ROOT=prior.ROOT
b=prior.b
SOURCE=prior.OUT
OUT=ROOT/'output/patched-discs-ending-subtitles-2026-11-02'
AUDIT=audio.OUT
TEXT=ROOT/'assets/subtitles/post-credits.en.json'
STATUS='private-ending-subtitles-runtime-pending'
VERSION='0.1.9'
TRACK_HASHES={1:'3783db572fb82610f0b81d9aad9d802cc529d99b62e9fffc560608e36d8de6b1',
              2:'52db5223a318555a68e8701913e93a7df5a09f6bf6dc4da1c7a246d2fa57fd67'}
read=prior.media.read
save=audio.save


def inputs():
    text=read(TEXT);review=read(AUDIT/'meaning-review.json')
    if text['version']!=VERSION or len(text['rows'])!=18 or review['rows_examined']!=18:
        raise ValueError('Incomplete translation/review')
    captions={row['voice']:row['text'] for row in text['rows']}
    if len(captions)!=18 or any(not t for t in captions.values()):raise ValueError('Incomplete captions')
    # Meaning changes are already applied; canonical glossary names are last.
    if 'Kain' not in captions[0xa17] or 'Cain' in ' '.join(captions.values()):raise ValueError('Canonical Kain regression')
    if captions[0xa11]!='Master!' or captions[0xa19]!='Darling!':raise ValueError('Canonical address regression')
    exe=(SOURCE/'1ST_READ.BIN').read_bytes()
    if b.sha(exe)!=prior.EXE_SHA:raise ValueError('Unknown cumulative executable')
    if b.READER.read_file(b.track(SOURCE,2),'1ST_READ.BIN')[0]!=exe:raise ValueError('Loose/embedded executable mismatch')
    # This same small, static zero reservation was used by the old dialogue
    # trial. Authenticate an existing read-only RAM capture too; no new capture.
    import whip_remove_font as old
    ram=old.CAPTURE.read_bytes()
    if b.sha(ram)!=old.CAPTURE_SHA or any(ram[cap.CODE-0x8c000000:cap.END-0x8c000000]):
        raise ValueError('Unverified live caption reservation')
    newexe,delta=cap.patch_exe(exe,(ROOT/'extracted/1ST_READ.BIN').read_bytes())
    scenario,lba=b.READER.read_file(b.track(SOURCE,2),'SCENARIO.DAT')
    newscenario,rows=cap.patch_archive(scenario,captions)
    report=dict(build_version=VERSION,source=str(SOURCE),captions=rows,
        source_executable_sha256=b.sha(exe),executable_sha256=b.sha(newexe),
        source_scenario_sha256=b.sha(scenario),scenario_sha256=b.sha(newscenario),
        changed_executable_bytes=len(delta),scenario_bytes=len(newscenario),
        script_group=cap.GROUP,script_runtime_group=cap.GROUP-1,
        helper_address=hex(cap.CODE),helper_bytes=len(cap.helper()),new_statement=cap.OPCODE,
        text_sha256=b.sha(TEXT.read_bytes()),meaning_review_sha256=b.sha((AUDIT/'meaning-review.json').read_bytes()),
        original_voice_load_start_wait_order_and_conditional_branches_preserved=True,
        original_group_instructions_reconstruct_exactly=True,new_button_waits=0,
        no_null_handler_padding=True,caption_max_rows=2,native_dialogue_font_unchanged=True,
        audio_archive_and_all_movies_unchanged=True,prior_credits_and_story_cards_preserved=True,
        moderate_asr_voices=[r['voice'] for r in text['rows'] if r['confidence']=='moderate'],
        gameplay_verified=False,physical_hardware_verified=False)
    return newexe,newscenario,report


def prepare():
    exe,scenario,report=inputs()
    # Show the actual change samples BEFORE saving candidate game data.
    for row in report['captions']:print(hex(row['voice']),repr(row['text']),flush=True)
    folder=AUDIT/'prepared'
    if folder.exists():raise ValueError('Preserve existing preparation')
    folder.mkdir();(folder/'1ST_READ.BIN').write_bytes(exe);(folder/'SCENARIO.DAT').write_bytes(scenario)
    (folder/'helper-disassembly.txt').write_text('\n'.join(sh4dis.disassemble(cap.helper(),0,len(cap.helper()),cap.CODE))+'\n')
    save(folder/'verification.json',report)
    preview(exe,report['captions'],folder)
    print('Prepared18 automatic captions; source discs untouched.',flush=True)


def preview(exe,rows,folder):
    """Actual packed canonical glyphs; row-fit proof, not an emulator capture."""
    import skies_vga_sharp_footer as font
    import skies_size_match as metrics
    system=b.READER.read_file(b.track(SOURCE,2),'SYSTEM.DAT')[0]
    pages=[font.previous.ritual.full.decode_vq(system[font.prior.FONT_OFFSET+16+bank*128:
        font.prior.FONT_OFFSET+16+bank*128+8192]) for bank in font.previous.ritual.full.BANKS]
    sheet=Image.new('RGBA',(1280,1120),'#151515');draw=ImageDraw.Draw(sheet)
    draw.text((12,8),'OFFLINE ROW-FIT PROOF - actual packed font, not in-game position/appearance verification',fill='white')
    checked=[]
    for i,row in enumerate(rows):
        x,y=(i%2)*640,(i//2)*120+32
        draw.rectangle((x+8,y+20,x+630,y+108),fill='black')
        draw.text((x+12,y+2),f"Voice {row['voice']:04x}",fill='#dfb040')
        cell=0;pen=0;line=0;max_right=0
        for char in row['text']:
            if char=='\n':cell=(cell//33+1)*33;pen=0;line=cell//33;continue
            if cell and cell%33==0:pen=0;line=cell//33
            if char==' ':pen+=8
            else:
                gid=font.prior.latin.charmap()[char]
                slot=exe[font.prior.atlas.FORWARD-font.prior.atlas.BASE+gid]
                if slot>=128:raise ValueError('Caption glyph not admitted')
                sx=slot%8*16;sy=(slot%32//8)*32
                tile=pages[slot//32].crop((sx,sy,sx+16,sy+24))
                box=tile.getbbox()
                if box:max_right=max(max_right,pen+box[2])
                sheet.alpha_composite(tile,(x+20+pen,y+28+line*36))
                pen+=exe[metrics.SMALL_ADV-cap.BASE+gid]
            cell+=1
        if line>1 or max_right>476:raise ValueError('Packed-font caption overflows native text area')
        checked.append(dict(voice=row['voice'],rows=line+1,max_ink_x=max_right))
    sheet.convert('RGB').save(folder/'caption-row-fit.png')
    save(folder/'layout-verification.json',dict(method='Decoded current native canonical glyphs/advances; offline row proof only',captions=checked,
        no_font_pixel_size_or_metrics_changes=True,in_game_position_verified=False))


def build():
    if OUT.exists():raise ValueError('Preserve existing complete output')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient E: space')
    exe,scenario,prepared=inputs()
    if read(AUDIT/'prepared/verification.json')!=prepared:raise ValueError('Stale preparation/review')
    if exe!=(AUDIT/'prepared/1ST_READ.BIN').read_bytes() or scenario!=(AUDIT/'prepared/SCENARIO.DAT').read_bytes():
        raise ValueError('Prepared binaries differ')
    previous=read(SOURCE/'manifest.json')
    if previous['status']!=prior.STATUS:raise ValueError('Wrong cumulative source status')
    b.domina.zero.combined.verify_files(SOURCE,previous['files']);b.domina.zero.combined.cue_checks(SOURCE)
    for disc in (1,2):
        row=next(r for r in previous['files'] if r['path']==b.track(SOURCE,disc).relative_to(SOURCE).as_posix())
        if row['sha256']!=TRACK_HASHES[disc]:raise ValueError('Wrong per-disc source')
    source=b.track(SOURCE,2);replacements={'1ST_READ.BIN':exe,'SCENARIO.DAT':scenario};plans=[]
    for name,data in replacements.items():
        before,lba=b.READER.read_file(source,name)
        if len(before)!=len(data):raise ValueError('Changed ISO file allocation')
        payload=data+bytes((-len(data))%2048)
        plans.append((lba-45000,payload))
    print('Authenticated plan: Disc1 exact copy; Disc2 only ending caption code/script and parity.',flush=True)
    OUT.mkdir();files=[];touched=[]
    for row in previous['files']:
        src,dst=SOURCE/row['path'],OUT/row['path'];dst.parent.mkdir(exist_ok=True)
        if row['path']==source.relative_to(SOURCE).as_posix():
            digest,touched=prior.prior.copy_track(src,dst,TRACK_HASHES[2],plans)
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
        expected=replacements.get(name)
        if expected is None:expected=b.READER.read_file(source,name)[0]
        if actual!=expected:raise ValueError('Unexpected ISO change '+name)
        print('Verified payload',name,flush=True)
    b.domina.zero.combined.verify_files(OUT,files);b.domina.zero.combined.cue_checks(OUT)
    b.domina.zero.combined.verify_files(SOURCE,previous['files'])
    (OUT/'1ST_READ.BIN').write_bytes(exe)
    shutil.copy2(SOURCE/'1ST_READ.BIN',OUT/'1ST_READ.disc1.BIN')
    for path in SOURCE.iterdir():
        if path.is_dir() and path.name not in ('disc1','disc2'):shutil.copytree(path,OUT/path.name)
        elif path.is_file() and (path.suffix=='.png' or path.name.endswith(('.en.json','.provenance.json','verification.json','coverage.json'))):shutil.copy2(path,OUT/path.name)
    shutil.copy2(TEXT,OUT/TEXT.name);shutil.copy2(AUDIT/'meaning-review.json',OUT/'ending-meaning-review.json')
    shutil.copy2(AUDIT/'prepared/caption-row-fit.png',OUT/'ending-caption-row-fit.png')
    shutil.copy2(AUDIT/'prepared/layout-verification.json',OUT/'ending-layout-verification.json')
    save(OUT/'ending-subtitle-verification.json',prepared)
    (OUT/'Black Matrix AD.m3u').write_text(''.join(f'disc{d}/Black-Matrix Advanced (Japan) (Disc {d}).cue\n' for d in (1,2)))
    report=dict(status=STATUS,build_version=VERSION,files=files,source=str(SOURCE),source_files=previous['files'],
        executable_sha256=b.sha(exe),disc_executable_sha256={1:prior.EXE_SHA,2:b.sha(exe)},
        disc1_exact_source_copy=True,changed_raw_sectors=touched,ending=prepared,
        saves_and_profile_configuration_unchanged=True,renderer_launch_only_settings=b.renderer_settings(),
        private_local_only=True,gameplay_verified=False,physical_hardware_verified=False,
        unresolved=['Four brief calls retain moderate Whisper confidence, documented in the English caption manifest.',
            'Fresh in-game post-credits playback and appearance still require testing.',
            *previous.get('unresolved',[])])
    save(OUT/'manifest.json',report)
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(
        'PRIVATE cumulative0.1.9: automatic English captions for the post-credits angel-CG conversation.\n'
        '18 unique voice cues including original master/character-dependent branches.\n'
        'Local Whisper small/large-v3 Japanese transcription, meaning/editorial review and final proof.\n'
        'Four short calls retain moderate ASR confidence; see post-credits.en.json.\n'
        'Native existing font/window, instant caption reveal; no added button waits.\n'
        'Original audio, cue order, conditional branches, art, all movies and credits retained.\n'
        'Disc1 exact0.1.8 copy; Disc2 only guarded code/script and raw sector parity.\n'
        'Play - Disc 2 - Ending Subtitles.cmd uses SAME original E: VMUs, latest saves PortA Slot2.\n'
        'No emulator launch/input/restart or save/card/profile writes during preparation.\n'
        'Offline script/code/disc verification passed; fresh in-game ending/hardware testing pending.\n'
        'Originals/previous outputs preserved. No M: output, upload, publication, tag or release.\n'
        'Complete translated game binaries must remain private/local.\n')
    print('Private0.1.9 ending subtitle pair verified:',OUT,flush=True)


def launch(disc):b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--build',action='store_true');p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.prepare:prepare()
    elif a.build:build()
    elif a.launch:launch(a.launch)
    else:print(json.dumps(inputs()[2],indent=2))
