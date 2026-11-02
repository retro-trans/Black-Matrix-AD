import struct
import sys
import unittest
import json
from unittest.mock import patch
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools/hd_ui'),str(ROOT/'tools'),str(ROOT/'tests')]
import equip_fallback_font as fix
import ending_subtitle_build as previous
import equip_font_build as delivery
import s_rank_budget as checklist
import status_instant_v3 as status
import remaining_parameters
import equipment_catalog
from sh4_runner import SH4


class EquipFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=(previous.OUT/'1ST_READ.BIN').read_bytes()
        cls.after,cls.delta=fix.patch_exe(cls.before,2)
        cls.raw=fix.CAPTURE.read_bytes()
        cls.record=fix.vwf.LINE_RECORDS+7*400
        cls.node=0x8c245d70
        cls.window=fix.vwf.WIN_TAB+29*28

    def cpu(self,cell=0,change=None):
        m=SH4();m.put(m.BASE,self.raw);m.put(fix.BASE,self.after)
        off=fix.atlas.STATES-m.BASE;m.put(fix.atlas.STATES,self.raw[off:off+32])
        words=[m.read(self.record+4+i*2,2) for i in range(40)]
        x=sum(m.read(fix.vwf.ADV_TAB+g,1) for g in words[cell//8*8:cell])
        y=2+cell//8*14
        m.write(self.node+8,cell,2)
        m.put(self.node+12,struct.pack('<8f',x,y,x+28,y,x+28,y+16,x,y+16))
        m.r[8:15]=[0x80000000+i*16 for i in range(7)]
        m.r[13]=self.window;m.r[14]=self.node;m.r[4]=self.node;m.r[15]=0x8c00e000
        m.fr[15]=fix.footer.fbits(.01)
        self.submitted=[];self.calls=[]
        if change:change(m)
        def trap(kind):
            def cb(cpu):
                self.calls.append(kind);n=cpu.r[4]
                if kind=='geometry':
                    local=struct.unpack('<8f',bytes(cpu.mem[n-m.BASE+12:n-m.BASE+44]))
                    origin=struct.unpack('<2f',bytes(cpu.mem[self.window-m.BASE+8:self.window-m.BASE+16]))
                    cpu.put(n+84,struct.pack('<8f',*(p+origin[i%2] for i,p in enumerate(local))))
                elif kind=='colour':cpu.put(n+116,bytes(cpu.mem[n-m.BASE+132:n-m.BASE+148]))
                elif kind=='submit':
                    self.assertEqual(cpu.r[5],4);self.assertEqual(cpu.fr[4],cpu.fr[15])
                    self.assertEqual([cpu.read(n+i,4) for i in (0,4,8)],[n+16,n+48,n+80])
                    self.submitted.append(bytes(cpu.mem[n-m.BASE-68:n-m.BASE+100]))
                for i in range(8):cpu.r[i]=0x12340000+i
                for i in range(6):cpu.fr[i]=fix.footer.fbits(-100-i)
            return cb
        for addr,kind in ((0x8c06cad0,'geometry'),(0x8c06c914,'bind'),
                          (0x8c06c984,'blend'),(0x8c06c9cc,'colour'),(0x8c0a53c8,'submit')):
            m.traps[addr]=trap(kind)
        return m

    def run_draw(self,m):
        m.r[4]=m.r[14]
        before=bytes(m.mem);regs=m.r[8:].copy();fr=m.fr[12:].copy();m.pr=0xffffffff
        m.run(fix.footer.MAIN)
        self.assertEqual(m.r[8:],regs);self.assertEqual(m.fr[12:],fr)
        changed=np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(m.mem,'u1'))
        self.assertTrue(all(0x8c00dc00-m.BASE<=i<0x8c00e000-m.BASE or
            self.node-m.BASE+84<=i<self.node-m.BASE+132 for i in changed))
        self.assertEqual(m.read(fix.atlas.MANAGER+2,2),407)
        self.assertEqual(m.read(self.record+0x188,4),15)
        self.assertEqual(m.read(fix.atlas.STATES+7,1),0)
        return self.submitted[-1]

    def test_every_cell_uses_full_font_correct_metrics_and_row_height(self):
        for cell in range(40):
            with self.subTest(cell=cell):
                m=self.cpu(cell);tile=self.run_draw(m)
                gid=m.read(self.record+4+2*cell,2)
                slot=m.read(fix.atlas.FORWARD+gid,1)
                self.assertNotEqual(struct.unpack_from('<I',tile,4)[0],15)
                self.assertEqual(struct.unpack_from('<H',tile,8)[0],slot)
                u,v=slot%8*32,(slot%32//8)*64+1
                self.assertEqual(struct.unpack_from('<8H',tile,148),(u,v,u+32,v,u+32,v+48,u,v+48))
                x=m.read(self.window+8,4);x=struct.unpack('<f',struct.pack('<I',x))[0]
                x+=sum(m.read(fix.metrics.SMALL_ADV+m.read(self.record+4+2*j,2),1) for j in range(cell//8*8,cell))
                oy=struct.unpack('<f',struct.pack('<I',m.read(self.window+12,4)))[0]
                y=oy+2+cell//8*14
                self.assertEqual(struct.unpack_from('<8f',tile,84),(x,y,x+16,y,x+16,y+12,x,y+12))
                self.assertEqual(tile[132:148],m.mem[self.node-m.BASE+132:self.node-m.BASE+148])
                self.assertEqual(tile[116:132],tile[132:148])
                self.assertEqual(self.calls,['geometry','bind','blend','colour','submit'])

    def test_disabled_tint_selected_white_and_fade_survive(self):
        for tint in (0xffffffff,0xff4c4c4c,0x60303030,0x00000000):
            m=self.cpu(10,lambda c:c.put(self.node+132,struct.pack('<4I',*(tint,)*4)))
            tile=self.run_draw(m)
            self.assertEqual(struct.unpack_from('<4I',tile,116),(tint,)*4)

    def test_guard_rejections_retain_original_native_fallback(self):
        changes=[lambda m:m.write(fix.CONTEXT+8,9,2),lambda m:m.write(fix.CONTEXT+10,4,2),
            lambda m:m.write(fix.CONTEXT+14,0,2),lambda m:m.write(fix.CONTEXT,28,4),
            lambda m:m.write(self.window+4,39,4),lambda m:m.write(self.record,39,2),
            lambda m:m.write(self.record+0x184,0x8000,2),lambda m:m.write(self.node+8,40,2),
            lambda m:m.write(self.record+4+30*2,0x141,2),
            lambda m:m.write(self.record+4+10*2,90,2),
            lambda m:m.put(fix.atlas.STATES,bytes(32)),
            lambda m:m.put(fix.footer.MANAGER,bytes(80*3264))]
        # Clearing all states removes donors, but does not alter this fallback's state.
        for change in changes:
            m=self.cpu(10,change);tile=self.run_draw(m)
            self.assertEqual(struct.unpack_from('<I',tile,4)[0],15)
            self.assertEqual(self.calls,['bind','blend','colour','geometry','submit'])

    def test_donor_lifetime_revalidated_and_no_redraw_drift(self):
        m=self.cpu(10);a=self.run_draw(m);self.assertEqual(self.run_draw(m),a)
        m.put(fix.atlas.STATES,bytes(32));b=self.run_draw(m)
        self.assertEqual(struct.unpack_from('<I',b,4)[0],15)
        self.assertEqual(struct.unpack_from('<I',a,4)[0],12)

    def test_already_canonical_owner_is_not_reinterpreted(self):
        m=self.cpu(10);m.write(fix.atlas.STATES+7,128,1);m.pr=0xffffffff
        m.run(fix.footer.MAIN)
        self.assertEqual(struct.unpack_from('<I',self.submitted[-1],4)[0],15)
        self.assertEqual(self.calls,['bind','blend','colour','geometry','submit'])

    def test_fixed_item_name_fields_have_no_structural_newlines_and_metrics_are_bounded(self):
        # Generic eligible() accepts structural newlines for dialogue, but
        # these exact Equip rows concatenate immutable padded8-cell names.
        data=delivery.b.READER.read_file(delivery.b.track(delivery.SOURCE,2),'PARAMETA.DAT')[0]
        offsets=[r['offset'] for r in remaining_parameters.entries() if r['category']=='item_name']
        offsets.extend(r['name_offset']-2 for r in equipment_catalog.entries())
        self.assertGreater(len(offsets),250)
        for offset in offsets:
            count,*words=struct.unpack_from('<9H',data,offset)
            self.assertLessEqual(count,8)
            self.assertFalse({10,13,0xa0ff}&set(words))
        differences=[self.after[fix.vwf.ADV_TAB-fix.BASE+g]-self.after[fix.metrics.SMALL_ADV-fix.BASE+g]
            for g in range(256) if self.after[fix.atlas.FORWARD-fix.BASE+g]<128]
        self.assertGreaterEqual(min(differences),0)
        self.assertLess(max(differences)*7,fix.vwf.NTAB)

    def test_guarded_per_disc_patch_and_allocators_untouched(self):
        for disc,path in ((1,previous.OUT/'1ST_READ.disc1.BIN'),(2,previous.OUT/'1ST_READ.BIN')):
            before=path.read_bytes();after,delta=fix.patch_exe(before,disc)
            self.assertEqual(delta,self.delta);self.assertEqual(len(after),len(before))
            allowed={i for a,b in fix.blocks().items() for i in range(a-fix.BASE,a-fix.BASE+len(b))}
            self.assertTrue(set(delta)<=allowed)
            for lo,hi in ((fix.atlas.CODE,fix.atlas.END),(fix.vwf.CODE,fix.vwf.FLOAT_TAB),
                          (0x8c0f4680,0x8c0f46e0),(0x8c0f31e0,0x8c0f327c)):
                self.assertEqual(after[lo-fix.BASE:hi-fix.BASE],before[lo-fix.BASE:hi-fix.BASE])
            self.assertEqual(fix.atlas.POOL_CEILING,448)
            with self.assertRaises(ValueError):fix.patch_exe(after,disc)

    def test_neighboring_status_and_checklist_code_untouched_and_executable(self):
        # Exercise the current checklist directly, without missing historical
        # September fixtures required by test_s_rank_budget.
        for lo,hi in ((0x8c0f2200,fix.OWNER),(fix.OWNER_END,fix.PEN),
                      (fix.PEN_END,fix.footer.FIND),(checklist.BUDGET,fix.GATE)):
            self.assertEqual(self.after[lo-fix.BASE:hi-fix.BASE],self.before[lo-fix.BASE:hi-fix.BASE])
        driver=status.v2.driver_hook(status.DRIVER,closing=True)
        self.assertEqual(self.after[status.DRIVER-fix.BASE:status.DRIVER-fix.BASE+len(driver)],driver)
        allocator=checklist.allocator()
        self.assertEqual(self.after[checklist.BUDGET-fix.BASE:checklist.BUDGET-fix.BASE+len(allocator)],allocator)
        table={};p=checklist.s.TABLE-fix.BASE
        while group:=int.from_bytes(self.after[p:p+2],'little'):
            table[group]=int.from_bytes(self.after[p+6:p+8],'little');p+=8
        for group in [0,*table,0x7fff]:
            m=SH4();m.put(m.BASE,self.raw);m.put(fix.BASE,self.after)
            m.write(checklist.s.GROUP,(group-1)&65535,2);m.r[15]=0x8c00e000;m.pr=0xffffffff;calls=[]
            def allocate(cpu):calls.append(cpu.r[4]);cpu.r[0]=0
            m.traps[checklist.ALLOCATOR]=allocate;m.run(checklist.BUDGET)
            self.assertEqual(calls,[checklist.node_budget(table.get(group,32))])

    def test_all_fourteen_existing_footer_outputs_are_byte_identical(self):
        tables=self.before[fix.footer.TABLE-fix.BASE:fix.footer.TABLE-fix.BASE+160]+self.before[0xe30c0:0xe3100]
        for off in range(0,len(tables),16):
            row=tables[off:off+16]
            with self.subTest(index=row[0]):
                def footer_node(m):
                    m.write(self.node+4,1,4);m.write(self.node+8,row[0],2)
                    x,y,xx,yy=struct.unpack_from('<4H',row,8)
                    m.put(self.node+148,struct.pack('<8H',x,y,xx,y,xx,yy,x,yy))
                    m.put(self.node+132,struct.pack('<4I',*(0xffffffff,)*4))
                m=self.cpu(0,footer_node);self.run_draw(m);after=self.submitted.copy()
                for addr in (fix.footer.MAIN,fix.footer.GEOMETRY):
                    size=len(fix.blocks()[addr]);m.put(addr,self.before[addr-fix.BASE:addr-fix.BASE+size])
                self.submitted=[];self.run_draw(m)
                self.assertEqual(after,self.submitted)

    def test_launch_mock_reuses_existing_profile_without_executing(self):
        with patch.object(delivery.b.domina.zero,'launch') as launch:
            for disc in (1,2):
                delivery.launch(disc);args=launch.call_args
                self.assertEqual(args.args,(disc,));self.assertEqual(args.kwargs['build'],delivery.OUT)
                self.assertEqual(args.kwargs['status'],delivery.STATUS)
                self.assertEqual(args.kwargs['settings']['rend.Resolution'],'1440')

    def test_complete_delivery_identities_and_gbk_safe_manifest(self):
        if not (delivery.OUT/'manifest.json').exists():self.skipTest('Candidate not complete')
        raw=(delivery.OUT/'manifest.json').read_bytes();raw.decode('ascii');report=json.loads(raw.decode('gbk'))
        self.assertEqual(report['build_version'],'0.1.11');self.assertEqual(report['status'],delivery.STATUS)
        self.assertFalse(report['gameplay_verified']);self.assertEqual(report['equip']['additional_texture_units'],0)
        for disc,name in ((1,'1ST_READ.disc1.BIN'),(2,'1ST_READ.BIN')):
            embedded=delivery.b.READER.read_file(delivery.b.track(delivery.OUT,disc),'1ST_READ.BIN')[0]
            self.assertEqual(embedded,(delivery.OUT/name).read_bytes())
            self.assertEqual(delivery.b.sha(embedded),report['disc_executable_sha256'][str(disc)])


if __name__=='__main__':unittest.main()
