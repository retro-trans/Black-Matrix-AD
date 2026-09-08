import struct
import sys
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/hd_ui'))
import bizin_font as font
import stock_atlas_pack
import fontdump
import latin
import vwf
from sh4_runner import SH4


class BizinFontTests(unittest.TestCase):
    def setUp(self):
        if not font.font_style.DEFAULT_TTF.exists():self.skipTest('download Bizin Gothic first')
        self.face=font.outline()

    def test_every_glyph_is_unscaled_outline_on_one_baseline(self):
        for ch in latin.charmap():
            expected=Image.new('L',(128,64))
            ImageDraw.Draw(expected).text((4,50),ch,font=self.face,fill=255,anchor='ls')
            actual=font.glyph(ch,self.face)
            self.assertEqual(actual.tobytes(),expected.tobytes())
        for ch in 'il':
            box=font.glyph(ch,self.face).getbbox()
            self.assertGreaterEqual(box[2]-box[0],20) # old fitted version was 7
        self.assertEqual(font.advances(self.face)['i'],8)
        self.assertEqual(font.advances(self.face)['l'],8)
        self.assertEqual(font.advances(self.face)[' '],8)

    def test_native_fallback_matches_hd_and_preserves_other_glyphs(self):
        source=ROOT/'extracted/FONT.BIN'
        if not source.exists():self.skipTest('local font fixture')
        data,_=font.build();original=source.read_bytes();seen=set()
        for ch,index in latin.charmap().items():
            if index in seen:continue
            seen.add(index)
            expected=font.glyph(ch,self.face).resize((32,16),Image.Resampling.LANCZOS)
            for y in range(16):
                for x in range(32):
                    self.assertEqual(bool(fontdump.pixel(data,0,index,x,y)),expected.getpixel((x,y))>=110)
        for index in range(fontdump.COUNT):
            if index not in seen:
                start=fontdump.HEADER+index*fontdump.GLYPH
                self.assertEqual(data[start:start+fontdump.GLYPH],original[start:start+fontdump.GLYPH])
        lo,hi=stock_atlas_pack.sheets(font.NATIVE,font.font_style.DEFAULT_TTF)
        forward,_,chars=stock_atlas_pack.atlas.tables()
        for ch in 'ilWg':
            index=chars[ch];x,y=stock_atlas_pack.cell(forward[index])
            self.assertEqual(hi.crop((x*4,y*4,x*4+128,y*4+64)).tobytes(),font.glyph(ch,self.face).tobytes())

    def test_metrics_only_touch_mapped_glyphs_and_drive_game_pen(self):
        data=bytearray([33])*0xE7464;before=bytes(data);font.patch_metrics(data)
        indices=set(latin.charmap().values())|{0}
        allowed={base-vwf.LOAD_BASE+i for base in (vwf.ADV_TAB,vwf.BEAR_TAB) for i in indices}
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(before,data)) if a!=b))
        cpu=SH4();cpu.put(vwf.LOAD_BASE,data)
        code=vwf.build_code(ui_fixes=True,natural_font=True)
        self.assertLessEqual(vwf.CODE+len(code.assemble()),vwf.FLOAT_TAB)
        cpu.put(vwf.CODE,code.assemble());cpu.put(vwf.FLOAT_TAB,vwf.float_table())
        ctx,node=0x8C100000,0x8C101000
        cpu.write(ctx,22,4);cpu.write(ctx+8,14,2)
        cpu.write(vwf.WIN_TAB+22*28,0x8009,2)
        chars=[latin.charmap()[c] for c in 'illwill']
        cpu.write(vwf.LINE_RECORDS,len(chars),2)
        cpu.put(vwf.LINE_RECORDS+4,struct.pack('<7H',*chars))
        cpu.write(vwf.LINE_RECORDS+0x184,0x8000,2)
        cpu.write(vwf.LINE_RECORDS+0x188,123,4)
        # Clear other live-record flags from the synthetic filler.
        for i in range(1,32):cpu.write(vwf.LINE_RECORDS+400*i+0x184,0,2)
        for i in range(7):
            cpu.r[8:13]=[ctx,i,i,123,node];cpu.r[15]=0x8C00F000;cpu.pr=0xFFFFFFFF
            cpu.run(code.labels['vwf_adjust'])
            self.assertEqual(cpu.read(node+12,4),int.from_bytes(struct.pack('<f',i*8),'little'))
        # The Yes/No selector must no longer compress a 16px font cell to 11px.
        cpu.write(ctx+8,3,2);cpu.write(ctx+10,2,2)
        cpu.put(node+16,struct.pack('<f',0));cpu.put(node+32,struct.pack('<f',14))
        cpu.write(node+150,0x40,2);cpu.write(node+158,0x78,2)
        cpu.pr=0xFFFFFFFF;cpu.run(code.labels['uv_fix'])
        self.assertEqual(cpu.read(node+16,4),0)
        self.assertEqual(cpu.read(node+32,4),int.from_bytes(struct.pack('<f',16),'little'))
        self.assertEqual(cpu.read(node+158,2),0x80)


if __name__=='__main__':unittest.main()
