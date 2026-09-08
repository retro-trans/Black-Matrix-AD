"""Generator and fail-closed source patch checks; no emulator needed."""
import sys
import contextlib
import io
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/hd_ui'))
import generate as hd_generate
import patch_flycast
import font_style
from PIL import ImageFont


class HDUITests(unittest.TestCase):
    def test_legacy_fitted_generator_preserves_native_masks_and_compact_bounds(self):
        source = ROOT / 'build/FONT.vwf.bin'
        verdana = Path('C:/Windows/Fonts/verdana.ttf')
        if not source.exists() or not font_style.DEFAULT_TTF.exists() or not verdana.exists():
            self.skipTest('requires generated native font and downloaded outline fonts')
        font = ImageFont.truetype(str(font_style.default_font()), 128)
        self.assertEqual(font.getname(), ('Bizin Gothic', 'Regular'))
        previous = ImageFont.truetype(str(verdana), 128)
        data = source.read_bytes()
        changed = 0
        for character in hd_generate.latin.charmap():
            rows, low, high = hd_generate.make_glyph(
                data, character, font, ink_scale=hd_generate.COMPACT_INK_SCALE)
            old_rows, old_low, old_high = hd_generate.make_glyph(
                data, character, previous, ink_scale=hd_generate.COMPACT_INK_SCALE)
            self.assertEqual(rows, old_rows)
            self.assertEqual(low.tobytes(), old_low.tobytes())
            self.assertEqual(high.getbbox(), old_high.getbbox())
            changed += high.tobytes() != old_high.tobytes()
        self.assertGreater(changed, 50)

    def test_download_checksum_rejects_modified_asset(self):
        with self.assertRaises(ValueError):
            font_style.verified(b'not the font', font_style.FONT_SHA256)

    def test_patch_anchor_requires_exactly_one_match(self):
        self.assertEqual(patch_flycast.once('abc', 'b', 'z'), 'azc')
        for source in ['', 'bb']:
            with self.assertRaises(ValueError):
                patch_flycast.once(source, 'b', 'z')

    def test_source_patch_rejects_non_build_tree(self):
        with self.assertRaises(ValueError):
            patch_flycast.patch(ROOT / 'tools')

    def test_external_pack_upgrade_is_idempotent_and_strict(self):
        original = 'width, height, bmhd::Glyphs, unsigned(std::size(bmhd::Glyphs)), hdPixels);'
        upgraded = patch_flycast.external_pack_call(original)
        self.assertIn('bmhd::fontPack().glyphs.data()', upgraded)
        self.assertNotIn('bmhd::Glyphs', upgraded)
        self.assertEqual(patch_flycast.external_pack_call(upgraded), upgraded)
        with self.assertRaises(ValueError):
            patch_flycast.external_pack_call('unrelated code')

    def test_generator_writes_external_pack_not_compiled_glyphs(self):
        source = ROOT / 'build/FONT.vwf.bin'
        ttf = Path('C:/Windows/Fonts/verdana.ttf')
        if not source.exists() or not ttf.exists():
            self.skipTest('requires generated MFD font and local outline font')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                hd_generate.generate(source, ttf, output)
            data = (output / 'black-matrix-hd-font.bin').read_bytes()
            magic, version, scale, count, stride, digest, checksum = struct.unpack('<8s4I32sI', data[:60])
            self.assertEqual((magic, version, scale, stride), (b'BMHDFNT\0', 1, 4, 8256))
            self.assertTrue(0 < count <= 256)
            self.assertEqual(len(data), 60 + count*stride)
            self.assertEqual(zlib.crc32(data[60:]), checksum)
            self.assertEqual(digest, hd_generate.hashlib.sha256(source.read_bytes()).digest())
            self.assertFalse((output / 'glyphs.generated.h').exists())
            self.assertFalse((output / 'black-matrix-hd-font.bin.tmp').exists())

    def test_high_resolution_glyph_preserves_ink_bounds(self):
        path = ROOT / 'build/FONT.vwf.bin'
        ttf = Path('C:/Windows/Fonts/verdana.ttf')
        if not path.exists() or not ttf.exists():
            self.skipTest('requires generated MFD font and local outline font')
        data = path.read_bytes()
        font = ImageFont.truetype(str(ttf), 128)
        for character in 'AgjW019?!':
            rows, low, high = hd_generate.make_glyph(data, character, font)
            self.assertEqual(len(rows), 16)
            self.assertEqual(high.size, (128,64))
            self.assertEqual(high.getbbox(), tuple(v*4 for v in low.getbbox()))
            self.assertTrue(any(0 < v < 255 for v in high.tobytes()))

    def test_compact_font_preserves_hash_mask_and_line_alignment(self):
        path = ROOT / 'build/FONT.vwf.bin'
        ttf = Path('C:/Windows/Fonts/verdana.ttf')
        if not path.exists() or not ttf.exists():
            self.skipTest('requires local native font and outline font')
        data = path.read_bytes()
        font = ImageFont.truetype(str(ttf), 128)
        scale = hd_generate.COMPACT_INK_SCALE
        for character in hd_generate.latin.charmap():
            old_rows, old_low, old_high = hd_generate.make_glyph(data, character, font)
            rows, low, high = hd_generate.make_glyph(data, character, font, ink_scale=scale)
            self.assertEqual(rows, old_rows)
            self.assertEqual(low.tobytes(), old_low.tobytes())
            x0, y0, x1, y1 = old_high.getbbox()
            width = max(1, round((x1-x0)*scale))
            height = max(1, round((y1-y0)*scale))
            x = x0 + (x1-x0-width)//2
            y = round(32 + (y0-32)*scale)
            self.assertEqual(high.getbbox(), (x, y, x+width, y+height))
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(y+height, 64)

    def test_invalid_ink_scale_is_rejected(self):
        for scale in (0, -1, 1.1):
            with self.assertRaises(ValueError):
                hd_generate.make_glyph(b'', 'A', None, ink_scale=scale)


if __name__ == '__main__':
    unittest.main()
