"""Local resource checks for cooking/cleaning prompts and the help tilemap."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import cooking
import pvr_atlas
import build_script
import psi2
import scriptpack
import woodcutting
import build


class CookingUITests(unittest.TestCase):
    def test_prompt_translations(self):
        entries=build_script.load_en(str(cooking.ROOT/'script/en/ch1_activity_prompts.en.tsv'))
        self.assertEqual(entries[0x51868],'Cook? (3 AP)')
        self.assertEqual(entries[0x61848],'Clean? (2 AP)')
        self.assertEqual(entries[0x51068],'Chop wood? (4 AP)')

    def test_help_glossary_controls(self):
        lines=cooking.strings()
        self.assertEqual(lines['title'],'Cooking')
        self.assertEqual(lines['green'],'Green ingredients')
        self.assertEqual(len(lines),9)

    def test_native_tilemap_roundtrip_and_patch_boundaries(self):
        path=cooking.ROOT/'extracted/EVENT.DAT'
        if not path.exists():self.skipTest('requires original EVENT.DAT')
        original=path.read_bytes()
        image=pvr_atlas.decode_scl(original,cooking.SCL)
        data=bytearray(original)
        pvr_atlas.encode_scl(data,cooking.SCL,image)
        self.assertEqual(pvr_atlas.decode_scl(data,cooking.SCL).tobytes(),image.tobytes())
        data=bytearray(original)
        tiles=cooking.patch(data)
        self.assertLessEqual(tiles,512)
        self.assertEqual(len(data),len(original))
        # Only the 600 map descriptors and the two texture payloads may change.
        cols,rows,_,atlases=pvr_atlas.scl_layout(original,cooking.SCL)
        ranges=[(cooking.SCL+32,cooking.SCL+32+cols*rows*4)]
        ranges += [(a+16,a+16+256*256*2) for a in atlases]
        last=0
        for lo,hi in sorted(ranges):
            self.assertEqual(data[last:lo],original[last:lo])
            last=hi
        self.assertEqual(data[last:],original[last:])
        decoded=pvr_atlas.decode_scl(data,cooking.SCL)
        self.assertEqual(decoded.crop((85,52,324,140)).tobytes(),
                         image.crop((85,52,324,140)).tobytes())

    def test_activity_prompt_repacking_preserves_branch_destinations(self):
        path=cooking.ROOT/'extracted/SCENARIO.DAT'
        if not path.exists():self.skipTest('requires original SCENARIO.DAT')
        translations=build_script.load_en(str(cooking.ROOT/'script/en/ch1_activity_prompts.en.tsv'))
        gate=build_script.load_en(str(cooking.ROOT/'script/en/ch1_gate_prompts.en.tsv'))
        self.assertEqual(set(gate),set(range(0x44048,0x49049,0x1000)))
        self.assertEqual(set(gate.values()),{'Go past the gate?'})
        translations.update(gate)
        checked=0
        for i,start,program in psi2.groups(path.read_bytes()):
            local={off-start:text for off,text in translations.items() if start<=off<start+len(program)}
            if not local:continue
            patched,_,_,_=scriptpack.repack_psi(program,local)
            before,after=psi2.walk(program),psi2.walk(patched)
            self.assertEqual(len(before.boundaries),len(after.boundaries))
            mapping=dict(zip(sorted(before.boundaries),sorted(after.boundaries)))
            self.assertEqual(len(before.targets),len(after.targets))
            for (_,old),(_,new) in zip(before.targets,after.targets):
                self.assertEqual(mapping[old+16],new+16)
            checked+=len(local)
        self.assertEqual(checked,len(translations))

    def test_woodcutting_asset_preserves_controller_and_storage(self):
        path=cooking.ROOT/'extracted/EVENT.DAT'
        if not path.exists():self.skipTest('requires original EVENT.DAT')
        original=path.read_bytes()
        before=pvr_atlas.decode_scl(original,woodcutting.SCL)
        data=bytearray(original)
        self.assertLessEqual(woodcutting.patch(data),512)
        cols,rows,_,atlases=pvr_atlas.scl_layout(original,woodcutting.SCL)
        ranges=[(woodcutting.SCL+32,woodcutting.SCL+32+cols*rows*4)]
        ranges += [(a+16,a+16+256*256*2) for a in atlases]
        last=0
        for lo,hi in sorted(ranges):
            self.assertEqual(data[last:lo],original[last:lo])
            last=hi
        self.assertEqual(data[last:],original[last:])
        after=pvr_atlas.decode_scl(data,woodcutting.SCL)
        self.assertEqual(before.crop((125,60,360,155)).tobytes(),
                         after.crop((125,60,360,155)).tobytes())
        self.assertEqual(cooking.strings(woodcutting.UI)['title'],'Woodcutting')

    def test_field_menu_slots_and_gate_choice_lengths(self):
        for off in (0x88B62,0x89854):
            text=dict(build.UI_STRINGS)[off]
            self.assertEqual([text[i:i+5].strip() for i in range(0,len(text),5)],
                             ['Save','Load','Setup'])
        offsets={'domina':0x4458E,'prica':0x4571A,'courreges':0x465E2,
                 'michette':0x4764A,'prague':0x485CE,'zero':0x4962E}
        for route,off in offsets.items():
            entries=build_script.load_en(str(cooking.ROOT/f'script/en/ch1_freedom_{route}.en.tsv'))
            for address,expected in ((off,'Go outside!'),(off+0x16,'Stay inside!')):
                self.assertEqual(entries[address],expected)
                wrapped,encoded=scriptpack.encode_text(entries[address],cols=15)
                self.assertNotIn('\n',wrapped)
                for parity in (0,1):
                    self.assertLessEqual(len(scriptpack.preserve_record_alignment(encoded,parity))//2,15)
        prague=build_script.load_en(str(cooking.ROOT/'script/en/ch1_freedom_prague.en.tsv'))
        wrapped,_=scriptpack.encode_text(prague[0x48586],cols=17)
        self.assertEqual(wrapped,'Well? Still want\nto go outside?')


if __name__=='__main__':unittest.main()
