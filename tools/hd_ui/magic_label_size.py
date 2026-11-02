"""Compact only the dedicated Range/Area record, without game metric changes."""
import argparse
import json
from PIL import Image, ImageDraw, ImageFont
import xxhash
import font_record_pack as records
import interface_redraw as pack
import ui_upscale as ui

OUT = pack.ROOT / 'build/ui-magic-label-size-v1'
TEXT = 'Range     Area '
BASELINES = {'15e8ff7e.png': '145f09d58f7ad4f16c3c13f5ec28815f45e1fac2929a13f6d73ad2e8efaeea56',
             'ac6c373c.png': 'b03646794186d27ed2fb919c85c44774614ad3f0ff7ca50ed083838ef2c55233'}
SIZE = 9.0


def word_mask(word):
    font = ImageFont.truetype(str(records.noto_font.default_font()), round(SIZE * 4))
    mask = Image.new('L', (128, 64))
    ImageDraw.Draw(mask).text((4, 47), word, font=font, fill=255, anchor='ls')
    bounds = mask.getbbox()
    if bounds is None or bounds[2] > 112 or bounds[3] > 64:
        raise ValueError('Word exceeds sampled 28x16 native glyph quad')
    return mask


def preview():
    report = json.loads((OUT / 'manifest.json').read_text())
    sheet = Image.new('RGB', (600, 240), '#181818')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 8), 'Previous HD', fill='white')
    draw.text((310, 8), 'Smaller labels', fill='white')
    advances = records.noto_font.advances()
    for row_index, row in enumerate(report['textures']):
        for column, folder in enumerate(('originals', 'textures')):
            atlas = Image.open(OUT / folder / row['texture']).convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            rendered = Image.new('RGBA', (280, 64))
            pen = 0
            for i, character in enumerate(row['word']):
                x, y = records.pack.cell(row['slot'] + i)
                glyph = atlas.crop((x * 4, y * 4, x * 4 + 112, y * 4 + 64))
                rendered.alpha_composite(glyph, (pen, 0))
                pen += advances[character] * 4
            sheet.paste(rendered, (12 + column * 298, 40 + row_index * 100), rendered)
    sheet.save(OUT / 'comparison.png')


def prepare():
    if OUT.exists():
        raise ValueError('Build exists; refusing overwrite')
    metadata = json.loads((records.noto_font.OUTPUT / 'record-pack.json').read_text())
    salt = metadata['palette_format_salt']
    pending = []
    for part, (low, original_mask) in enumerate(records.record_parts(TEXT)):
        name = '%x.png' % (xxhash.xxh32(records.twiddled(low), seed=7).intdigest() ^ salt)
        previous = (ui.TARGET / name).read_bytes()
        if name not in BASELINES or pack.sha(previous) != BASELINES[name]:
            raise ValueError('Unexpected installed label record')
        with Image.open(ui.TARGET / name) as im:
            before = im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if before.getchannel('A').tobytes() != original_mask.tobytes():
            raise ValueError('Not the full canonical Range/Area record')
        # A complete short word fits the first character's sampled quad.
        # Clear the remaining letters in this dedicated record so the word
        # contracts uniformly instead of retaining full-size letter spacing.
        word, slot = ('Range', 0) if part == 0 else ('Area', 2)
        mask = Image.new('L', before.size)
        x, y = records.pack.cell(slot)
        mask.paste(word_mask(word), (x * 4, y * 4))
        after = before.copy(); after.putalpha(mask)
        pending.append((name, previous, before, after, word, slot))
    if {p[0] for p in pending} != set(BASELINES):
        raise ValueError('Unexpected record allocation')
    for folder in ('originals', 'textures', 'upright'):
        (OUT / folder).mkdir(parents=True)
    rows = []
    for name, previous, before, after, word, slot in pending:
        (OUT / 'originals' / name).write_bytes(previous)
        after.save(OUT / 'upright' / name)
        after.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(OUT / 'textures' / name)
        rows.append(dict(texture=name, original_file_sha256=BASELINES[name],
                         output_file_sha256=pack.sha((OUT / 'textures' / name).read_bytes()), word=word, slot=slot))
    report = dict(status='prepared', font_size=SIZE, previous_font_size=records.noto_font.SIZE,
                  baseline=11.75, left_inset=1, textures=rows,
                  scope='Dedicated HD Range/Area record only. Font, numbers, panel, native build and game metrics unchanged.',
                  live_game_verified=False)
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'install', 'restore'))
    args = parser.parse_args()
    print(json.dumps(prepare() if args.command == 'prepare' else pack.apply(OUT, args.command == 'restore'), indent=2))
