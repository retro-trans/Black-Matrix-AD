"""Silver embedded fallback with hash aliases preserving existing HD font art."""
import argparse
import json
import hashlib
import shutil
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import native_silver
import font_record_pack as records

engine=native_silver.engine
native=engine.native
ROOT=engine.ROOT
SOURCE=ROOT/'build/reusable-atlas-noto-ui-r35-ritual-heading-v1'
OUT=ROOT/'build/reusable-atlas-noto-ui-r35-hd-silver-fallback-v1'
REVIEW=ROOT/'build/hd-silver-fallback-v1'
TARGET=ROOT/'build/stock-atlas-run/data/textures/T20101M'
DUMPS=ROOT/'build/stock-atlas-run/data/texdump/T20101M'


def fonts():
    with native_silver.configured() as e:_,silver,_=e.font_and_widths()
    return native.noto_font.NATIVE.read_bytes(),silver


def glyph_dictionary():
    old,new=fonts();face=native.noto_font.outline()
    high={};low={};seen=set()
    for ch,index in {' ':0,**native.latin.charmap()}.items():
        if index in seen:continue
        seen.add(index)
        a=records.indexed_cell(old,index);b=records.indexed_cell(new,index)
        outline=Image.new('L',(128,64)) if ch==' ' else native.noto_font.glyph(ch,face)
        high[outline.tobytes()]=(a,b,ch)
        low[a.tobytes()]=(a,b,ch)
    return high,low


@lru_cache(maxsize=4)
def morton_order(size):
    y,x=np.indices((size,size));order=np.zeros((size,size),dtype=np.int64)
    for bit in range(size.bit_length()-1):
        order|=((y>>bit)&1)<<(2*bit)|((x>>bit)&1)<<(2*bit+1)
    return np.argsort(order.ravel())


def key(im,salt):
    if im.width!=im.height or im.width not in (32,64,128,256):raise ValueError('Invalid sheet dimensions')
    values=np.array(im,dtype=np.uint8).ravel()[morton_order(im.width)]
    if values.max()>3:raise ValueError('Invalid glyph palette indices')
    raw=(values[0::2]|(values[1::2]<<4)).tobytes()
    return '%x.png'%(records.xxhash.xxh32(raw,seed=7).intdigest()^salt)


def from_high(path,dictionary):
    with Image.open(path) as f:im=f.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if im.width!=im.height or im.width not in (128,256,512,1024):return None
    old=Image.new('L',(im.width//4,im.height//4));new=old.copy()
    alpha=im.getchannel('A')
    for y in range(0,im.height,64):
        for x in range(0,im.width,128):
            found=dictionary.get(alpha.crop((x,y,x+128,y+64)).tobytes())
            if found is None:return None
            a,b,_=found;old.paste(a,(x//4,y//4));new.paste(b,(x//4,y//4))
    return old,new


def from_capture(path,dictionary):
    with Image.open(path) as f:im=f.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if im.width!=im.height or im.width not in (32,64,128,256):return None
    palette=[(0,0,0,0),(198,231,231,255),(156,156,156,255),(74,74,74,255)]
    pixels=np.array(im);indices=np.zeros(pixels.shape[:2],dtype=np.uint8);matched=np.zeros(indices.shape,dtype=bool)
    for i,color in enumerate(palette):
        mask=np.all(pixels==color,axis=2)
        if i==0:mask=pixels[:,:,3]==0
        indices[mask]=i;matched|=mask
    if not matched.all():return None
    old=Image.fromarray(indices);new=old.copy();changed=False
    for y in range(0,im.height,16):
        for x in range(0,im.width,32):
            found=dictionary.get(old.crop((x,y,x+32,y+16)).tobytes())
            if found:
                a,b,ch=found
                new.paste(b,(x,y));changed|=a.tobytes()!=b.tobytes()
    return (old,new) if changed else None


def audit():
    if (REVIEW/'installation.json').exists():
        raise ValueError('Installed alias audit is immutable; use a new revision for future text packs')
    REVIEW.mkdir(exist_ok=True)
    high,low=glyph_dictionary()
    salt,_,_=records.verified_palette(DUMPS)
    special=special_sheets(salt)
    rows=[];unknown=[];mismatches=[]
    for path in sorted(TARGET.glob('*.png')):
        source='high-outline'
        pair=special.get(path.name)
        if pair is not None:source='verified-record-template'
        else:pair=from_high(path,high)
        if pair is None and (DUMPS/path.name).exists():
            pair=from_capture(DUMPS/path.name,low);source='capture'
        if pair is None:
            unknown.append(path.name);continue
        a,b=pair
        if key(a,salt)!=path.name:
            mismatches.append(path.name);continue
        rows.append(dict(old=path.name,new=key(b,salt),source=source,sha256=native.base.digest(path)))
    report=dict(salt=salt,aliases=rows,unknown=unknown,mismatches=mismatches)
    (REVIEW/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(verified=len(rows),unknown=len(unknown),mismatches=len(mismatches)),indent=2))
    return report


def special_sheets(salt):
    # These HD sheets intentionally use custom typography, so their original
    # native pixels must come from exact record templates, not HD image shape.
    old,new=fonts();chars={' ':0,**native.latin.charmap()};templates={}
    groups=[[0,i] for i in range(487,492)]
    groups += [[i,tail] for i in range(492,497) for tail in (0,chars['Y'])]
    for ids in groups:
        sheets=[]
        for data in (old,new):
            sheet=Image.new('L',(32,32))
            for i,index in enumerate(ids):sheet.paste(records.indexed_cell(data,index),(0,i*16))
            sheets.append(sheet)
        templates[key(sheets[0],salt)]=tuple(sheets)
    from magic_label_size import TEXT
    offset=0
    for capacity in records.capacities(len(TEXT)):
        size=int((capacity*512)**0.5);sheets=[]
        for data in (old,new):
            sheet=Image.new('L',(size,size))
            for i,ch in enumerate(TEXT[offset:offset+capacity]):
                sheet.paste(records.indexed_cell(data,chars[ch]),records.pack.cell(i))
            sheets.append(sheet)
        templates[key(sheets[0],salt)]=tuple(sheets);offset+=capacity
    return templates


LEGACY_SHEETS={'4c68da55.png','5e95c452.png','82c60896.png',
               'b867fb36.png','d0c4f66b.png','e01b63db.png'}


def validate_report(report):
    if report['mismatches']:raise ValueError('Unverified texture hashes')
    # Remaining monochrome font sheets must be the six preserved legacy font
    # atlases. All current Noto canonical sheets must have verified aliases.
    current=json.loads((ROOT/'build/noto-regular-font/stock-pack.json').read_text())
    aliased={r['old'] for r in report['aliases']}
    if not {r['texture'] for r in current['textures']}<=aliased:raise ValueError('Canonical HD font not covered')
    for name in report['unknown']:
        with Image.open(TARGET/name) as im:
            if im.convert('RGB').getcolors(3) is not None and name not in LEGACY_SHEETS:
                raise ValueError('Unclassified font texture: '+name)
    keys={}
    for row in report['aliases']:
        if native.base.digest(TARGET/row['old'])!=row['sha256']:raise ValueError('HD source changed since audit')
        target=TARGET/row['new']
        if target.exists() and native.base.digest(target)!=row['sha256']:raise ValueError('Existing hash collision')
        if row['new'] in keys and keys[row['new']]!=row['sha256']:raise ValueError('Alias hash collision')
        keys[row['new']]=row['sha256']


def install():
    report=json.loads((REVIEW/'audit.json').read_text());validate_report(report)
    manifest=json.loads((OUT/'manifest.json').read_text())
    if manifest['status']!='verified-hd-silver-discs':raise ValueError('Disc build not verified')
    for path,digest in manifest['protected'].items():
        if native.base.digest(ROOT/path)!=digest:raise ValueError('Protected source differs')
    added=[]
    for row in report['aliases']:
        destination=TARGET/row['new']
        if not destination.exists():shutil.copy2(TARGET/row['old'],destination);added.append(row['new'])
    for row in report['aliases']:
        if native.base.digest(TARGET/row['new'])!=row['sha256']:raise ValueError('Alias readback mismatch')
    for path,digest in manifest['protected'].items():
        if native.base.digest(ROOT/path)!=digest:raise ValueError('Existing file changed')
    installation=dict(status='installed-hd-silver-fallback',added=added,alias_count=len(report['aliases']),
                      unchanged_art_and_legacy_sheets=report['unknown'],live_game_verified=False)
    (REVIEW/'installation.json').write_text(json.dumps(installation,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=installation['status'],added=len(added),verified_aliases=len(report['aliases'])),indent=2))


def build_discs():
    if OUT.exists():raise ValueError('Preserve existing output')
    old,font=fonts()
    protected={str(p.relative_to(ROOT)):native.base.digest(p) for p in SOURCE.rglob('*') if p.is_file()}
    protected.update({str(p.relative_to(ROOT)):native.base.digest(p) for p in TARGET.glob('*.png')})
    OUT.mkdir();discs=[]
    for path in SOURCE.iterdir():
        if path.is_file() and path.suffix!='.json':shutil.copy2(path,OUT/path.name)
    for disc,folder in ((1,'disc'),(2,'disc2')):
        shutil.copytree(SOURCE/folder,OUT/folder)
        name=f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
        before_track,after_track=SOURCE/folder/name,OUT/folder/name
        with before_track.open('rb') as f:
            lba,size=native.inject.find(f,'SYSTEM.DAT');before=native.inject._extent(f,lba,size)
        off=native.FONT_OFFSET
        if before[off:off+len(old)]!=old:raise ValueError('HD source font not Noto')
        after=before[:off]+font+before[off+len(old):]
        changes={engine.raw_offset(lba,i):b for i,(a,b) in enumerate(zip(before,after)) if a!=b}
        with after_track.open('r+b') as f:
            for pos,value in changes.items():f.seek(pos);f.write(bytes([value]))
        engine.verify_track(before_track,after_track,changes)
        with after_track.open('rb') as f:
            if native.inject._extent(f,lba,size)!=after:raise ValueError('HD font readback failed')
        (OUT/('SYSTEM.DAT' if disc==1 else 'SYSTEM.disc2.DAT')).write_bytes(after)
        discs.append(dict(disc=disc,changed_bytes=len(changes),track_sha256=native.base.digest(after_track)))
        print('Verified HD disc '+str(disc),flush=True)
    for path,digest in protected.items():
        if native.base.digest(ROOT/path)!=digest:raise ValueError('Protected source changed')
    (OUT/'FONT.bin').write_bytes(font)
    report=dict(status='verified-hd-silver-discs',discs=discs,executable_unchanged=True,
                metrics='Original HD/Noto spacing preserved for HD replacement compatibility',
                protected=protected,live_game_verified=False)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


def review_unknown():
    report=json.loads((REVIEW/'audit.json').read_text())
    names=[]
    for name in report['unknown']:
        with Image.open(TARGET/name) as im:
            if im.convert('RGB').getcolors(3) is not None:names.append(name)
    sheet=Image.new('RGB',(1200,((len(names)+3)//4)*190),'#302820');draw=ImageDraw.Draw(sheet)
    for i,name in enumerate(names):
        im=Image.open(TARGET/name).convert('RGBA');im.thumbnail((290,160))
        x=(i%4)*300;y=(i//4)*190
        draw.text((x+5,y+3),name,fill='white');sheet.paste(im,(x+5,y+22),im)
    sheet.save(REVIEW/'unknown-font-review.png')
    return names


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build-discs',action='store_true');parser.add_argument('--review-unknown',action='store_true');parser.add_argument('--install',action='store_true')
    args=parser.parse_args()
    if args.build_discs:build_discs()
    elif args.install:install()
    elif args.review_unknown:print(review_unknown())
    else:audit()
