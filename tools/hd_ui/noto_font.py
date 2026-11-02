"""Noto Sans CJK JP Regular, sharing natural outline metrics with the game.

The user requested a smaller version after the 14.75px in-game trial.
Use a 13.25px em (about 10% smaller), 11.75px baseline and 1px inset.
No individual glyph is stretched or squeezed.
Run with --fetch to obtain the pinned OFL assets; builds never fetch silently.
"""
import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import bizin_font

ROOT = bizin_font.ROOT
latin = bizin_font.latin
fontdump = bizin_font.fontdump
vwf = bizin_font.vwf
ASSETS = ROOT/'assets/fonts/noto-sans-cjk-jp'
DEFAULT_TTF = ASSETS/'NotoSansCJKjp-Regular.otf'
LICENSE = ASSETS/'LICENSE.txt'
FONT_SHA256 = '68a3fc98800b2a27b371f2fb79991daf3633bd89309d4ffaa6946fd587f375b5'
LICENSE_SHA256 = '6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2'
URL = 'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Japanese/NotoSansCJKjp-Regular.otf'
LICENSE_URL = 'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE'
OUTPUT = ROOT/'build/noto-regular-font'
NATIVE = OUTPUT/'FONT.bin'
SIZE, SCALE, BASELINE, LEFT = 13.25, 4, 11.75, 1
# The game draws into 640x240 and displays at 640x480. Compensate its 2x Y
# stretch in GAME geometry/advances, not by distorting the outline textures.
DISPLAY_X = 2


def verified(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Noto Regular asset checksum mismatch')
    return data


def default_font():
    verified(DEFAULT_TTF.read_bytes(), FONT_SHA256)
    verified(LICENSE.read_bytes(), LICENSE_SHA256)
    return DEFAULT_TTF


def copy_license(output):
    default_font()
    shutil.copyfile(LICENSE, Path(output)/'Noto-CJK-LICENSE.txt')


def fetch():
    pending = []
    for path, url, digest in ((DEFAULT_TTF, URL, FONT_SHA256),
                              (LICENSE, LICENSE_URL, LICENSE_SHA256)):
        if path.exists():
            verified(path.read_bytes(), digest)
            continue
        with urllib.request.urlopen(url, timeout=60) as response:
            pending.append((path, verified(response.read(), digest)))
    for path, data in pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return default_font()


def outline(path=None):
    source = default_font()
    if path is not None and Path(path).resolve() != source.resolve():
        raise ValueError('Noto renderer requires the pinned Regular face')
    return ImageFont.truetype(str(source), round(SIZE*SCALE))


def glyph(character, font=None):
    font = font or outline()
    # Measure actual ink with generous margins, not a bbox containing advance
    # whitespace. Check negative bearings as well as right/bottom clipping.
    probe = Image.new('L', (256, 256))
    ImageDraw.Draw(probe).text((32, 128), character, font=font, fill=255, anchor='ls')
    box = probe.getbbox()
    if box and (box[0]-32+LEFT*SCALE < 0 or box[1]-128+BASELINE*SCALE < 0
                or box[2]-32+LEFT*SCALE > 128 or box[3]-128+BASELINE*SCALE > 64):
        raise ValueError('Noto glyph exceeds its atlas cell: '+repr(character))
    return probe.crop((32-LEFT*SCALE, 128-BASELINE*SCALE,
                       32-LEFT*SCALE+128, 128-BASELINE*SCALE+64))


def advances(font=None):
    font = font or outline()
    return {ch: round(font.getlength(ch)/SCALE) for ch in {' ': 0, **latin.charmap()}}


def game_advances(font=None):
    return {ch: width*DISPLAY_X for ch, width in advances(font).items()}


def build():
    face = outline()
    data = bytearray((ROOT/'extracted/FONT.BIN').read_bytes())
    seen = set()
    for ch, index in latin.charmap().items():
        if index in seen:
            continue
        seen.add(index)
        mask = glyph(ch, face).resize((32, 16), Image.Resampling.LANCZOS)
        record = latin.blank_record()
        for y in range(16):
            for x in range(32):
                if mask.getpixel((x, y)) >= 110:
                    latin.set_pixel(record, x, y, 1)
        start = fontdump.HEADER + index*fontdump.GLYPH
        data[start:start+fontdump.GLYPH] = record
    OUTPUT.mkdir(parents=True, exist_ok=True)
    NATIVE.write_bytes(data)
    metadata = dict(name='Noto Sans CJK JP Regular', font_sha256=FONT_SHA256,
                    size=SIZE, baseline=BASELINE, left=LEFT, advance=game_advances(face),
                    outline_advance=advances(face), display_x_compensation=DISPLAY_X,
                    native_threshold=110, shape='direct rasterization; no per-glyph scaling')
    (OUTPUT/'metrics.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return bytes(data), metadata


def patch_metrics(exe):
    widths = game_advances()
    seen = set()
    for ch, index in {' ': 0, **latin.charmap()}.items():
        if index in seen:
            continue
        seen.add(index)
        exe[vwf.ADV_TAB-vwf.LOAD_BASE+index] = widths[ch]
        exe[vwf.BEAR_TAB-vwf.LOAD_BASE+index] = 0


def preview():
    # Same sample panel, now at the user's requested smaller size. Display
    # aspect is corrected in the game, so this square-pixel preview is valid.
    from compare_noto import panel
    face = outline()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for native, name in ((False, 'text-preview.png'), (True, 'native-preview.png')):
        panel(face, BASELINE*SCALE, LEFT*SCALE, native).save(OUTPUT/name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    if parser.parse_args().fetch:
        print(fetch())
    else:
        build()
        preview()
