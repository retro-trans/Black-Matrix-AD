import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/hd_ui'))
import reusable_atlas as atlas
import stock_atlas_pack as pack
import sh4asm
from sh4_runner import SH4
from PIL import Image


class ReusableAtlasTests(unittest.TestCase):
    @staticmethod
    def native_units(count):
        capacities=(128,32,8,2,0); parts=[]; i=0
        while count:
            size=capacities[i]
            if count>size:
                parts.append(size);count-=size
            elif count>capacities[i+1]*(4-len(parts)):
                parts.append(size);break
            else:i+=1
        return sum(parts)//2

    def size_stub(self,m,count):
        a=sh4asm.Asm(0x8C05D934)
        a.long_('last_count',0x8CF01000);a.long_('slots',128)
        a.long_('native_units',self.native_units(count))
        a.mov_l_pc('last_count',1);a.mov_l_store(4,1)
        a.mov_l_pc('slots',0);a.cmp_eq(4,0);a.bf('native')
        a.rts();a.mov_i(64,0)
        a.label('native');a.mov_l_pc('native_units',0);a.rts();a.nop()
        m.put(a.org,a.assemble())

    def machine(self, glyphs, record_index=0):
        m = SH4()
        code = atlas.build_code(); m.put(atlas.CODE, code.assemble())
        forward, reverse, _ = atlas.tables()
        m.put(atlas.FORWARD, forward); m.put(atlas.REVERSE, reverse)
        m.put(atlas.COSTS,bytes(atlas.native_units(n) for n in range(193)))
        record = atlas.vwf.LINE_RECORDS + record_index * 400
        m.write(record, len(glyphs), 2)
        m.put(record+4, struct.pack('<%dH' % len(glyphs), *glyphs))
        m.write(record+0x184, 0x8800, 2); m.write(record+0x188, 123, 4)
        m.r[4] = m.r[14] = record; m.r[15] = 0x8CFF0000
        return m, code, record

    def test_eligibility_and_fallback(self):
        for count, glyph, expected in ((1,160,1),(51,160,1),(93,160,1),(192,218,1),(57,160,1),
                                       (0,160,0),(193,160,0),(51,0xA0FF,1),
                                       (93,1000,0),(93,0xC001,0),(93,255,0)):
            with self.subTest(count=count, glyph=glyph):
                m,c,_=self.machine([glyph]*count)
                m.run(c.labels['eligible']); self.assertEqual(m.r[0],expected)

    def test_size_hook(self):
        # Expose descriptor count and units separately, as the native ABI does.
        for count, glyph, expected in ((1,160,128),(51,160,128),(93,160,128),(192,160,128),
                                       (57,160,128),(93,1000,93)):
            m,c,record=self.machine([glyph]*count)
            m.write(record+0x184,0x8000,2)
            self.size_stub(m,count);m.r[4]=count
            m.r[5:8]=[55,66,77];m.run(c.labels['size_hook'])
            self.assertEqual(m.read(0x8CF01000,4),expected)
            self.assertEqual(m.r[0],self.native_units(expected));self.assertEqual(m.r[5:8],[55,66,77])
            self.assertEqual(m.r[15],0x8CFF0000)

    def test_live_handle_slot_and_stale_fallback(self):
        f,_,_=atlas.tables()
        for count in atlas.COUNTS:
            for i in (0,count-1):
                m,c,record=self.machine([160]*(count-1)+[218],record_index=31)
                m.write(atlas.STATES+31,128,1)
                m.r[4]=123;m.r[5]=i;m.run(c.labels['slot_hook'])
                self.assertEqual(m.r[0],f[218 if i==count-1 else 160])
                self.assertEqual(m.r[15],0x8CFF0000)
        for live, handle in ((False,123),(True,456)):
            m,c,record=self.machine([160]*93)
            if not live:m.write(record+0x184,0,2)
            m.r[4]=handle;m.r[5]=27;m.run(c.labels['slot_hook'])
            self.assertEqual(m.r[0],27)

    def fill(self, glyphs, fixed=True):
        m,c,record=self.machine(glyphs)
        m.write(atlas.STATES,128 if fixed else 0,1)
        # Actual SH-4 blit stub records (glyph, slot, attr) per call.
        pointer=0x8CF00000;output=pointer+4;m.write(pointer,output,4)
        a=sh4asm.Asm(0x8C05DC42);a.long_('pointer',pointer)
        a.mov_l_pc('pointer',1);a.mov_l_at(1,2)
        for r in (4,5,6):a.mov_l_store(r,2);a.add_i(4,2)
        a.mov_l_store(2,1);a.rts();a.nop();m.put(a.org,a.assemble())
        m.run(c.labels['fill_hook'],limit=50000)
        self.assertEqual(m.r[15],0x8CFF0000)
        self.assertEqual(m.read(record,2),len(glyphs))
        return [tuple(m.read(p+4*i,4) for i in range(3))
                for p in range(output,m.read(pointer,4),12)]

    def test_fixed_contents_independent_of_line(self):
        _,reverse,_=atlas.tables();glyphs=struct.unpack('<128H',reverse)
        expected=[(g,i,0) for i,g in enumerate(glyphs)]
        self.assertEqual(self.fill([160]*93),expected)
        self.assertEqual(self.fill([218]*192),expected)

    def test_original_blit_and_attribute_controls(self):
        self.assertEqual(self.fill([160,0xC002,161,0xA0FF,1000],fixed=False),
                         [(160,0,0),(161,2,2),(1000,4,2)])

    def test_code_bounds_and_default_vwf(self):
        c=atlas.build_code();b=c.assemble()
        self.assertLessEqual(atlas.CODE+len(b),atlas.COSTS)
        self.assertLessEqual(atlas.vwf.CODE+len(atlas.vwf.build_code(c.labels['slot_hook']).assemble()),atlas.vwf.FLOAT_TAB)

    def test_budget_fallback_and_freed_record_recovery(self):
        for live, used, admitted in ((True,0,False),(False,0,True),
                                     (False,385,False),(False,384,True)):
            m,c,record=self.machine([160]*5)
            m.write(record+0x184,0x8000,2)
            self.size_stub(m,5)
            m.write(record+400+0x184,0x8800 if live else 0,2)
            m.write(record+800+0x184,0x8800 if live else 0,2)
            m.write(atlas.STATES+1,191,1);m.write(atlas.STATES+2,191,1)
            m.write(atlas.MANAGER+2,used,2)
            m.write(atlas.STATES,191,1)  # A previous occupant must be reset.
            m.r[4]=5;m.run(c.labels['size_hook'])
            self.assertEqual(bool(m.read(atlas.STATES,1)),admitted)
            self.assertEqual(m.read(0x8CF01000,4),128 if admitted else 5)
            # Changing budget later cannot retroactively switch UV mapping.
            m.write(record+0x184,0x8800,2)
            m.write(atlas.MANAGER+2,0 if not admitted else 512,2)
            m.pr=0xFFFFFFFF;m.r[4]=123;m.r[5]=3;m.run(c.labels['slot_hook'])
            self.assertEqual(m.r[0],atlas.tables()[0][160] if admitted else 3)

    def test_short_labels_bounded_extra_memory(self):
        m,c,_=self.machine([160]*1)
        used=0;extra=0;fixed_count=0
        for i in range(32):
            record=atlas.vwf.LINE_RECORDS+400*i
            m.write(record,1,2);m.write(record+4,160,2);m.write(record+0x184,0x8000,2)
            self.size_stub(m,1)
            m.pr=0xFFFFFFFF;m.r[14]=record;m.r[4]=1;m.run(c.labels['size_hook'])
            used+=m.r[0];m.write(atlas.MANAGER+2,used,2);m.write(record+0x184,0x8800,2)
            state=m.read(atlas.STATES+i,1);extra+=state&127;fixed_count+=bool(state)
            self.assertLessEqual(extra,atlas.EXTRA_BUDGET)
            self.assertLessEqual(used,512)
        self.assertEqual(fixed_count,2)

    def test_pending_large_menu_reserves_native_capacity(self):
        m,c,_=self.machine([160]*32)
        # All 32 pending records exactly fill the ORIGINAL 512-unit budget.
        # None may be enlarged, even though the used counter initially is zero.
        for i in range(32):
            r=atlas.vwf.LINE_RECORDS+400*i
            m.write(r,32,2);m.put(r+4,struct.pack('<32H',*([160]*32)))
            m.write(r+0x184,0x8000,2)
        used=0
        for i in range(32):
            r=atlas.vwf.LINE_RECORDS+400*i
            self.size_stub(m,32);m.pr=0xFFFFFFFF;m.r[4]=32;m.r[14]=r
            m.run(c.labels['size_hook'])
            self.assertEqual(m.read(atlas.STATES+i,1),0)
            used+=m.r[0];m.write(atlas.MANAGER+2,used,2);m.write(r+0x184,0x8800,2)
        self.assertEqual(used,512)

    def test_original_capacity_reference(self):
        for n in range(193):self.assertEqual(atlas.native_units(n),self.native_units(n))
        self.assertEqual([atlas.native_units(n) for n in (1,32,57,93,128,192)],
                         [1,16,32,48,64,96])

    def test_newline_maps_to_blank_without_reading_outside_lut(self):
        m,c,_=self.machine([160,0xA0FF,161])
        m.write(atlas.STATES,128,1);m.r[4]=123;m.r[5]=1
        m.run(c.labels['slot_hook']);self.assertEqual(m.r[0],0)

    def test_cells_tile_sheet_without_overlap(self):
        pixels=set()
        for slot in range(128):
            x,y=pack.cell(slot)
            self.assertLessEqual(x+32,256);self.assertLessEqual(y+16,256)
            cell={(xx,yy) for yy in range(y,y+16) for xx in range(x,x+32)}
            self.assertTrue(pixels.isdisjoint(cell));pixels.update(cell)
        self.assertEqual(len(pixels),256*256)

    def test_pack_requires_exact_mask_and_preserves_orientation(self):
        low=Image.new('L',(256,256));low.putpixel((13,29),255)
        high=low.resize((1024,1024),Image.Resampling.NEAREST)
        dump=Image.new('RGBA',low.size,(0,0,0,0))
        dump.paste((198,231,231,255),(0,0,256,256),low)
        dump=dump.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        result=pack.replacement(dump,low,high)
        self.assertIsNotNone(result)
        upright=result.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        self.assertEqual(upright.getpixel((13*4,29*4)),(198,231,231,255))
        self.assertEqual(upright.getpixel((0,0))[3],0)
        dump.putpixel((0,0),(198,231,231,255))
        self.assertIsNone(pack.replacement(dump,low,high))

    def test_stock_segments_and_blank_padding(self):
        low=Image.new('L',(256,256))
        for x,y in ((1,2),(129,2),(1,130)):low.putpixel((x,y),255)
        high=low.resize((1024,1024),Image.Resampling.NEAREST)
        parts=list(pack.segments(low,high))
        self.assertEqual([i for i,_,_ in parts],[0,1,2])
        for _,lo,hi in parts:
            self.assertEqual(lo.size,(128,128));self.assertEqual(hi.size,(512,512))
            self.assertEqual(lo.getpixel((1,2)),255)
            self.assertEqual(hi.getpixel((4,8)),255)

    def test_real_patch_guards_and_preserved_literals(self):
        src=ROOT/'build/1ST_READ.vwf.bin';orig=ROOT/'extracted/1ST_READ.BIN'
        if not src.exists() or not orig.exists():self.skipTest('local game fixture')
        before=src.read_bytes();original=orig.read_bytes()
        after,_=atlas.patch(before,original)
        self.assertEqual(len(after),len(before))
        self.assertEqual(after[0x4E0F0:0x4E100],before[0x4E0F0:0x4E100])
        self.assertEqual(after[0xE6800:0xE6900],before[0xE6800:0xE6900])
        damaged=bytearray(before);damaged[atlas.ARENA-atlas.BASE]=1
        with self.assertRaisesRegex(ValueError,'occupied'):atlas.patch(damaged,original)
        damaged=bytearray(before);damaged[atlas.SIZE_CALL-atlas.BASE]^=1
        with self.assertRaisesRegex(ValueError,'signature'):atlas.patch(damaged,original)


if __name__=='__main__':unittest.main()
