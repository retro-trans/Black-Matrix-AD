"""Localize the captured deployment HUD with a standard Flycast PNG.

No runtime matcher or emulator changes. The exact decoded stock texture must
match before installation. Generated game-derived graphics stay in build/.
"""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import font_style

ROOT = Path(__file__).resolve().parents[2]
NAME = '240fd9ad.png'
SOURCE_HASH = '2f8e0d9e5ce13a849b064bb7e4d037657cafcbd4c2c12fa9b03282e3ea6a9dcd'
SCALE = 4
WORD_PADDING = 3  # Native pixels on each side: six pixels between word groups.
# Permit an explicit upgrade of our first generated pack, not arbitrary art.
PREVIOUS_PACK_HASHES = {
    '709901f396775790f4ee301e9802f1bae0bc71e02815281abc44bd43cef19bc1',
    'cd5aee1b01699fc7c3a76e69929bb32b83663632b9b57196f72d522254fee3bb',
    '9947609337af2358c5d9214a8121059f2035fb8019521f1a1aa6c0c332a13802',
    '44e310f3ba6f31bf816eb8c905c15449b1447242c0a339f859e27755bfab8767',
}
# Live atlas 4, individual 16px sprites 100..103 and 107..111. Keep each
# original word group meaningful rather than placing partial English words
# in reusable Japanese glyph groups. Stance sprites 104..106 are untouched.
LABELS = (((184, 80, 216, 96), 'Initial'),
          ((144, 96, 176, 112), 'Setup'),
          ((144, 112, 224, 128), 'Mode'))


def validate(native):
    if native.mode != 'RGBA' or native.size != (256, 256):
        raise ValueError('unexpected deployment HUD format')
    if hashlib.sha256(native.tobytes()).hexdigest() != SOURCE_HASH:
        raise ValueError('deployment HUD dump does not match the verified source')


def render(native, font_path):
    validate(native)
    # Untouched art remains the original pixels, replicated at an integer
    # scale. Only the nine heading tiles get newly rasterized outline text.
    high = native.resize((1024, 1024), Image.Resampling.NEAREST)
    # The sprites form one continuous heading. Rasterize one line and split
    # it across their source rectangles, never squeeze words independently.
    font = ImageFont.truetype(str(font_path), 15*SCALE)
    heading = Image.new('RGBA',(144*SCALE,16*SCALE),(255,255,255,0))
    mask = Image.new('L',heading.size)
    ImageDraw.Draw(mask).text((WORD_PADDING*SCALE,12*SCALE),'Initial Setup Mode',
                              font=font,fill=255,anchor='ls')
    heading.putalpha(mask)
    offset = 0
    for (x0, y0, x1, y1), text in LABELS:
        width, height = (x1-x0)*SCALE, (y1-y0)*SCALE
        label = heading.crop((offset,0,offset+width,height))
        offset += width
        high.paste(label, (x0*SCALE, y0*SCALE))
    return high


def check_upgrade(old, replacement):
    old = old.convert('RGBA')
    if old.size != replacement.size:
        raise ValueError('a different deployment replacement is already installed')
    if (old.tobytes() != replacement.tobytes()
            and hashlib.sha256(old.tobytes()).hexdigest() not in PREVIOUS_PACK_HASHES):
        raise ValueError('a different deployment replacement is already installed')


def install():
    profile = ROOT/'build/stock-atlas-run/data'
    source = profile/'texdump/T20101M'/NAME
    with Image.open(source) as dump:
        native = dump.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    font = font_style.default_font()
    high = render(native, font)
    target = profile/'textures/T20101M'/NAME
    # Never silently replace a different user-supplied texture pack asset.
    flipped = high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if target.exists():
        with Image.open(target) as old:
            check_upgrade(old, flipped)
    target.parent.mkdir(parents=True, exist_ok=True)
    flipped.save(target)
    font_style.copy_license(target.parent)
    (ROOT/'build/hd-ui').mkdir(parents=True, exist_ok=True)
    preview = Image.new('RGBA', (144*SCALE, 16*SCALE), 'black')
    x = 0
    for rect, _ in LABELS:
        crop = high.crop(tuple(v*SCALE for v in rect))
        preview.alpha_composite(crop, (x, 0)); x += crop.width
    preview.save(ROOT/'build/hd-ui/deployment-heading-english.png')
    metadata = dict(texture=NAME, source_rgba_sha256=SOURCE_HASH,
                    revision=5, outer_padding_native_pixels=WORD_PADDING,
                    outline_font=str(font), outline_font_sha256=font_style.FONT_SHA256,
                    font_size=15, shape='direct rasterization; no word scaling',
                    replacement_rgba_sha256=hashlib.sha256(flipped.tobytes()).hexdigest(),
                    label='Initial Setup Mode', scope='stock Flycast texture replacement only')
    (ROOT/'build/hd-ui/deployment-heading-pack.json').write_text(
        json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata


if __name__ == '__main__':
    print(json.dumps(install(), indent=2))
