"""Offline HD replacements for fully verified native English fallback atlases.

Canonical atlas admission is deliberately budgeted. Text that cannot reserve
another canonical sheet still uses the original per-record texture. Match
EVERY 32x16 cell of a captured texture against this build's native Noto font,
then render the same cells with its outlines. Never change SH-4 allocation,
record contents, glyph geometry, or Japanese/unknown pixels.
"""
import hashlib
import json
from pathlib import Path

from PIL import Image
import generate
import noto_font
import stock_atlas_pack

ROOT = noto_font.ROOT


def dictionary():
    data = noto_font.NATIVE.read_bytes()
    face = noto_font.outline()
    result = {bytes(32*16): Image.new('L', (128, 64))}
    ambiguous = set()
    seen = set()
    for ch, index in noto_font.latin.charmap().items():
        # Same first-alias rule as the native font/canonical atlas generators.
        if index in seen:
            continue
        seen.add(index)
        native = generate.native_glyph(data, ch)
        high = noto_font.glyph(ch, face)
        expected = high.resize((32, 16), Image.Resampling.LANCZOS).point(
            lambda value: 255 if value >= 110 else 0)
        actual = native[1] if native is not None else Image.new('L', (32, 16))
        if expected.tobytes() != actual.tobytes():
            raise ValueError('stale native Noto font; regenerate with noto_font.py')
        if native is None:
            continue
        key = native[1].tobytes()
        if key in result and result[key].tobytes() != high.tobytes():
            ambiguous.add(key)
        else:
            result[key] = high
    for key in ambiguous:
        del result[key]
    return result


def replacement(dump, glyphs):
    if (dump.width not in (32, 64, 128, 256)
            or dump.height not in (32, 64, 128, 256)):
        return None
    native = dump.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    colors = native.getcolors(2)
    if colors is None or len(colors) != 2:
        return None
    backgrounds = [color for _, color in colors if color[3] == 0]
    if len(backgrounds) != 1:
        return None
    low = native.getchannel('A').point(lambda value: 255 if value else 0)
    high = Image.new('L', (native.width*4, native.height*4))
    nonblank = 0
    for y in range(0, native.height, 16):
        for x in range(0, native.width, 32):
            cell = low.crop((x, y, x+32, y+16))
            outline = glyphs.get(cell.tobytes())
            if outline is None:
                return None
            nonblank += cell.getbbox() is not None
            high.paste(outline, (x*4, y*4))
    # Very small mark-only textures provide weak evidence of font identity.
    if nonblank < 3:
        return None
    return stock_atlas_pack.replacement(dump, low, high)


def install(dumps=None, output=None):
    profile = ROOT/'build/stock-atlas-run/data'
    dumps = Path(dumps or profile/'texdump/T20101M')
    output = Path(output or profile/'textures/T20101M')
    glyphs = dictionary()
    pending = []
    matches = []
    for path in sorted(dumps.glob('*.png')):
        if not 1 <= len(path.stem) <= 8 or any(c not in '0123456789abcdef' for c in path.stem):
            continue
        with Image.open(path) as dump:
            high = replacement(dump, glyphs)
        if high is None:
            continue
        target = output/path.name
        matches.append(dict(texture=path.name, size=list(high.size),
                            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            installed=not target.exists()))
        if target.exists():
            with Image.open(target) as existing:
                if existing.size != high.size or existing.convert('RGBA').tobytes() != high.tobytes():
                    raise ValueError('refusing to overwrite a different texture: '+path.name)
            continue
        pending.append((target, high))
    # Validate the whole batch before installing any replacements.
    output.mkdir(parents=True, exist_ok=True)
    for target, high in pending:
        high.save(target)
    noto_font.copy_license(output)
    metadata = dict(font_sha256=noto_font.FONT_SHA256,
                    native_font_sha256=hashlib.sha256(noto_font.NATIVE.read_bytes()).hexdigest(),
                    font_size=noto_font.SIZE, output=str(output),
                    textures=matches,
                    scope='exact English native-cell matches only; no runtime allocation changes')
    report = ROOT/'build/noto-regular-font/fallback-pack.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata


if __name__ == '__main__':
    print(json.dumps(install(), indent=2))
