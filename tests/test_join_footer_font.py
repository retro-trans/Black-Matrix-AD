import json
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools/hd_ui'),str(ROOT/'tools'),str(ROOT/'tests')]
import join_footer_font as fix
from test_equip_fallback_font import EquipFontTests


class JoinFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=(fix.SOURCE/'1ST_READ.BIN').read_bytes()
        cls.after,cls.delta=fix.patch_exe(cls.before,2)
        cls.raw=fix.equip.CAPTURE.read_bytes()
        cls.record=fix.equip.vwf.LINE_RECORDS+7*400
        cls.node=0x8c245d70;cls.window=fix.equip.vwf.WIN_TAB+29*28

    cpu=EquipFontTests.cpu
    run_draw=EquipFontTests.run_draw
    test_existing_fourteen_footers_identical=EquipFontTests.test_all_fourteen_existing_footer_outputs_are_byte_identical
    test_equip_all_forty_cells=EquipFontTests.test_every_cell_uses_full_font_correct_metrics_and_row_height
    test_equip_tints_and_fades=EquipFontTests.test_disabled_tint_selected_white_and_fade_survive
    test_equip_guards=EquipFontTests.test_guard_rejections_retain_original_native_fallback
    test_equip_donor_lifetime=EquipFontTests.test_donor_lifetime_revalidated_and_no_redraw_drift

    def join_cpu(self,change=None):
        def setup(m):
            m.write(self.node+4,1,4);m.write(self.node+8,67,2)
            x,y,xx,yy=fix.RECT
            m.put(self.node+148,struct.pack('<8H',x,y,xx,y,xx,yy,x,yy))
            m.put(self.node+132,struct.pack('<4I',*(0xffffffff,)*4))
            if change:change(m)
        return self.cpu(0,setup)

    def test_join_uses_exact_font_uv_size_advances_gold_and_baseline(self):
        m=self.join_cpu();self.run_draw(m)
        self.assertEqual(len(self.submitted),4)
        self.assertEqual(self.calls,['geometry']+['bind','blend','colour','submit']*4)
        pen=0;origin=struct.unpack('<2f',struct.pack('<2I',m.read(self.window+8,4),m.read(self.window+12,4)))
        for tile,ch in zip(self.submitted,'Join'):
            gid=fix.f.prior.latin.charmap()[ch];slot=m.read(fix.equip.atlas.FORWARD+gid,1)
            self.assertNotEqual(struct.unpack_from('<I',tile,4)[0],1)
            self.assertEqual(struct.unpack_from('<H',tile,8)[0],slot)
            u,v=slot%8*32,(slot%32//8)*64+1
            self.assertEqual(struct.unpack_from('<8H',tile,148),(u,v,u+32,v,u+32,v+48,u,v+48))
            x,y=origin[0]+pen,origin[1]+2.5
            self.assertEqual(struct.unpack_from('<8f',tile,84),(x,y,x+16,y,x+16,y+12,x,y+12))
            self.assertEqual(struct.unpack_from('<4I',tile,116),(0xffffb828,)*4)
            pen+=m.read(fix.equip.metrics.SMALL_ADV+gid,1)
        self.assertLessEqual(pen+16,64)  # Original32-source-pixel sprite is X2.
        self.assertEqual(m.read(self.node+4,4),1);self.assertEqual(m.read(self.node+8,2),67)

    def test_join_repeat_draw_and_fallback_guards(self):
        m=self.join_cpu();self.run_draw(m);first=self.submitted.copy();self.run_draw(m)
        self.assertEqual(self.submitted[4:],first)
        for change in (lambda m:m.write(self.node+148,65,2),
                       lambda m:m.put(self.node+132,struct.pack('<4I',*(0xff444444,)*4)),
                       lambda m:m.put(fix.equip.atlas.STATES,bytes(32)),
                       lambda m:m.write(self.node+8,66,2),
                       lambda m:m.write(fix.f.MANAGER+3264+2,130,2)):
            m=self.join_cpu(change);tile=self.run_draw(m)
            self.assertEqual(len(self.submitted),1)
            self.assertEqual(struct.unpack_from('<I',tile,4)[0],1)
            self.assertEqual(self.calls,['bind','blend','colour','geometry','submit'])

    def test_per_disc_patch_guards_and_exact_scope(self):
        for disc,name in ((1,'1ST_READ.disc1.BIN'),(2,'1ST_READ.BIN')):
            before=(fix.SOURCE/name).read_bytes();after,delta=fix.patch_exe(before,disc)
            self.assertEqual(len(after),len(before));self.assertEqual(len(delta),278)
            allowed=set(range(fix.f.MAIN-fix.BASE,fix.f.MAIN_END-fix.BASE))|set(range(fix.ROW-fix.BASE,fix.ROW_END-fix.BASE))
            self.assertTrue(set(delta)<=allowed)
            with self.assertRaises(ValueError):fix.patch_exe(after,disc)
            # Equip helper, its literals, all neighboring code and existing
            # fourteen table rows must remain exact.
            for lo,hi in ((fix.equip.GATE,fix.equip.GATE_END),(fix.equip.OWNER,fix.equip.OWNER_END),
                          (fix.equip.PEN,fix.equip.PEN+len(fix.equip.pen())),(0x8c0f2500,fix.f.FIND),
                          (fix.f.GEOMETRY,fix.f.GEOMETRY_END),(fix.f.TABLE,fix.f.TABLE_END),
                          (0x8c0f30c0,0x8c0f3100),(0x8c0f4680,0x8c0f46e0)):
                self.assertEqual(before[lo-fix.BASE:hi-fix.BASE],after[lo-fix.BASE:hi-fix.BASE])

    def test_launch_mock_and_complete_delivery(self):
        with patch.object(fix.b.domina.zero,'launch') as launch:
            for disc in (1,2):
                fix.launch(disc);self.assertEqual(launch.call_args.args,(disc,))
                self.assertEqual(launch.call_args.kwargs['build'],fix.OUT)
                self.assertEqual(launch.call_args.kwargs['settings']['rend.Resolution'],'1440')
        if not (fix.OUT/'manifest.json').exists():return
        raw=(fix.OUT/'manifest.json').read_bytes();raw.decode('ascii');report=json.loads(raw.decode('gbk'))
        self.assertEqual(report['build_version'],'0.1.12');self.assertFalse(report['gameplay_verified'])
        for disc,name in ((1,'1ST_READ.disc1.BIN'),(2,'1ST_READ.BIN')):
            expected,_=fix.patch_exe((fix.SOURCE/name).read_bytes(),disc)
            self.assertEqual((fix.OUT/name).read_bytes(),expected)
            self.assertEqual(fix.b.READER.read_file(fix.b.track(fix.OUT,disc),'1ST_READ.BIN')[0],expected)
            self.assertEqual(fix.b.sha(expected),report['disc_executable_sha256'][str(disc)])


if __name__=='__main__':unittest.main()
