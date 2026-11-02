"""Localize the captured deployment HUD with a standard Flycast PNG.

No runtime matcher or emulator changes. The exact decoded stock texture must
match before installation. Generated game-derived graphics stay in build/.
"""
import hashlib
import json
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import font_style
import noto_font
import cooking

ROOT = Path(__file__).resolve().parents[2]
NAME = '240fd9ad.png'
SOURCE_HASH = '2f8e0d9e5ce13a849b064bb7e4d037657cafcbd4c2c12fa9b03282e3ea6a9dcd'
SCALE = 4
WORD_PADDING = 3  # Outer padding in source-space pixels.
# Permit an explicit upgrade of our first generated pack, not arbitrary art.
PREVIOUS_PACK_HASHES = {
    '709901f396775790f4ee301e9802f1bae0bc71e02815281abc44bd43cef19bc1',
    'cd5aee1b01699fc7c3a76e69929bb32b83663632b9b57196f72d522254fee3bb',
    '9947609337af2358c5d9214a8121059f2035fb8019521f1a1aa6c0c332a13802',
    '44e310f3ba6f31bf816eb8c905c15449b1447242c0a339f859e27755bfab8767',
    'ec34a8dd329ad6f60376fe419beadcc643304b7d6a7ab76371f8a4fa4a92ea90',
    '85e229a2754f09319b6317bd96fe8a0298325f239c143c4a8f9daa52f3f865d9',
    '81c3d05309d42d7bde5b2fd64d32038a994c544fb862fa5399ebfea926eae9b8',
}
# Original atlas regions. Stance sprites 104..106 are untouched.
LABELS = (((184, 80, 216, 96), 'Initial'),
          ((144, 96, 176, 112), 'Setup'),
          ((144, 112, 224, 128), 'Mode'))
# Verified in setup-heading-before.ram: 32px screen quads advance by 28px,
# then 24px for the last katakana tiles. Source-space offsets divide by 2.
# Do NOT concatenate nine 16px crops: that duplicates ink in the overlaps.
TILES = ((100, 184, 80, 0), (101, 200, 80, 14),
         (102, 144, 96, 28), (103, 160, 96, 42),
         (107, 144, 112, 56), (108, 160, 112, 70),
         (109, 176, 112, 84), (110, 192, 112, 96),
         (111, 208, 112, 108))
WIDTH = 124
# move-banner-before.ram: whole 32x16 sprites, not overlapping glyph tiles.
# Sprite 160 is live at X64..128/Y208..224; PVX 0x508060 also identifies 161.
ACTIONS = ((160, (192,208,224,224), 'move'),
           (161, (192,224,224,240), 'attack'))
ACTION_SIZE, ACTION_BASELINE = 10, 11.75
UI = ROOT/'script/ui/action_headings.tsv'
THINKING = (144,80,184,96)  # CHAR PVX 0x860, sprite 99: one 40x16 quad.
THINKING_COLOR = (180,49,16)


def thinking_label(font_path):
    word=cooking.strings(UI)['thinking']
    face=ImageFont.truetype(str(font_path),9*SCALE)
    width=face.getlength(word)
    probe=Image.new('RGBA',(256,128))
    ImageDraw.Draw(probe).text(((40*SCALE-width)/2,11.75*SCALE),word,
        font=face,fill=THINKING_COLOR+(255,),anchor='ls',
        stroke_width=SCALE,stroke_fill=(16,0,0,255))
    box=probe.getbbox()
    if not box or box[0]<0 or box[2]>40*SCALE or box[3]>=16*SCALE:
        raise ValueError('Thinking indicator exceeds original 40x16 sprite')
    return probe.crop((0,0,40*SCALE,16*SCALE))


def action_labels(font_path):
    """Center full words at one smaller em; never squeeze individual letters."""
    face = ImageFont.truetype(str(font_path), round(ACTION_SIZE*SCALE))
    words = cooking.strings(UI)
    result = []
    for sprite, rect, key in ACTIONS:
        word = words[key]
        width = face.getlength(word)
        if not word or width > 30*SCALE:
            raise ValueError('battle banner exceeds original 32x16 sprite')
        # Probe before cropping, so bounds checks cannot conceal clipped ink.
        probe = Image.new('L', (512,128))
        ImageDraw.Draw(probe).text(((32*SCALE-width)/2, ACTION_BASELINE*SCALE),
                                  word, font=face, fill=255, anchor='ls')
        box = probe.getbbox()
        if box is None or box[0] < SCALE or box[2] > 31*SCALE or box[3] >= 16*SCALE:
            raise ValueError('battle banner ink exceeds original 32x16 sprite')
        result.append((sprite, rect, probe.crop((0,0,32*SCALE,16*SCALE))))
    return result


def typography(font_path):
    if Path(font_path).resolve() == noto_font.DEFAULT_TTF.resolve():
        return noto_font.SIZE, noto_font.BASELINE
    return 13, 11.5


def heading(font_path,text='Initial Setup Mode'):
    size, baseline = typography(font_path)
    font = ImageFont.truetype(str(font_path), round(size*SCALE))
    mask = Image.new('L', (WIDTH*SCALE, 16*SCALE))
    ImageDraw.Draw(mask).text((WORD_PADDING*SCALE, baseline*SCALE),
                             text, font=font, fill=255, anchor='ls')
    box = mask.getbbox()
    if box is None or box[2] > (WIDTH-WORD_PADDING)*SCALE or box[3] >= mask.height:
        raise ValueError('deployment heading does not fit verified sprite footprint')
    return mask


def compose(high):
    """Reconstruct the actual overlapping sprite positions, not atlas order."""
    result = Image.new('RGBA', (WIDTH*SCALE, 16*SCALE))
    for _, x, y, offset in TILES:
        tile = high.crop((x*SCALE, y*SCALE, (x+16)*SCALE, (y+16)*SCALE))
        result.alpha_composite(tile, (offset*SCALE, 0))
    return result


def validate(native):
    if native.mode != 'RGBA' or native.size != (256, 256):
        raise ValueError('unexpected deployment HUD format')
    if hashlib.sha256(native.tobytes()).hexdigest() != SOURCE_HASH:
        raise ValueError('deployment HUD dump does not match the verified source')


def render(native, font_path):
    validate(native)
    # Untouched art remains the original pixels, replicated at an integer
    # scale. Only heading tiles, action captions and Thinking get outlines.
    high = native.resize((1024, 1024), Image.Resampling.NEAREST)
    line = Image.new('RGBA', (WIDTH*SCALE, 16*SCALE), (255,255,255,0))
    line.putalpha(heading(font_path))
    for i, (_, x, y, offset) in enumerate(TILES):
        end = TILES[i+1][3] if i+1 < len(TILES) else WIDTH
        label = Image.new('RGBA', (16*SCALE, 16*SCALE), (255,255,255,0))
        label.paste(line.crop((offset*SCALE, 0, end*SCALE, 16*SCALE)), (0,0))
        high.paste(label, (x*SCALE, y*SCALE))
    for _, rect, mask in action_labels(font_path):
        label = Image.new('RGBA', mask.size, (255,255,255,0))
        label.putalpha(mask)
        high.paste(label, (rect[0]*SCALE, rect[1]*SCALE))
    high.paste(thinking_label(font_path),(THINKING[0]*SCALE,THINKING[1]*SCALE))
    return high


def check_upgrade(old, replacement):
    old = old.convert('RGBA')
    if old.size != replacement.size:
        raise ValueError('a different deployment replacement is already installed')
    if (old.tobytes() != replacement.tobytes()
            and hashlib.sha256(old.tobytes()).hexdigest() not in PREVIOUS_PACK_HASHES):
        raise ValueError('a different deployment replacement is already installed')


def install(font_style_name='noto-regular'):
    profile = ROOT/'build/stock-atlas-run/data'
    source = profile/'texdump/T20101M'/NAME
    with Image.open(source) as dump:
        native = dump.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if font_style_name not in ('bizin', 'noto-regular'):
        raise ValueError('unknown heading font style')
    style = noto_font if font_style_name == 'noto-regular' else font_style
    font = style.default_font()
    high = render(native, font)
    target = profile/'textures/T20101M'/NAME
    # Never silently replace a different user-supplied texture pack asset.
    flipped = high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if target.exists():
        with Image.open(target) as old:
            check_upgrade(old, flipped)
    target.parent.mkdir(parents=True, exist_ok=True)
    flipped.save(target)
    style.copy_license(target.parent)
    (ROOT/'build/hd-ui').mkdir(parents=True, exist_ok=True)
    preview = Image.new('RGBA', (WIDTH*SCALE, 16*SCALE), 'black')
    preview.alpha_composite(compose(high))
    preview.save(ROOT/'build/hd-ui/deployment-heading-english.png')
    # Reconstruct the captured background/text quads in corrected screen aspect:
    # background 64x24 source -> 128x24 game; text 32x16 -> 64x16 game.
    banners = Image.new('RGBA', (128*SCALE, 2*48*SCALE), 'black')
    background = high.crop((40*SCALE,232*SCALE,104*SCALE,256*SCALE))
    background = background.resize((128*SCALE,48*SCALE), Image.Resampling.NEAREST)
    for row, (_,rect,_) in enumerate(ACTIONS):
        tile = high.crop(tuple(v*SCALE for v in rect))
        tile = tile.resize((64*SCALE,32*SCALE), Image.Resampling.NEAREST)
        banners.alpha_composite(background, (0,row*48*SCALE))
        banners.alpha_composite(tile, (32*SCALE,(row*48+8)*SCALE))
    banners.save(ROOT/'build/hd-ui/battle-banners-english.png')
    thinking=Image.new('RGBA',(160,64),'black')
    thinking.alpha_composite(thinking_label(font))
    thinking.save(ROOT/'build/hd-ui/thinking-label-english.png')
    metadata = dict(texture=NAME, source_rgba_sha256=SOURCE_HASH,
                    revision=8, outer_padding_native_pixels=WORD_PADDING,
                    outline_font=str(font), outline_font_sha256=style.FONT_SHA256,
                    font_size=typography(font)[0], sprite_offsets=[t[3] for t in TILES],
                    shape='direct rasterization; transparent overlap tails; no word scaling',
                    replacement_rgba_sha256=hashlib.sha256(flipped.tobytes()).hexdigest(),
                    label='Initial Setup Mode',
                    action_labels={k:cooking.strings(UI)[k] for _,_,k in ACTIONS},
                    action_font_size=ACTION_SIZE, action_baseline=ACTION_BASELINE,
                    action_sprites=[dict(sprite=i,uv=rect) for i,rect,_ in ACTIONS],
                    thinking=dict(label=cooking.strings(UI)['thinking'],sprite=99,uv=THINKING,
                                  size=9,color=THINKING_COLOR),
                    scope='stock Flycast texture replacement only')
    (ROOT/'build/hd-ui/deployment-heading-pack.json').write_text(
        json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font-style', choices=('bizin', 'noto-regular'), default='noto-regular')
    print(json.dumps(install(parser.parse_args().font_style), indent=2))
