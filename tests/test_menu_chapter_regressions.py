"""Source-asset guards for the September 7 screenshot regressions."""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_script
import chaptercards
import cooking
import mainmenu
import patchline
import pvr_atlas
import terms
import vwf


def native_rows(text, cols):
    """Replay the native cell cursor, including its full-row newline rule."""
    cell = 0
    rows = []
    for ch in text:
        if ch == '\n':
            cell = (cell//cols+1)*cols
        else:
            while len(rows) <= cell//cols:
                rows.append('')
            rows[cell//cols] += ch
            cell += 1
    return rows


class ScreenshotRegressionTests(unittest.TestCase):
    def test_narr_opcode_in_spoken_window_has_no_split_word_or_blank_row(self):
        source = build_script.load_en(ROOT/'script/en/ch1_town_residents_shops.en.tsv')
        for off, expected in (
            (0x1B6FA, ["Don't tell me you're a runaway", 'slave?!']),
            (0x1B7A6, ["So you're the slave owned by that",
                       'occult-mad freak who lives up on', 'the hill!!']),
        ):
            wrapped = patchline.wrap(source[off], cols=patchline.NARR_COLS)
            self.assertEqual(native_rows(wrapped, patchline.COLS), expected)
            self.assertEqual(native_rows(wrapped, patchline.NARR_COLS), expected)

    def test_menu_records_widths_and_neighbours(self):
        path = ROOT/'extracted/1ST_READ.BIN'
        if not path.exists(): self.skipTest('requires original executable')
        original = path.read_bytes()
        # Exercise composition with the actual VWF payload/arena allocations.
        data, *_ = vwf.apply()
        before = bytes(data)
        mainmenu.patch(data)
        expected_labels = cooking.strings(mainmenu.UI)
        for i, (record, ptr, patches, last) in enumerate(mainmenu.MENUS):
            address = mainmenu.STORAGE+i*mainmenu.RECORD_BYTES
            self.assertEqual(struct.unpack_from('<I',data,ptr)[0],address)
            offset = address-vwf.LOAD_BASE
            words = struct.unpack_from('<64H',data,offset)
            self.assertEqual(words[0],63)
            labels = [expected_labels[k] for k in ('status','ritual','items','shop','abilities','system',last)]
            for row,label in enumerate(labels):
                self.assertEqual(words[1+row*9:1+(row+1)*9],
                                 tuple(patchline.to_sjis(c) for c in label.ljust(9)))
            for off, old in patches:
                self.assertEqual(struct.unpack_from('<H',original,off)[0],old)
                self.assertEqual(struct.unpack_from('<H',data,off)[0],old&0xFF00|9)
            self.assertEqual(data[record:record+58],original[record:record+58])
        self.assertEqual(len(data),len(original))
        allowed = set(range(mainmenu.STORAGE-vwf.LOAD_BASE,
                            mainmenu.STORAGE-vwf.LOAD_BASE+2*mainmenu.RECORD_BYTES))
        for _,ptr,patches,_ in mainmenu.MENUS:
            allowed.update(range(ptr,ptr+4))
            for off,_ in patches: allowed.update(range(off,off+2))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(before,data)) if a!=b))
        with self.assertRaises(ValueError): mainmenu.patch(data)

    def test_chapter_graphic_stays_within_its_existing_asset(self):
        path=ROOT/'extracted/EVENT.DAT'
        if not path.exists(): self.skipTest('requires original EVENT.DAT')
        original=path.read_bytes()
        data=bytearray(original)
        cols,rows,_,atlases=pvr_atlas.scl_layout(data,chaptercards.SCL)
        count=chaptercards.patch(data)
        self.assertLessEqual(count,len(atlases)*256)
        end=max(atlases)+16+256*256*2
        self.assertEqual(data[:chaptercards.SCL],original[:chaptercards.SCL])
        self.assertEqual(data[end:],original[end:])
        self.assertEqual(data[chaptercards.SCL:chaptercards.SCL+32],
                         original[chaptercards.SCL:chaptercards.SCL+32])
        for atlas in atlases:
            self.assertEqual(data[atlas-16:atlas+16],original[atlas-16:atlas+16])
        self.assertEqual(pvr_atlas.decode_scl(data,chaptercards.SCL).size,(640,240))
        self.assertEqual(len(data),len(original))

    def test_ui_label_glossary_does_not_force_menu_grammar_on_prose(self):
        glossary=terms.load_glossary()
        self.assertEqual(terms.source_term_counts('状態',glossary),{'状態':1})
        self.assertNotIn('状態',terms.source_term_counts('こんな状態では',glossary))
        self.assertEqual(cooking.strings(chaptercards.UI)['chapter'],'Chapter 1')


if __name__=='__main__': unittest.main()
