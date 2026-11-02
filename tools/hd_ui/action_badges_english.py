"""ImageGen production lettering for all remaining Japanese battle badges."""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

import numpy as np
from PIL import Image,ImageDraw
import join_footer_font as prior
import native_translation_parity as native
import pvr_atlas
import japanese_audit

ROOT=prior.ROOT
b=prior.b
SOURCE=prior.OUT
OUT=ROOT/'output/patched-discs-action-badges-2026-11-02'
ASSETS=ROOT/'assets/ui/battle-labels/action-badges-v1'
ASSET=ASSETS/'generated-lettering.png'
ASSET_SHA='3a04fe2944bdfc2081e1dd716e0f8c24451c41d90ff97a91e98c725478f64a65'
PREPARED=ROOT/'build/action-badge-prepared-v2-2026-11-02'
VERSION='0.1.13'
STATUS='private-action-badges-runtime-pending'
CHAR_SHA='eb0176d000002d84f8288fae6e36ccb2335aa6faae169643a27f7224faa19edf'
TEXTURE=0x1350
LABELS={82:'Miss!',83:'Guard',84:'Stone',85:'Poison',86:'Paral.',87:'Status',
        88:'Sleep',89:'Up',90:'Down',91:'Freeze',104:'Stance',162:'Magic'}
RECTS={82:(176,0,200,16),83:(96,48,128,64),84:(200,0,224,16),85:(176,16,200,32),
       86:(200,16,224,32),87:(176,32,224,48),88:(128,48,160,64),89:(160,48,192,64),
       90:(192,48,224,64),91:(176,64,216,80),104:(176,96,224,112),162:(192,240,224,256)}
SPLIT=(104,105,106)
save=prior.save


def masks():
    if b.sha(ASSET.read_bytes())!=ASSET_SHA:raise ValueError('Generated lettering asset changed')
    with Image.open(ASSET) as image:
        if image.mode!='RGBA' or image.size!=(1536,1024):raise ValueError('Unexpected generated atlas')
        # Native1555 stores binary alpha. Transparent RGB is never sampled.
        alpha=image.getchannel('A')
    result={};coverage=[]
    for i,(index,text) in enumerate(LABELS.items()):
        # Identical source-cell conversion for every word; no font/letter
        # reconstruction or per-word fitting. This retains one-pixel stems
        # that the earlier overly small64x32 conversion dropped.
        tile=alpha.crop(((i%3)*512,(i//3)*256,(i%3+1)*512,(i//3+1)*256))
        tile=tile.resize((73,43),Image.Resampling.LANCZOS).point(lambda a:255 if a>=96 else 0)
        box=tile.getbbox()
        if box is None:raise ValueError('Blank generated word '+text)
        ink=tile.crop(box);rect=RECTS[index];w,h=rect[2]-rect[0],rect[3]-rect[1]
        if ink.width>w-1 or ink.height>h-4:raise ValueError(f'Generated word exceeds native slot {text}: {ink.size}/{w,h}')
        result[index]=ink
        coverage.append(dict(sprite=index,text=text,ink_size=list(ink.size),target_size=[w,h],generated_cell=i))
    return result,coverage


def artwork(before):
    page=pvr_atlas.decode(before,TEXTURE);words,coverage=masks();result={}
    for index,ink in words.items():
        r=RECTS[index];w,h=r[2]-r[0],r[3]-r[1]
        original=np.asarray(page.crop(r));pixels=original[original[:,:,3]>0]
        foreground=max((tuple(int(c) for c in p[:3]) for p in pixels),key=sum)
        # Inverse of native.encode's floor-to5bit conversion preserves the
        # original decoded peak gray/red/gold exactly.
        colour=tuple((round(c*31/255)*255+30)//31 for c in foreground)
        tile=Image.new('RGBA',(w,h));x=(w-ink.width-1)//2;y=3
        shadow=Image.new('RGBA',ink.size,(0,0,0,0));shadow.putalpha(ink)
        tile.alpha_composite(shadow,(x+1,y+1))
        fg=Image.new('RGBA',ink.size,colour+(0,));fg.putalpha(ink)
        tile.alpha_composite(fg,(x,y))
        if tile.getbbox() is None or tile.getbbox()[3]>h:raise ValueError('Packed badge clips')
        result[index]=tile
    return result,coverage


def patch(before,disc):
    if disc not in (1,2) or b.sha(before)!=CHAR_SHA:raise ValueError('Unknown cumulative CHAR')
    rows=native.pack.descriptors(before,TEXTURE);page=pvr_atlas.decode(before,TEXTURE)
    original=japanese_audit.archive(disc,'CHAR.DAT');old=pvr_atlas.decode(original,TEXTURE)
    expected={i:r for i,r in RECTS.items() if i!=104}|{i:(176+(i-104)*16,96,192+(i-104)*16,112) for i in SPLIT}
    if any(rows[i]!=r for i,r in expected.items()):raise ValueError('Action descriptor changed')
    for r in RECTS.values():
        if page.crop(r).tobytes()!=old.crop(r).tobytes():raise ValueError('Expected original Japanese region')
    tiles,coverage=artwork(before);after=bytearray(before);allowed=set()
    for index,tile in tiles.items():
        for pos,value in native.encode(before,TEXTURE,RECTS[index],tile):
            after[pos:pos+2]=value;allowed.update((pos,pos+1))
    delta=np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(after,'u1')).tolist()
    if not delta or not set(delta)<=allowed or len(after)!=len(before):raise ValueError('Out-of-action-art edit')
    packed=pvr_atlas.decode(after,TEXTURE)
    for index,tile in tiles.items():
        # Verify exact native quantization; no unexpected opaque box/glow.
        actual=packed.crop(RECTS[index]);a=np.asarray(actual)
        if set(a[:,:,3].ravel())!={0,255}:raise ValueError('Unexpected alpha format')
        if not np.array_equal(a[:,:,3],np.asarray(tile)[:,:,3]):raise ValueError('Native alpha differs')
    for i,r in rows.items():
        if i not in expected and page.crop(r).tobytes()!=packed.crop(r).tobytes():raise ValueError('Unrelated descriptor pixels changed '+str(i))
    return bytes(after),delta,coverage


def preview(before,after,folder):
    old,new=pvr_atlas.decode(before,TEXTURE),pvr_atlas.decode(after,TEXTURE)
    sheet=Image.new('RGB',(760,68*12+45),'#171717');d=ImageDraw.Draw(sheet)
    d.text((8,8),'ACTUAL PACKED native sprites at4x - offline, NOT gameplay',fill='white')
    d.text((180,26),'Before',fill='white');d.text((440,26),'English (generated pixels)',fill='white')
    for row,(i,text) in enumerate(LABELS.items()):
        y=45+row*68;d.text((8,y+18),f'{i} {text}',fill='white')
        for x,page in ((180,old),(440,new)):
            tile=page.crop(RECTS[i]);tile=tile.resize((tile.width*4,tile.height*4),Image.Resampling.NEAREST)
            sheet.paste(tile,(x,y),tile)
    sheet.save(folder/'action-badges-packed-preview.png')


def prepare(write=False):
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    if manifest['status']!=prior.STATUS or manifest['build_version']!='0.1.12':raise ValueError('Wrong cumulative source')
    before=b.READER.read_file(b.track(SOURCE,2),'CHAR.DAT')[0]
    after,delta,coverage=patch(before,2)
    one=b.READER.read_file(b.track(SOURCE,1),'CHAR.DAT')[0]
    if one!=before or patch(one,1)[0]!=after:raise ValueError('Per-disc CHAR differs')
    report=dict(build_version=VERSION,status=STATUS,source=str(SOURCE),source_char_sha256=CHAR_SHA,char_sha256=b.sha(after),
        changed_char_bytes=len(delta),reviewed_descriptors=169,translated_label_groups=12,changed_descriptors=14,
        labels=LABELS,rectangles=RECTS,split_stance_descriptors=SPLIT,coverage=coverage,
        generated_asset_sha256=b.sha(ASSET.read_bytes()),imagegen_role='ACTUAL generated lettering alpha packed into native sprites',
        common_source_cell=[512,256],common_native_conversion_cell=[73,43],foreground_coverage_threshold=96,
        no_word_specific_scaling=True,no_old_font_masks=True,alpha_format='native1bit',
        palette_peak_and_existing_geometry_preserved=True,all_other_pixels_headers_descriptors_unchanged=True,
        code_scripts_gameplay_audio_movies_and_prior_fixes_unchanged=True,saves_profiles_and_emulator_untouched=True,
        private_local_only=True,gameplay_verified=False,physical_hardware_verified=False)
    # Use the same string keys/lists in memory and in the persisted JSON proof.
    report=json.loads(json.dumps(report))
    if write:
        folder=PREPARED
        if folder.exists():raise ValueError('Preserve prior preparation')
        folder.mkdir();(folder/'CHAR.DAT').write_bytes(after);save(folder/'verification.json',report)
        preview(before,after,folder)
    return manifest,after,report


def build():
    manifest,char,report=prepare()
    review=json.loads((ASSETS/'labels.en.json').read_text())
    if review['asset_sha256']!=ASSET_SHA or review['review']['accuracy_rows_examined']!=12 or review['review']['editorial_packed_labels_examined']!=12 or review['review']['main_final_proof_rows']!=12:
        raise ValueError('Incomplete asset/editorial review')
    if json.loads((PREPARED/'verification.json').read_text())!=report or (PREPARED/'CHAR.DAT').read_bytes()!=char:
        raise ValueError('Stale prepared native artwork')
    if OUT.exists():raise ValueError('Preserve previous output')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient E: space')
    b.domina.zero.combined.verify_files(SOURCE,manifest['files']);b.domina.zero.combined.cue_checks(SOURCE)
    print('Authenticated0.1.13:12 reviewed generated English badges,14 native descriptors; no code changes.',flush=True)
    OUT.mkdir();files=[];touched={}
    for item in manifest['files']:
        src,dst=SOURCE/item['path'],OUT/item['path'];dst.parent.mkdir(exist_ok=True)
        disc=next((d for d in (1,2) if src==b.track(SOURCE,d)),None)
        if disc:
            _,lba=b.READER.read_file(src,'CHAR.DAT')
            plans=[(lba-45000,char+bytes((-len(char))%2048))]
            digest,sectors=prior.prior.prior.prior.prior.copy_track(src,dst,item['sha256'],plans)
            touched[disc]=sectors;files.append(dict(path=item['path'],bytes=dst.stat().st_size,sha256=digest))
            print('Whole-track exact-change/parity verified Disc',disc,flush=True)
        else:shutil.copy2(src,dst);files.append(dict(item))
    for disc in (1,2):
        src,dst=b.track(SOURCE,disc),b.track(OUT,disc)
        with src.open('rb') as a,dst.open('rb') as c:
            directory=list(b.READER.inject.iso_files(a))
            if directory!=list(b.READER.inject.iso_files(c)) or b.READER.inject._extent(a,45000,32768)!=b.READER.inject._extent(c,45000,32768):
                raise ValueError('Boot/directory changed')
        for name,_,_ in directory:
            expected=char if name=='CHAR.DAT' else b.READER.read_file(src,name)[0]
            if b.READER.read_file(dst,name)[0]!=expected:raise ValueError('Unrelated ISO payload changed '+name)
        print('Every ISO payload verified Disc',disc,flush=True)
    b.domina.zero.combined.verify_files(OUT,files);b.domina.zero.combined.cue_checks(OUT)
    for path in SOURCE.iterdir():
        if path.is_dir() and path.name not in ('disc1','disc2'):shutil.copytree(path,OUT/path.name)
        elif path.is_file() and path.name not in ('manifest.json','SHA256SUMS','README.txt'):shutil.copy2(path,OUT/path.name)
    shutil.copytree(ASSETS,OUT/'action-badges-assets')
    shutil.copy2(PREPARED/'action-badges-packed-preview.png',OUT/'action-badges-packed-preview.png')
    save(OUT/'action-badges-verification.json',report)
    save(OUT/'manifest.json',dict(manifest,status=STATUS,build_version=VERSION,files=files,source=str(SOURCE),source_files=manifest['files'],
        changed_raw_sectors=touched,action_badges=report,
        unresolved=['Fresh English badge appearance/contrast and physical-hardware checks remain pending.',
            'Existing Normal/Latent lettering remains unchanged; this is not a whole-game Japanese-image completion claim.',
            *manifest.get('unresolved',[])]))
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(
        'PRIVATE local cumulative0.1.13 - English battle action/status badges\n'
        '12 Japanese labels translated across14 descriptors after auditing all169 sprites in the battle UI atlas.\n'
        'Magic, Miss!, Guard, Stone, Poison, Paral., Status, Sleep, Up, Down, Freeze, Stance.\n'
        'Actual generated lettering alpha is packed, not reference-only. Original palette peak, native geometry and actions retained.\n'
        'One common cell conversion, one-bit alpha, thin lower-right shadow; no old font masks or word-specific scaling.\n'
        'Normal/Latent unchanged. This is not a claim that every Japanese image in the entire game is translated.\n'
        'All prior fixes retained, including Join/Equip/ending subtitles. Only14 CHAR rectangles and raw parity change.\n'
        'Use Play - Disc 2 - English Action Badges.cmd (or Disc1); SAME original E: VMUs, latest old save PortA Slot2.\n'
        'No emulator launch/input/restart, save/card/profile changes, M: output or original-disc changes.\n'
        'Offline asset/archive/disc verification complete; fresh gameplay/contrast/physical-hardware checks pending.\n'
        'Complete binaries must remain private/local. No upload, publication, tag, release or public catalog edit.\n')
    print('Private0.1.13 English battle badge pair ready:',OUT,flush=True)


def launch(disc):b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--build',action='store_true')
    p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.build:build()
    elif a.launch:launch(a.launch)
    else:print(json.dumps(prepare(a.prepare)[2],indent=2))
