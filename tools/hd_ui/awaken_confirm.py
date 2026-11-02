"""Translate the shared awakening confirmation in its existing 20-byte slot."""
import json
import struct
import shutil
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cooking
import patchline
import remaining_parameters
import native_m6x11 as engine
import hd_silver_fallback as hd
from PIL import Image

ROOT=engine.ROOT
OUT=ROOT/'build/awaken-confirm-v1'
UI=ROOT/'script/ui/awaken_confirm.tsv'
OFFSET=0x8A100
END=0x8A114
POINTER=0x7796C
WIDTH=0x778D2
ORIGINAL=bytes.fromhex('080003b0f0826f8ac190b382b982dc82b7824281')
VARIANTS={
    'hd':('reusable-atlas-noto-ui-r35-hd-silver-fallback-v1','reusable-atlas-noto-ui-r35-hd-awaken-prompt-v1'),
    'native':('reusable-atlas-noto-ui-r35-native-silver-v1','reusable-atlas-noto-ui-r35-native-silver-awaken-prompt-v1'),
}


def payload():
    text=cooking.strings(UI)['awaken']
    if text!='Awaken {ITEM}?':raise ValueError('Review changed confirmation wording/layout')
    left,right=text.split('{ITEM}')
    words=[*(patchline.to_sjis(c) for c in left),0xB003,*(patchline.to_sjis(c) for c in right)]
    data=struct.pack('<%dH'%(len(words)+1),len(words),*words)
    if len(data)!=END-OFFSET:raise ValueError('Confirmation exceeds existing slot')
    return data


def patch(data):
    if data[OFFSET:END]!=ORIGINAL:raise ValueError('Unexpected awakening confirmation')
    if data[POINTER:POINTER+4]!=struct.pack('<I',0x8C010000+OFFSET):raise ValueError('Unknown confirmation pointer')
    if data[WIDTH:WIDTH+2]!=bytes.fromhex('0874'):raise ValueError('Unknown name-length plus eight window width')
    target=bytearray(data);target[OFFSET:END]=payload()
    return bytes(target)


def build(patcher=patch,out=OUT,variants=VARIANTS,status='verified-awaken-confirm',details=None):
    OUT,VARIANTS=out,variants
    if OUT.exists() or any((ROOT/'build'/v[1]).exists() for v in VARIANTS.values()):raise ValueError('Preserve prior output')
    protected={p.name:engine.native.base.digest(p) for p in hd.TARGET.glob('*.png')}
    OUT.mkdir();reports=[]
    for mode,(src,dst) in VARIANTS.items():
        source=ROOT/'build'/src;target=ROOT/'build'/dst;target.mkdir()
        for p in source.iterdir():
            if p.is_file() and p.suffix!='.json':shutil.copy2(p,target/p.name)
        variants=[]
        for disc,folder in ((1,'disc'),(2,'disc2')):
            name=f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
            old=source/folder/name;before_sha=engine.native.base.digest(old)
            with old.open('rb') as f:
                lba,size=engine.native.inject.find(f,'1ST_READ.BIN');before=engine.native.inject._extent(f,lba,size)
            after=patcher(before)
            changes={engine.raw_offset(lba,i):b for i,(a,b) in enumerate(zip(before,after)) if a!=b}
            shutil.copytree(source/folder,target/folder);new=target/folder/name
            with new.open('r+b') as f:
                for off,value in changes.items():f.seek(off);f.write(bytes([value]))
            engine.verify_track(old,new,changes)
            with new.open('rb') as f:
                if engine.native.inject._extent(f,lba,size)!=after:raise ValueError('Executable readback failed')
            if engine.native.base.digest(old)!=before_sha:raise ValueError('Source track changed')
            for p in (source/folder).iterdir():
                if p.name!=name and engine.native.base.digest(p)!=engine.native.base.digest(target/folder/p.name):raise ValueError('Other disc component changed')
            (target/('1ST_READ.BIN' if disc==1 else '1ST_READ.disc2.BIN')).write_bytes(after)
            row=dict(mode=mode,disc=disc,changed_bytes=len(changes),track_sha256=engine.native.base.digest(new))
            variants.append(row);reports.append(row);print(mode+' disc '+str(disc)+' verified',flush=True)
        (target/'manifest.json').write_text(json.dumps(dict(status=status,variants=variants),indent=2),encoding='utf-8')
    if any(engine.native.base.digest(hd.TARGET/n)!=sha for n,sha in protected.items()):raise ValueError('Existing HD textures changed')
    detail=details if details is not None else dict(prompt='Awaken {ITEM}?',offset=OFFSET,pointer_and_width_unchanged=True,yes_no_actions_unchanged=True)
    (OUT/'build-verification.json').write_text(json.dumps(dict(status=status,variants=reports,
        **detail,original_hd_hashes=protected,live_game_verified=False),indent=2),encoding='utf-8')


def prepare_hd():
    old,silver=hd.fonts();salt,color,_=hd.records.verified_palette(hd.DUMPS)
    rows=[r for r in remaining_parameters.entries() if r['category']=='latent_name']
    if len(rows)!=57 or any(len(r['english'])>8 for r in rows):raise ValueError('Review ability-name catalog')
    # Check translated names in every actual current source disc, not just TSV.
    for src,_ in VARIANTS.values():
        for disc,folder in ((1,'disc'),(2,'disc2')):
            track=ROOT/'build'/src/folder/f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
            with track.open('rb') as f:data=engine.native.inject._extent(f,*engine.native.inject.find(f,'PARAMETA.DAT'))
            for row in rows:
                expected=remaining_parameters.encode(row);o=row['offset']
                if data[o:o+len(expected)]!=expected:raise ValueError('Actual ability name differs from catalog')
    texts={f'Awaken {name}?' for r in rows for name in (r['english'],r['english'].ljust(8))}
    pending={};coverage=[];high_font=engine.native.noto_font.outline();chars={' ':0,**engine.native.latin.charmap()}
    for text in sorted(texts):
        start=0
        for cap in hd.records.capacities(len(text)):
            size=int((cap*512)**0.5);low=Image.new('L',(size,size));noto=low.copy();high=Image.new('L',(size*4,size*4))
            for i,ch in enumerate(text[start:start+cap]):
                x,y=hd.records.pack.cell(i)
                low.paste(hd.records.indexed_cell(silver,chars[ch]),(x,y));noto.paste(hd.records.indexed_cell(old,chars[ch]),(x,y))
                high.paste(engine.native.noto_font.glyph(ch,high_font),(x*4,y*4))
            start+=cap
            art=Image.new('RGBA',high.size,color[:3]+(0,));art.putalpha(high);art=art.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            for font,sheet in (('silver',low),('noto',noto)):
                name=hd.key(sheet,salt)
                if name in pending and pending[name].tobytes()!=art.tobytes():raise ValueError('HD hash collision')
                if (hd.TARGET/name).exists():
                    with Image.open(hd.TARGET/name) as im:
                        if im.convert('RGBA').tobytes()!=art.tobytes():raise ValueError('Existing HD art differs: '+name)
                pending[name]=art;coverage.append(dict(text=text,texture=name,font=font,capacity=cap))
    pack=OUT/'pack';pack.mkdir()
    added=[]
    for name,art in pending.items():
        art.save(pack/name)
        if not (hd.TARGET/name).exists():shutil.copy2(pack/name,hd.TARGET/name);added.append(name)
        with Image.open(hd.TARGET/name) as im:
            if im.convert('RGBA').tobytes()!=art.tobytes():raise ValueError('HD readback failed')
    before=json.loads((OUT/'build-verification.json').read_text())['original_hd_hashes']
    if any(engine.native.base.digest(hd.TARGET/n)!=sha for n,sha in before.items()):raise ValueError('Prior HD texture changed')
    report=dict(status='installed-awaken-confirm',ability_records=57,expanded_texts=len(texts),
        added=added,coverage=coverage,existing_hd_preserved=len(before),live_game_verified=False)
    (OUT/'installation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(abilities=57,added=len(added),expanded_texts=len(texts))),flush=True)


if __name__=='__main__':build();prepare_hd()
