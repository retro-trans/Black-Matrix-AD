"""Derive Noto stock texture names from three pixel-verified Bizin captures.

Each captured sheet independently supplies the palette/format hash salt.
All three must agree before installing anything. Bizin textures are retained.
"""
import hashlib
import json
from pathlib import Path

import xxhash
from PIL import Image
import bizin_font
import font_style
import noto_font
import stock_atlas_pack as pack
from seed_bizin_pack import twiddled, PROFILE

CAPTURES = {0: '82c60896.png', 1: '5e95c452.png', 2: '4c68da55.png'}


def prepare(dumps, old_parts, new_parts):
    """Read-only validation. Return all replacements or raise without writes."""
    if set(old_parts) != set(CAPTURES) or set(new_parts) != set(CAPTURES):
        raise ValueError('expected three complete canonical font segments')
    pending = []
    for index, name in CAPTURES.items():
        with Image.open(dumps/name) as image:
            dump = image.convert('RGBA')
        old_low, _ = old_parts[index]
        new_low, high = new_parts[index]
        result = pack.replacement(dump, old_low, high)
        if result is None:
            raise ValueError('capture does not match every canonical Bizin pixel: '+name)
        salt = int(Path(name).stem, 16)^xxhash.xxh32(twiddled(old_low), seed=7).intdigest()
        texture = '%x.png'%(xxhash.xxh32(twiddled(new_low), seed=7).intdigest()^salt)
        pending.append((result, dict(segment=index, texture=texture, source_capture=name,
                        source_rgba_sha256=hashlib.sha256(dump.tobytes()).hexdigest(),
                        palette_format_salt=salt,
                        rgba_sha256=hashlib.sha256(result.tobytes()).hexdigest())))
    if len({m['palette_format_salt'] for _, m in pending}) != 1:
        raise ValueError('three captured stock hashes disagree on raw layout/palette')
    if len({m['texture'] for _, m in pending}) != 3:
        raise ValueError('new font texture hash collision')
    if {m['texture'] for _, m in pending} & set(CAPTURES.values()):
        raise ValueError('Noto textures would overwrite the Bizin fallback')
    return pending


def write_pack(target, pending, *, previous_hashes=None):
    # Validate every existing target before writing any replacement.
    for result, metadata in pending:
        path = target/metadata['texture']
        if path.exists():
            with Image.open(path) as image:
                pixels=image.convert('RGBA').tobytes()
                approved=(previous_hashes or {}).get(metadata['texture'],set())
                if (image.size != result.size or
                        (pixels != result.tobytes() and hashlib.sha256(pixels).hexdigest() not in approved)):
                    raise ValueError('different replacement already exists: '+str(path))
    target.mkdir(parents=True, exist_ok=True)
    for result, metadata in pending:
        result.save(target/metadata['texture'])


def install():
    noto_font.default_font()  # Require the license before any pack writes.
    old = pack.sheets(bizin_font.NATIVE, font_style.default_font())
    new = pack.sheets(noto_font.NATIVE, noto_font.default_font(), renderer=noto_font)
    parts = lambda sheets: {i: (lo, hi) for i, lo, hi in pack.segments(*sheets)}
    pending = prepare(PROFILE/'texdump/T20101M', parts(old), parts(new))
    target = PROFILE/'textures/T20101M'
    write_pack(target, pending)
    noto_font.copy_license(target)
    metadata = dict(font_sha256=noto_font.FONT_SHA256,
                    size=noto_font.SIZE, baseline=noto_font.BASELINE,
                    native_font_sha256=hashlib.sha256(noto_font.NATIVE.read_bytes()).hexdigest(),
                    textures=[m for _, m in pending],
                    verification='three Bizin captures fully matched; hash salts agree; Noto in-game check pending')
    (noto_font.OUTPUT/'stock-pack.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print('Installed Noto Regular stock textures: '+', '.join(m['texture'] for _, m in pending))
    return metadata


if __name__ == '__main__':
    install()
