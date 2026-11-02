"""Replace the blunt attack-type kanji with a compact hammer pictogram."""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inject
import house_layers as layers
import interface_redraw as interface
import native_translation_parity as native
import vertical_attack_icon as vertical
import ui_upscale as ui

ROOT = ui.ROOT
OUT = ROOT / 'build/blunt-attack-v1'
PACK = OUT / 'pack'
HD = ROOT / 'build/reusable-atlas-noto-ui-r35-sin-label-case-v1'
SOURCE = ROOT / 'build/reusable-atlas-noto-ui-r35-native-sin-label-case-v1'
DEST = ROOT / 'build/reusable-atlas-noto-ui-r35-native-blunt-attack-v1'
TEXTURE, INDEX, RECT = 0x21890, 9, (48, 16, 64, 32)
NAME = '401e327b.png'


def read(root, disc):
    folder = root / ('disc' if disc == 1 else 'disc2')
    track = folder / f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
    with track.open('rb') as f:
        lba, size = inject.find(f, 'SYSTEM.DAT')
        data = inject._extent(f, lba, size)
    return data, track, lba


def native_artwork():
    return vertical.artwork(art=ROOT/'assets/ui/blunt-attack.svg')


def artwork():
    image=Image.new('RGBA',(64,64))
    image.paste(native_artwork().resize((40,40),Image.Resampling.LANCZOS),(12,4))
    return image


def patch(before):
    if interface.descriptors(before, TEXTURE)[INDEX] != RECT:
        raise ValueError('Blunt attack sprite geometry changed')
    after = bytearray(before)
    allowed = np.zeros(len(before), bool)
    for pos, value in native.encode(before, TEXTURE, RECT, native_artwork()):
        after[pos:pos+2] = value
        allowed[pos:pos+2] = True
    delta = np.frombuffer(before, dtype='u1') != np.frombuffer(after, dtype='u1')
    if np.any(delta & ~allowed) or not delta.any():
        raise ValueError('Unexpected native pixel changes')
    return bytes(after), int(delta.sum())


def prepare():
    if OUT.exists():
        raise ValueError('Refusing to overwrite prepared pack')
    before, _, _ = read(HD, 1)
    low, key = layers.page(before, TEXTURE)
    if key != NAME or interface.descriptors(before, TEXTURE)[INDEX] != RECT:
        raise ValueError('Unknown source atlas')
    path = ui.TARGET / NAME
    with Image.open(path) as im:
        base = im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    high, changed = interface.compose(base, [(RECT, artwork(), 'Blunt attack')])
    (PACK / 'textures').mkdir(parents=True)
    (PACK / 'originals').mkdir()
    shutil.copy2(path, PACK / 'originals' / NAME)
    high.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(PACK / 'textures' / NAME)
    records = []
    for disc in (1, 2):
        hd_data, _, _ = read(HD, disc)
        hd_page, hd_key = layers.page(hd_data, TEXTURE)
        if hd_key != NAME or hd_page.tobytes() != low.tobytes():
            raise ValueError('HD source differs between discs')
        source, _, _ = read(SOURCE, disc)
        source_page, _ = layers.page(source, TEXTURE)
        if source_page.crop(RECT).tobytes() != low.crop(RECT).tobytes():
            raise ValueError('Native Blunt attack differs from HD source')
        after, count = patch(source)
        (OUT / f'SYSTEM.disc{disc}.DAT').write_bytes(after)
        records.append(dict(disc=disc, source_sha256=ui.digest(source),
                            output_sha256=ui.digest(after), changed_bytes=count))
    report = dict(label='Blunt attack', sprite=INDEX, rectangle=RECT,
                  textures=[dict(texture=NAME, original_file_sha256=ui.digest(path.read_bytes()),
                                 output_file_sha256=ui.digest((PACK/'textures'/NAME).read_bytes()))],
                  archives=records, hd_changed_pixels=changed, in_game_verified=False)
    (PACK / 'manifest.json').write_text(json.dumps(report, indent=2))
    preview(before,after,high)
    print(json.dumps(report, indent=2))


def preview(before=None,after=None,high=None):
    if before is None:
        before=read(HD,1)[0]
        after=(OUT/'SYSTEM.disc1.DAT').read_bytes()
        with Image.open(PACK/'textures'/NAME) as im:
            high=im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    # Actual encoded native pixels alongside installed-size HD artwork.
    native_page, _ = layers.page(after, TEXTURE)
    preview = Image.new('RGB',(700,220),'#100b05')
    draw = ImageDraw.Draw(preview)
    for y, label, page, scale in ((8,'HD',high,4),(116,'Native',native_page,1)):
        draw.text((10,y),label+' - sword / thrust / blunt / bow / staff (unchanged)',fill='white')
        for col,index in enumerate((6,8,9,11,23)):
            rect=interface.descriptors(before,TEXTURE)[index]
            tile=page.crop(tuple(v*scale for v in rect))
            tile=tile.resize((64,64),Image.Resampling.LANCZOS if scale==4 else Image.Resampling.NEAREST)
            preview.paste(tile,(20+col*130,y+25),tile)
    preview.save(OUT/'preview.png')


def build():
    from build_activity_translations import hashfile
    from build_menu_choice_fix import verify_track
    if DEST.exists():
        raise ValueError('Refusing to overwrite native build')
    manifest = json.loads((PACK/'manifest.json').read_text())
    DEST.mkdir()
    for p in SOURCE.iterdir():
        if p.is_file() and p.suffix in ('.DAT', '.BIN'):
            shutil.copy2(p, DEST/p.name)
    records = []
    for disc in (1, 2):
        before, old, lba = read(SOURCE, disc)
        after = (OUT/f'SYSTEM.disc{disc}.DAT').read_bytes()
        row = manifest['archives'][disc-1]
        if ui.digest(before) != row['source_sha256'] or ui.digest(after) != row['output_sha256']:
            raise ValueError('Prepared/source archive changed')
        old_sha = hashfile(old)
        folder = DEST/old.parent.name
        shutil.copytree(old.parent, folder)
        new = folder/old.name
        with new.open('r+b') as f:
            for pos in range(0,len(after),2048):
                if before[pos:pos+2048] != after[pos:pos+2048]:
                    f.seek((lba-inject.HIGH_DENSITY_LBA+pos//2048)*2352+16)
                    f.write(after[pos:pos+2048])
        if read(DEST,disc)[0] != after:
            raise ValueError('Disc readback failed')
        changed = verify_track(old,new,lba,len(before))
        if changed != row['changed_bytes'] or hashfile(old) != old_sha:
            raise ValueError('Unexpected disc/source changes')
        for p in old.parent.iterdir():
            if p.name != old.name and hashfile(p) != hashfile(folder/p.name):
                raise ValueError('Other disc component changed')
        name = 'SYSTEM.DAT' if disc == 1 else 'SYSTEM.disc2.DAT'
        (DEST/name).write_bytes(after)
        records.append(dict(disc=disc, changed_bytes=changed,
                            source_track_sha256=old_sha, track_sha256=hashfile(new)))
        print('Verified native Blunt attack: Disc', disc, flush=True)
    report = dict(status='verified-native-blunt-attack', variants=records, in_game_verified=False)
    (DEST/'manifest.json').write_text(json.dumps(report, indent=2))
    (OUT/'build-verification.json').write_text(json.dumps(report, indent=2))


def install():
    import house_composite as composite
    if json.loads((OUT/'build-verification.json').read_text())['status'] != 'verified-native-blunt-attack':
        raise ValueError('Native build not verified')
    composite.OUT, composite.PACK = OUT, PACK
    composite.install()
    path = OUT/'installation.json'
    report = json.loads(path.read_text())
    report.update(status='installed-blunt-attack', label='Blunt attack', in_game_verified=False)
    path.write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    if '--preview' in sys.argv: preview()
    elif '--build' in sys.argv: build()
    elif '--install' in sys.argv: install()
    else: prepare()
