"""Translate the separately drawn inactive attack-mode kanji tiles."""
import json
import shutil
import numpy as np
from PIL import Image, ImageDraw
import attack_mode_labels as base

ui, pack = base.ui, base.pack
OUT = ui.ROOT/'build/attack-mode-split-labels-v1'
SOURCE = ui.ROOT/'build/reusable-atlas-noto-ui-r35-native-silver-attack-modes-v1'
DEST = ui.ROOT/'build/reusable-atlas-noto-ui-r35-native-silver-attack-split-v1'
RECTS = {165:(176,192,192,208), 166:(176,208,192,224),
         167:(176,224,192,240), 168:(176,240,192,256)}
PAIRS = {163:(165,167), 164:(166,168)}


def tiles(is_hd):
    result={}
    for whole,(left,right) in PAIRS.items():
        art=base.artwork(whole,is_hd)
        result[left]=art.crop((0,0,64,64))
        result[right]=art.crop((64,0,128,64))
    return result


def patch_char(before):
    original=ui.japanese_audit.archive(1,'CHAR.DAT')
    native,_=base.layers.page(original,base.TEXTURE)
    page,_=base.layers.page(before,base.TEXTURE)
    rows=pack.descriptors(before,base.TEXTURE)
    after=bytearray(before);allowed=set()
    for index,art in tiles(False).items():
        rect=RECTS[index]
        if rows[index]!=rect or page.crop(rect).tobytes()!=native.crop(rect).tobytes():
            raise ValueError('Unexpected split-label source')
        for offset,value in base.native.encode(before,base.TEXTURE,rect,art):
            after[offset:offset+2]=value;allowed.update((offset,offset+1))
    changed=np.flatnonzero(np.frombuffer(before,dtype='u1')!=np.frombuffer(after,dtype='u1')).tolist()
    if not changed or not set(changed).issubset(allowed):raise ValueError('Unexpected native change')
    return bytes(after)


def prepare():
    if OUT.exists() or DEST.exists():raise ValueError('Preserve existing build')
    protected={p.name:pack.sha(p.read_bytes()) for p in ui.TARGET.glob('*.png')}
    old_manifest=json.loads((base.OUT/'manifest.json').read_text())
    alias_names=[base.NAME,'93c943b4.png']
    pending={}
    for name in alias_names:
        expected=next(r['output_file_sha256'] for r in old_manifest['textures'] if r['texture']==name)
        if protected[name]!=expected:raise ValueError('Current battle atlas changed: '+name)
        with Image.open(ui.TARGET/name) as im:before=im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        high,_=pack.compose(before,[(RECTS[i],art,str(i)) for i,art in tiles(True).items()])
        pending[name]=high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    OUT.mkdir();DEST.mkdir()
    for folder in ('textures','originals'):(OUT/folder).mkdir()
    # Preserve current native discs, creating a new isolated revision.
    for path in SOURCE.iterdir():
        if path.is_file() and path.suffix!='.json':shutil.copy2(path,DEST/path.name)
    tracks=[]
    for disc,folder in ((1,'disc'),(2,'disc2')):
        filename=f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
        old=SOURCE/folder/filename;new=DEST/folder/filename
        source_hash=base.engine.native.base.digest(old)
        with old.open('rb') as f:
            lba,size=base.inject.find(f,'CHAR.DAT');before=base.inject._extent(f,lba,size)
        after=patch_char(before)
        delta=np.flatnonzero(np.frombuffer(before,dtype='u1')!=np.frombuffer(after,dtype='u1')).tolist()
        changes={base.engine.raw_offset(lba,i):after[i] for i in delta}
        shutil.copytree(SOURCE/folder,DEST/folder)
        with new.open('r+b') as f:
            for sector in sorted({i//2048 for i in delta}):
                f.seek(base.engine.raw_offset(lba,sector*2048));f.write(after[sector*2048:(sector+1)*2048])
        base.engine.verify_track(old,new,changes)
        with new.open('rb') as f:
            if base.inject._extent(f,lba,size)!=after:raise ValueError('Native archive readback failed')
        if base.engine.native.base.digest(old)!=source_hash:raise ValueError('Source disc changed')
        for path in (SOURCE/folder).iterdir():
            if path.name!=filename and base.engine.native.base.digest(path)!=base.engine.native.base.digest(DEST/folder/path.name):
                raise ValueError('Other track changed')
        (DEST/('CHAR.DAT' if disc==1 else 'CHAR.disc2.DAT')).write_bytes(after)
        (OUT/f'CHAR-disc{disc}-before.bin').write_bytes(before)
        _,old_key=base.layers.page(before,base.TEXTURE)
        _,new_key=base.layers.page(after,base.TEXTURE)
        if old_key!='93c943b4.png':raise ValueError('Unexpected native atlas key')
        if new_key in pending and pending[new_key].tobytes()!=pending[base.NAME].tobytes():raise ValueError('Alias collision')
        pending[new_key]=pending[base.NAME]
        tracks.append(dict(disc=disc,changed_bytes=len(delta),source_sha256=source_hash,
                           output_sha256=base.engine.native.base.digest(new),old_key=old_key,new_key=new_key))
        print('Native disc',disc,'verified',flush=True)
    entries=[]
    for name,art in pending.items():
        path=ui.TARGET/name;prior=path.read_bytes() if path.exists() else None
        if prior is not None and name not in alias_names:raise ValueError('New alias already exists')
        if prior is not None:shutil.copy2(path,OUT/'originals'/name)
        art.save(OUT/'textures'/name)
        entries.append(dict(texture=name,original_file_sha256=pack.sha(prior) if prior else None,
                            output_file_sha256=pack.sha((OUT/'textures'/name).read_bytes())))
    if {p.name:pack.sha(p.read_bytes()) for p in ui.TARGET.glob('*.png')}!=protected:raise ValueError('Profile changed during preparation')
    report=dict(status='prepared-attack-mode-split-labels',textures=entries,original_hd_hashes=protected,
                split_tiles=RECTS,pairs=PAIRS,tracks=tracks,live_game_verified=False,
                diagnosis='Inactive choices draw separate glyphs 165/167 and 166/168, not full-word sprites 163/164.',
                scope='Only four inactive split attack-selector tiles; all other texture pixels, portraits, fonts, gameplay and saves preserved.')
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2))
    (DEST/'manifest.json').write_text(json.dumps(dict(status='verified-attack-mode-split-labels',tracks=tracks),indent=2))
    preview=Image.new('RGB',(560,210),'#b4b0a0');draw=ImageDraw.Draw(preview)
    for col,is_hd in enumerate((True,False)):
        draw.text((10+col*280,8),'HD' if is_hd else 'Native Silver',fill='black')
        parts=tiles(is_hd)
        for row,(whole,(left,right)) in enumerate(PAIRS.items()):
            for j,i in enumerate((left,right)):
                preview.paste(parts[i],(10+col*280+j*64,35+row*80),parts[i])
    preview.save(OUT/'preview.png')
    print('Prepared split-label translation',flush=True)


def install():
    report=json.loads((OUT/'manifest.json').read_text())
    before={p.name:pack.sha(p.read_bytes()) for p in ui.TARGET.glob('*.png')}
    if before!=report['original_hd_hashes']:raise ValueError('Profile changed before installation')
    result=pack.apply(OUT)
    expected=dict(before);expected.update({r['texture']:r['output_file_sha256'] for r in report['textures']})
    if {p.name:pack.sha(p.read_bytes()) for p in ui.TARGET.glob('*.png')}!=expected:raise ValueError('Unexpected installed changes')
    result.update(status='installed-attack-mode-split-labels',other_textures_preserved=len(before)-2,live_game_verified=False)
    (OUT/'installation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':
    import sys
    install() if 'install' in sys.argv else prepare()
