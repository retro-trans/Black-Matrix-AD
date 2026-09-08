import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/hd_ui'))
import reusable_atlas as atlas
import battle_menu as battle
import mainmenu
import patchline


class BattleMenuTests(unittest.TestCase):
    def fixture(self):
        data=bytearray(0xE7464)
        code=atlas.build_code().assemble()
        data[atlas.CODE-atlas.BASE:atlas.CODE-atlas.BASE+len(code)]=code
        struct.pack_into('<H',data,battle.ORIGINAL,24)
        struct.pack_into('<I',data,battle.POINTER,atlas.BASE+battle.ORIGINAL)
        struct.pack_into('<H',data,battle.WIDTH,0xE403)
        return data

    def verify(self,data):
        before=bytes(data);meta=battle.patch(data)
        start=meta['storage']-atlas.BASE;end=start+meta['bytes']
        words=struct.unpack_from('<73H',data,start)
        self.assertEqual(words[0],72)
        self.assertEqual(meta['labels'],['Move','Attack','Magic','Items','Status','Refill BP','Stance','Summon'])
        for i,label in enumerate(meta['labels']):
            self.assertEqual(words[1+9*i:1+9*(i+1)],tuple(patchline.to_sjis(c) for c in label.ljust(9)))
        self.assertEqual(struct.unpack_from('<H',data,battle.WIDTH)[0],0xE409)
        self.assertEqual(struct.unpack_from('<I',data,battle.POINTER)[0],meta['storage'])
        self.assertLessEqual(meta['storage']+meta['bytes'],atlas.COSTS)
        allowed=set(range(start,end))|set(range(battle.POINTER,battle.POINTER+4))|set(range(battle.WIDTH,battle.WIDTH+2))
        self.assertEqual(len(before),len(data))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(before,data)) if a!=b))

    def test_rows_and_scoped_changes(self):self.verify(self.fixture())

    def test_atomic_rejection(self):
        for off in (battle.ORIGINAL,battle.POINTER,battle.WIDTH,atlas.CODE-atlas.BASE):
            data=self.fixture();data[off]^=1;before=bytes(data)
            with self.assertRaises(ValueError):battle.patch(data)
            self.assertEqual(data,before)

    def test_composes_with_main_menu_and_hd(self):
        src=ROOT/'build/1ST_READ.vwf.bin';orig=ROOT/'extracted/1ST_READ.BIN'
        if not src.exists() or not orig.exists():self.skipTest('local game fixture')
        exe,_=atlas.patch(src.read_bytes(),orig.read_bytes())
        self.verify(mainmenu.patch(bytearray(exe)))


if __name__=='__main__':unittest.main()
