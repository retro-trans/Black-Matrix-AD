"""Full main-menu labels compose with the stock-emulator HD atlas patch."""
import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tools/hd_ui'))
import mainmenu
import reusable_atlas as atlas
import latin
import patchline


class MainMenuTests(unittest.TestCase):
    def fixture(self):
        # Synthetic signatures suffice for mutation and fail-closed checks.
        data=bytearray(0xE7464)
        for original,pointer,instructions,_ in mainmenu.MENUS:
            struct.pack_into('<H',data,original,28)
            struct.pack_into('<I',data,pointer,mainmenu.vwf.LOAD_BASE+original)
            for off,expected in instructions:struct.pack_into('<H',data,off,expected)
        return data

    def verify_patch(self,before):
        data=mainmenu.patch(bytearray(before))
        labels=mainmenu.cooking.strings(mainmenu.UI)
        allowed=set(range(mainmenu.STORAGE-mainmenu.vwf.LOAD_BASE,
                          mainmenu.STORAGE_END-mainmenu.vwf.LOAD_BASE))
        for i,(old,ptr,sites,last) in enumerate(mainmenu.MENUS):
            address=mainmenu.STORAGE+i*mainmenu.RECORD_BYTES
            self.assertEqual(struct.unpack_from('<I',data,ptr)[0],address)
            words=struct.unpack_from('<64H',data,address-mainmenu.vwf.LOAD_BASE)
            self.assertEqual(words[0],63)
            rows=[labels[k] for k in ('status','ritual','items','shop','abilities','system',last)]
            for row,label in enumerate(rows):
                self.assertEqual(words[1+9*row:1+9*(row+1)],
                                 tuple(patchline.to_sjis(c) for c in label.ljust(9)))
                self.assertTrue(all(atlas.tables()[0][latin.sjis_to_index(patchline.to_sjis(c))]!=255 for c in label))
            self.assertEqual(data[old:old+58],before[old:old+58])
            allowed.update(range(ptr,ptr+4))
            for off,oldop in sites:
                self.assertEqual(struct.unpack_from('<H',data,off)[0],oldop&0xFF00|9)
                allowed.update(range(off,off+2))
        self.assertEqual(len(before),len(data))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(before,data)) if a!=b))
        return data

    def test_labels_row_stride_and_only_intended_writes(self):
        self.verify_patch(bytes(self.fixture()))

    def test_late_signature_failure_is_atomic(self):
        data=self.fixture();data[mainmenu.MENUS[-1][2][-1][0]]^=1
        before=bytes(data)
        with self.assertRaisesRegex(ValueError,'instruction'):mainmenu.patch(data)
        self.assertEqual(data,before)

    def test_occupied_arena_and_repeat_are_rejected(self):
        data=self.fixture();data[mainmenu.STORAGE-mainmenu.vwf.LOAD_BASE]=1
        with self.assertRaisesRegex(ValueError,'storage'):mainmenu.patch(data)
        data=mainmenu.patch(self.fixture())
        with self.assertRaises(ValueError):mainmenu.patch(data)

    def test_ensure_accepts_only_exact_previous_installation(self):
        data=mainmenu.patch(self.fixture());before=bytes(data)
        self.assertEqual(mainmenu.ensure(data),before)
        data[mainmenu.STORAGE-mainmenu.vwf.LOAD_BASE+4]^=1
        before=bytes(data)
        with self.assertRaises(ValueError):mainmenu.ensure(data)
        self.assertEqual(data,before)

    def test_composes_with_actual_hd_executable(self):
        src=ROOT/'build/1ST_READ.vwf.bin';orig=ROOT/'extracted/1ST_READ.BIN'
        if not src.exists() or not orig.exists():self.skipTest('local game fixture')
        baseline,*_=mainmenu.vwf.apply()
        before,_=atlas.patch(bytes(baseline),orig.read_bytes())
        data=self.verify_patch(before)
        self.assertEqual(data[atlas.ARENA-atlas.BASE:atlas.END-atlas.BASE],
                         before[atlas.ARENA-atlas.BASE:atlas.END-atlas.BASE])
        self.assertEqual(mainmenu.STORAGE_END,atlas.ARENA)


if __name__=='__main__':unittest.main()
