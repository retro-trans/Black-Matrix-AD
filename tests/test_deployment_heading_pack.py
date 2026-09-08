import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/hd_ui'))
import deployment_heading_pack as pack


class DeploymentHeadingTests(unittest.TestCase):
    def test_unknown_texture_is_rejected(self):
        for size in ((256, 256), (128, 128)):
            with self.assertRaises(ValueError):
                pack.validate(Image.new('RGBA', size))

    def test_only_heading_tiles_change(self):
        source = ROOT/'build/stock-atlas-run/data/texdump/T20101M'/pack.NAME
        font = pack.font_style.DEFAULT_TTF
        if not source.exists() or not font.exists():
            self.skipTest('requires local captured HUD and outline font')
        with Image.open(source) as im:
            native = im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        actual = pack.render(native, font)
        expected = native.resize(actual.size, Image.Resampling.NEAREST)
        assembled = Image.new('L',(144*pack.SCALE,16*pack.SCALE))
        offset=0
        for rect, _ in pack.LABELS:
            rect = tuple(v*pack.SCALE for v in rect)
            label = actual.crop(rect)
            bounds = label.getchannel('A').getbbox()
            self.assertIsNotNone(bounds)
            assembled.paste(label.getchannel('A'),(offset,0));offset+=label.width
            actual.paste((0, 0, 0, 0), rect)
            expected.paste((0, 0, 0, 0), rect)
        self.assertEqual(actual.tobytes(), expected.tobytes())
        reference=Image.new('L',assembled.size)
        ImageDraw.Draw(reference).text((pack.WORD_PADDING*pack.SCALE,12*pack.SCALE),
            'Initial Setup Mode',font=ImageFont.truetype(str(font),15*pack.SCALE),
            fill=255,anchor='ls')
        self.assertEqual(assembled.tobytes(),reference.tobytes())
        self.assertLessEqual(assembled.getbbox()[2],assembled.width-pack.WORD_PADDING*pack.SCALE)

    def test_upgrade_does_not_overwrite_an_unrelated_pack(self):
        old = Image.new('RGBA', (1024, 1024), 'red')
        replacement = Image.new('RGBA', (1024, 1024), 'white')
        with self.assertRaises(ValueError):
            pack.check_upgrade(old, replacement)
        pack.check_upgrade(replacement, replacement)


if __name__ == '__main__':
    unittest.main()
