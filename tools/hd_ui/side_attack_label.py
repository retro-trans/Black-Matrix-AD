"""Localize only SYSTEM sprite 7 (horizontal/side attack) in current builds."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import blunt_attack as base
import native_silver
import native_m6x11 as engine
import noto_font
from build_s_rank_layout_fix import copy_verified

ROOT, TEXTURE = base.ROOT, base.TEXTURE
OUT = ROOT/'build/side-attack-label-v1'
PACK = OUT/'pack'
RECT, INDEX = (16, 16, 32, 32), 7
DEST_SUFFIX = '-side-v1'
EXTRA_ALIASES = ()
HASH_ALL_TEXTURES = True
NATIVE = (
    's-rank-checklist-native-analog-v4',
    's-rank-checklist-native-v4',
    'analog-movement-native-v1-shop-confirm-v1',
    'reusable-atlas-noto-ui-r35-native-silver-attack-split-v1-shop-confirm-v1',
)
HD = (
    's-rank-checklist-hd-analog-v4', 's-rank-checklist-hd-v4',
    'analog-movement-hd-v1-shop-confirm-v1',
    'reusable-atlas-noto-ui-r35-hd-attack-modes-v1-shop-confirm-v1',
)


def artwork(hd=False):
    scale = 4 if hd else 1
    # One short word, centered inside the original 16x16 icon. No UV changes.
    font = ImageFont.truetype(str(noto_font.default_font() if hd else native_silver.FACE),
                              25 if hd else 12)
    box = font.getbbox('Side')
    w, h = box[2]-box[0], box[3]-box[1]
    if w > 14*scale or h > 12*scale:
        raise ValueError('Side caption does not fit')
    mask = Image.new('L' if hd else '1', (16*scale, 16*scale))
    ImageDraw.Draw(mask).text(((16*scale-w)//2-box[0], (16*scale-h)//2-box[1]),
                             'Side', font=font, fill=255)
    image = Image.new('RGBA', mask.size, (240, 168, 66, 0))
    image.putalpha(mask.convert('L'))
    return image


def patch(before):
    original = (ROOT/'extracted/SYSTEM.DAT').read_bytes()
    if base.interface.descriptors(before, TEXTURE)[INDEX] != RECT:
        raise ValueError('Side attack descriptor changed')
    old, _ = base.layers.page(before, TEXTURE)
    reference, _ = base.layers.page(original, TEXTURE)
    if old.crop(RECT).tobytes() != reference.crop(RECT).tobytes():
        raise ValueError('Side attack pixels are not the original kanji')
    after = bytearray(before)
    allowed = set()
    for off, value in base.native.encode(before, TEXTURE, RECT, artwork()):
        after[off:off+2] = value
        allowed.update((off, off+1))
    delta = {i:int(after[i]) for i in np.flatnonzero(
        np.frombuffer(before, dtype='u1') != np.frombuffer(after, dtype='u1'))}
    if not delta or not set(delta).issubset(allowed):
        raise ValueError('Out-of-tile native changes')
    return bytes(after), delta


def prepare():
    if OUT.exists():
        raise ValueError('Preserve existing preparation')
    sources = []
    aliases = set(EXTRA_ALIASES)
    for name in (*NATIVE, *HD):
        for disc in (1, 2):
            before, _, lba = base.read(ROOT/'build'/name, disc)
            after, delta = patch(before)
            low, key = base.layers.page(before, TEXTURE)
            _, new_key = base.layers.page(after, TEXTURE)
            aliases.add(key)
            if name in NATIVE:
                sources.append(dict(source=name, disc=disc, lba=lba,
                                    before_sha256=base.ui.digest(before),
                                    after_sha256=base.ui.digest(after),
                                    changed_bytes=len(delta), old_key=key, new_key=new_key))
    OUT.mkdir()
    (PACK/'textures').mkdir(parents=True)
    (PACK/'originals').mkdir()
    protected = ({p.name:base.interface.sha(p.read_bytes()) for p in base.ui.TARGET.glob('*.png')}
                 if HASH_ALL_TEXTURES else None)
    pending = {}
    for key in sorted(aliases):
        path = base.ui.TARGET/key
        if not path.exists():
            raise ValueError('Missing current HD alias: '+key)
        with Image.open(path) as image:
            high = image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        high, _ = base.interface.compose(high, [(RECT, artwork(True), 'Side')])
        pending[key] = high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    for row in sources:
        new_key = row['new_key']
        image = pending[row['old_key']]
        if new_key in pending and pending[new_key].tobytes() != image.tobytes():
            raise ValueError('Alias collision')
        if new_key not in pending and (base.ui.TARGET/new_key).exists():
            raise ValueError('New alias already exists')
        pending[new_key] = image
    textures = []
    for key, image in pending.items():
        path = base.ui.TARGET/key
        previous = path.read_bytes() if path.exists() else None
        if previous is not None:
            (PACK/'originals'/key).write_bytes(previous)
        image.save(PACK/'textures'/key)
        textures.append(dict(texture=key, original_file_sha256=base.interface.sha(previous) if previous else None,
                             output_file_sha256=base.interface.sha((PACK/'textures'/key).read_bytes())))
    (PACK/'manifest.json').write_text(json.dumps(dict(textures=textures), indent=2))
    (OUT/'preparation.json').write_text(json.dumps(dict(sources=sources, original_hd_hashes=protected), indent=2))
    before = base.read(ROOT/'build'/NATIVE[0], 1)[0]
    after, _ = patch(before)
    old, _ = base.layers.page(before, TEXTURE)
    low, _ = base.layers.page(after, TEXTURE)
    preview = Image.new('RGB', (480, 140), '#120e08')
    draw = ImageDraw.Draw(preview)
    for x, label, tile in ((12, 'Original', old.crop(RECT)),
                           (172, 'Native Silver', low.crop(RECT)),
                           (332, 'HD', artwork(True))):
        draw.text((x, 8), label, fill='white')
        tile = tile.resize((96, 96), Image.Resampling.NEAREST)
        preview.paste(tile, (x, 30), tile)
    preview.save(OUT/'preview.png')
    print('Prepared Side label; no installed files changed', flush=True)


def build():
    prepared = json.loads((OUT/'preparation.json').read_text())
    destinations = {name: name+DEST_SUFFIX for name in NATIVE}
    if any((ROOT/'build'/name).exists() for name in destinations.values()):
        raise ValueError('Preserve existing build outputs')
    reports = []
    for name, dest_name in destinations.items():
        source, dest = ROOT/'build'/name, ROOT/'build'/dest_name
        manifest = json.loads((source/'manifest.json').read_text())
        dest.mkdir()
        for path in source.iterdir():
            if path.is_file() and path.suffix != '.json' and not path.name.startswith('SYSTEM.'):
                copy_verified(path, dest/path.name)
        variants = []
        for disc in (1, 2):
            row = next(r for r in prepared['sources'] if r['source']==name and r['disc']==disc)
            before, track, lba = base.read(source, disc)
            after, delta = patch(before)
            if base.ui.digest(before)!=row['before_sha256'] or base.ui.digest(after)!=row['after_sha256']:
                raise ValueError('Source or artwork changed since preparation')
            folder = dest/('disc' if disc==1 else 'disc2')
            folder.mkdir()
            expected = next(r['track_sha256'] for r in manifest['variants'] if r['disc']==disc)
            raw = {int(engine.raw_offset(lba, i)):v for i,v in delta.items()}
            # Authenticate the entire source; patch only the tile's pixel bytes;
            # then read and hash the entire output. Source tracks remain intact.
            sha = copy_verified(track, folder/track.name, expected, raw)
            for path in track.parent.iterdir():
                if path.name != track.name:
                    copy_verified(path, folder/path.name)
            actual, _, _ = base.read(dest, disc)
            if actual != after:
                raise ValueError('SYSTEM archive readback mismatch')
            archive_name = 'SYSTEM.DAT' if disc==1 else 'SYSTEM.disc2.DAT'
            (dest/archive_name).write_bytes(after)
            result = dict(source=name, destination=dest_name, disc=disc, changed_bytes=len(delta),
                          source_track_sha256=expected, track_sha256=sha)
            variants.append(result)
            reports.append(result)
            print(name, 'disc', disc, 'verified:', len(delta), 'icon bytes only', flush=True)
        (dest/'manifest.json').write_text(json.dumps(dict(status='verified-side-attack-label',
            source_status=manifest['status'], variants=variants), indent=2))
    (OUT/'build-verification.json').write_text(json.dumps(dict(status='verified-side-attack-label',
        sources=destinations, variants=reports, live_game_verified=False,
        scope='SYSTEM sprite 7 only. Executables, gameplay, portraits, other pixels and saves unchanged.'), indent=2))


def install():
    report = json.loads((OUT/'build-verification.json').read_text())
    if report['status'] != 'verified-side-attack-label' or len(report['variants']) != 8:
        raise ValueError('Build incomplete')
    def inventory():
        return {p.name:(p.stat().st_size, p.stat().st_mtime_ns)
                for p in base.ui.TARGET.glob('*.png')}
    before = inventory()
    textures = json.loads((PACK/'manifest.json').read_text())['textures']
    changed = {r['texture'] for r in textures}
    # apply() authenticates every changed file against its preparation hash and
    # readback-verifies each output. Other files are never opened for writing.
    result = base.interface.apply(PACK)
    actual = inventory()
    if set(actual) != set(before) | changed or any(actual.get(n)!=v for n,v in before.items() if n not in changed):
        raise ValueError('Unrelated HD assets changed')
    result.update(status='installed-side-attack-label', live_game_verified=False,
                  unrelated_file_metadata_preserved=len(set(before)-changed))
    (OUT/'installation.json').write_text(json.dumps(result, indent=2))
    print(result, flush=True)


if __name__ == '__main__':
    import sys
    {'prepare':prepare, 'build':build, 'install':install}[sys.argv[1]]()
