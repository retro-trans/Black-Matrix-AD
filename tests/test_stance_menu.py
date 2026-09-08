import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/hd_ui'))
import reusable_atlas as atlas
import battle_menu
import stance_menu as stance
import mainmenu
import patchline
from sh4_runner import SH4


class StanceMenuTests(unittest.TestCase):
    def fixture(self):
        src=ROOT/'build/1ST_READ.vwf.bin'
        orig=ROOT/'extracted/1ST_READ.BIN'
        if not src.exists() or not orig.exists():self.skipTest('local executable fixtures')
        data,_=atlas.patch(src.read_bytes(),orig.read_bytes())
        data=mainmenu.patch(bytearray(data))
        battle=battle_menu.patch(data)
        return data,battle

    def test_composition_labels_and_scoped_changes(self):
        data,battle=self.fixture();before=bytes(data)
        meta=stance.patch(data,battle)
        self.assertEqual(meta['labels'],['Guard','Evade','Counter'])
        start=meta['storage']-atlas.BASE
        words=struct.unpack_from('<22H',data,start)
        self.assertEqual(words[0],21)
        self.assertEqual(words[1:],tuple(patchline.to_sjis(c)
            for label in meta['labels'] for c in label.ljust(7)))
        end=meta['helper']+meta['helper_bytes']-atlas.BASE
        self.assertLessEqual(end,atlas.COSTS-atlas.BASE)
        allowed=set(range(start,end))|set(range(stance.POINTER,stance.POINTER+4))|set(range(stance.CONSTRUCTOR+6,stance.CONSTRUCTOR+14))
        self.assertEqual(len(data),len(before))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(before,data)) if a!=b))
        # Execute the assembled leaf, verifying both logical and allocated
        # dimensions and the untouched stance-count register.
        cpu=SH4();cpu.put(atlas.BASE,data)
        cpu.r[14]=0x8C19743C;cpu.r[0]=3;cpu.r[11]=3
        cpu.run(meta['helper'])
        self.assertEqual([cpu.read(cpu.r[14]+n,2) for n in (0,2,4,6)],[7,3,7,3])
        self.assertEqual(cpu.r[11],3)
        self.assertEqual(cpu.r[3],meta['storage'])

    def test_unknown_constructor_pointer_and_occupied_storage_fail_atomically(self):
        for target in ('code','pointer','storage','record'):
            data,battle=self.fixture()
            off={'code':stance.CONSTRUCTOR,'pointer':stance.POINTER,
                 'record':stance.ORIGINAL,
                 'storage':((battle['storage']+battle['bytes']+3)&~3)-atlas.BASE}[target]
            data[off]^=1;before=bytes(data)
            with self.assertRaises(ValueError):stance.patch(data,battle)
            self.assertEqual(data,before)


if __name__=='__main__':unittest.main()
