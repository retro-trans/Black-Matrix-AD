"""Resource-boundary checks for the five requested September 7 UI screens."""
import csv
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import chapter_cards
import cooking
import field_battle_ui as ui
import patchline
import pvr_atlas
import uistr


def assert_outside_unchanged(test, before, after, ranges):
    test.assertEqual(len(before), len(after))
    last = 0
    for lo, hi in sorted(ranges):
        test.assertEqual(before[last:lo], after[last:lo])
        last = hi
    test.assertEqual(before[last:], after[last:])


class FieldBattleUITests(unittest.TestCase):
    def original(self, name):
        path = ui.ROOT / 'extracted' / name
        if not path.exists():
            self.skipTest('requires original ' + name)
        return path.read_bytes()

    def test_menu_slots_and_unchanged_executable_code(self):
        before = self.original('1ST_READ.BIN')
        after = bytearray(before)
        ui.patch_executable(after)
        text = cooking.strings(ui.UI)
        layouts = [(0x88B28, ui.FIELD, 4),
                   (0x8981A, ui.FIELD[:-1] + ('deploy',), 4),
                   (0x87FA6, ui.BATTLE, 3),
                   (0x87FD8, ui.STANCES, 3),
                   (0x8A054, ('refill_heading',), 2)]
        layouts += [(0x8823A + 8*i, (key,), 3) for i, key in enumerate(ui.BATTLE)]
        ranges = []
        for off, keys, width in layouts:
            for i, key in enumerate(keys):
                words = struct.unpack_from('<%dH' % width, after, off + 2*width*i)
                expected = tuple(patchline.to_sjis(c) for c in text[key].ljust(width))
                self.assertEqual(words, expected)
            ranges.append((off, off + 2*width*len(keys)))
        assert_outside_unchanged(self, before, after, ranges)
        # Overflow must fail before writing into a following slot.
        with self.assertRaises(ValueError):
            ui.record(after, 0x87FA6, ['TOO LONG'] * 8, 3)

    def test_stances_and_refill_heading_match_original_sources(self):
        before = self.original('1ST_READ.BIN')
        self.assertEqual(next(uistr.walk(before, 0x87FD6, 1))[2],
                         '防　御回　避反　撃')
        self.assertEqual(next(uistr.walk(before, 0x8A052, 1))[2], '補血')
        text = cooking.strings(ui.UI)
        self.assertEqual([text[k] for k in ui.STANCES], ['Grd', 'Eva', 'Ctr'])
        self.assertEqual(text['refill_heading'], 'BP')

    def test_help_preserves_all_other_parameter_data(self):
        before = self.original('PARAMETA.DAT')
        after = bytearray(before)
        ui.patch_parameters(after)
        assert_outside_unchanged(self, before, after,
            [(offset, offset + 57*2) for offset in (ui.HELP_OFFSET, *ui.BATTLE_HELP)] +
            [(offset-2, offset+16) for offset in ui.ITEM_NAMES] +
            [(offset, offset+76) for offset in ui.ITEM_DESCRIPTIONS])
        lines = cooking.strings(ui.UI)['position_help'].split('\\n')
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(len(line) <= 19 for line in lines))

    def test_battle_help_sources_and_padded_rows(self):
        before = self.original('PARAMETA.DAT')
        after = bytearray(before)
        ui.patch_parameters(after)
        english = cooking.strings(ui.BATTLE_HELP_UI)
        with ui.BATTLE_HELP_UI.open(encoding='utf-8') as f:
            sources = {r['id']:r['japanese'] for r in csv.DictReader(
                (line for line in f if not line.startswith('#')), delimiter='\t')}
        for offset, key in ui.BATTLE_HELP.items():
            # Bind each translation to the actual source, not just a coincidental
            # 57-word record somewhere else in the parameter archive.
            original = next(uistr.walk(before, offset-2, 1))[2]
            self.assertEqual(original.replace('\u3000', ''), sources[key])
            lines = english[key].split('\\n')
            self.assertEqual(len(lines), 3)
            self.assertTrue(all(len(line) <= 19 for line in lines))
            expected = tuple(patchline.to_sjis(c) for line in lines
                             for c in line.ljust(19))
            self.assertEqual(struct.unpack_from('<57H', after, offset), expected)

    def test_item_names_fit_reserved_slots_and_preserve_flags(self):
        before = self.original('PARAMETA.DAT')
        after = bytearray(before)
        ui.patch_parameters(after)
        text = cooking.strings(ui.ITEM_UI)
        for offset, (key, _) in ui.ITEM_NAMES.items():
            self.assertLessEqual(len(text[key]), 8)
            self.assertEqual(struct.unpack_from('<H', after, offset-2)[0], len(text[key]))
            self.assertEqual(struct.unpack_from('<8H', after, offset),
                tuple(patchline.to_sjis(c) for c in text[key].ljust(8)))
            self.assertEqual(after[offset+16:offset+20], before[offset+16:offset+20])
        for offset, key in ui.ITEM_DESCRIPTIONS.items():
            lines = text[key].split('\\n')
            self.assertEqual(len(lines), 2)
            self.assertTrue(all(len(line) <= 19 for line in lines))
            self.assertEqual(struct.unpack_from('<38H', after, offset),
                tuple(patchline.to_sjis(c) for line in lines for c in line.ljust(19)))

    def test_cards_preserve_storage_and_surrounding_art(self):
        before = self.original('EVENT.DAT')
        after = bytearray(before)
        counts = chapter_cards.patch(after)
        ranges = []
        for off, used in zip((chapter_cards.END_SCL, chapter_cards.OPEN_SCL), counts):
            cols, rows, _, atlases = pvr_atlas.scl_layout(before, off)
            self.assertLessEqual(used, len(atlases)*256)
            ranges.append((off + 32, off + 32 + cols*rows*4))
            ranges.extend((a + 16, a + 16 + 256*256*2) for a in atlases)
        assert_outside_unchanged(self, before, after, ranges)
        original = pvr_atlas.decode_scl(before, chapter_cards.OPEN_SCL)
        result = pvr_atlas.decode_scl(after, chapter_cards.OPEN_SCL)
        for y in range(240):
            for x in range(640):
                if not any(x0 <= x <= x1 and y0 <= y <= y1
                           for x0, y0, x1, y1 in chapter_cards.PANELS):
                    self.assertEqual(result.getpixel((x, y)), original.getpixel((x, y)))


if __name__ == '__main__':
    unittest.main()
