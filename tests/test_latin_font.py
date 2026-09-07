"""Font-trial bounds, unchanged Japanese data, and measured VWF advances."""
import sys
import unittest
import string
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import latin
import fontdump
import vwf
import widths


class LatinFontTests(unittest.TestCase):
    def test_bizin_trial_bounds_and_unmodified_glyphs(self):
        source=Path(latin.ROOT)/'extracted/FONT.BIN'
        if not source.exists(): self.skipTest('requires original local font')
        data, mapping, clipped, baseline=latin.build()
        self.assertFalse(clipped)
        self.assertEqual(baseline,12)
        self.assertEqual(latin.WIDE,1.5)
        widest=0
        for index in set(mapping.values()):
            points=[(x,y) for x,y,v in fontdump.pixels(data,0,index) if v]
            self.assertTrue(points)
            span=max(x for x,y in points)-min(x for x,y in points)+1
            widest=max(widest,span)
            self.assertLessEqual(span,23)
            self.assertTrue(all(1<=x<24 and 0<=y<16 for x,y in points))
            self.assertEqual(widths.advance(data,index),span+1)
        self.assertEqual(widest,20)
        letter_widths=[]
        for ch in string.ascii_letters:
            lo,hi=widths.extents(data,mapping[ch])
            letter_widths.append(hi-lo+1)
        self.assertEqual(max(letter_widths),13)
        h_points=[(x,y) for x,y,v in fontdump.pixels(data,0,mapping['H']) if v]
        self.assertEqual((max(x for x,y in h_points)-min(x for x,y in h_points)+1,
                          max(y for x,y in h_points)-min(y for x,y in h_points)+1),(12,12))
        body_points=[(x,y) for ch in string.ascii_letters+string.digits
                     for x,y,v in fontdump.pixels(data,0,mapping[ch]) if v]
        self.assertEqual((min(y for x,y in body_points),max(y for x,y in body_points)),(0,15))
        # The next larger integer size cannot fit the alphabet; it must fall
        # back to 19px instead of clipping letters or resizing only Y.
        larger,_,lost,_=latin.build(size=20)
        self.assertFalse(lost)
        self.assertEqual(data,larger)
        # The storage cap must not rescale any glyph in the default profile.
        uncapped,_,_,_=latin.build(max_width=None)
        self.assertEqual(data,uncapped)
        original=source.read_bytes()
        self.assertEqual(len(data),len(original))
        restored=bytearray(data)
        for index in set(mapping.values()):
            offset=fontdump.HEADER+index*fontdump.GLYPH
            restored[offset:offset+fontdump.GLYPH]=original[offset:offset+fontdump.GLYPH]
        self.assertEqual(restored,original)

    def test_installed_font_and_vwf_metrics_agree(self):
        path=Path(latin.ROOT)/'build/FONT.vwf.bin'
        if not path.exists(): self.skipTest('requires generated font')
        data=path.read_bytes()
        advances,bearings=vwf.metrics(None)
        for index in set(latin.charmap().values()):
            lo,hi=widths.extents(data,index)
            self.assertEqual(advances[index],hi-lo+2)
            self.assertEqual(bearings[index],lo)


if __name__=='__main__': unittest.main()
