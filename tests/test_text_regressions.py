"""Run with python -m unittest discover -s tests -v. No emulator required."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import psi2
import scriptpack
import vwf
from sh4_runner import SH4


class APGrammarTests(unittest.TestCase):
    def test_warning_does_not_swallow_following_jump(self):
        # AP warning with cost 3; jump to the final return. The old 'ee'
        # signature swallowed st 3 + its target as tag-3 variable expression.
        body = struct.pack('<HHHHIHHIH', 9, 0x23, 1, 0, 3, 0, 3, 0x14, 7)
        program = b'PSI22.00' + struct.pack('<II', 0, len(body)) + body
        walked = psi2.walk(program)
        self.assertEqual(walked.boundaries, {0x10, 0x1E, 0x24})
        self.assertEqual(walked.targets, [(0x20, 0x14)])

    def test_ap_handler_reads_one_expression_in_original_executable(self):
        path = Path(vwf.ROOT) / 'extracted' / '1ST_READ.BIN'
        if not path.exists():
            self.skipTest('requires original local executable')
        exe = path.read_bytes()
        self.assertEqual(struct.unpack_from('<I', exe, 0x8A408 + 0x23 * 4)[0],
                         0x8C08E1E6)
        # Its only operand-reader call; it then polls the native AP modal.
        self.assertEqual(exe[0x7E1FC:0x7E206],
                         bytes.fromhex('2ad22bd80b4209000228'))
        self.assertEqual(psi2.T1_SIGS[0x23], 'e')

    def test_repacking_library_relocates_ap_exit(self):
        path = Path(vwf.ROOT) / 'extracted' / 'SCENARIO.DAT'
        if not path.exists():
            self.skipTest('requires original local scenario')
        program = next(p for i, _, p in psi2.groups(path.read_bytes()) if i == 106)
        rebuilt, _, _, growth = scriptpack.repack_psi(program, {0x48: 'Read it? (3 AP)'})
        self.assertGreater(growth, 0)
        # Only the prompt before the AP test changed size in this fixture.
        field = 0x94 + growth
        target = struct.unpack_from('<I', rebuilt, field)[0] + psi2.TARGET_BIAS
        self.assertEqual(target, 0x2FB2 + growth)
        self.assertIn((field, target - psi2.TARGET_BIAS), psi2.walk(rebuilt).targets)
        self.assertEqual(rebuilt[target:target + 2], program[0x2FB2:0x2FB4])


class VWFTests(unittest.TestCase):
    CTX = 0x8C100000
    NODE = 0x8C101000

    def setUp(self):
        self.cpu = SH4()
        self.code = vwf.build_code()
        self.cpu.put(vwf.CODE, self.code.assemble())
        self.cpu.put(vwf.FLOAT_TAB, vwf.float_table())
        self.adv = [8, 18, 5, 11, 7, 16] + [20] * (vwf.NGLYPH - 6)
        self.bear = [0, 2, 1, 3, 0, 2] + [1] * (vwf.NGLYPH - 6)
        self.cpu.put(vwf.ADV_TAB, bytes(self.adv))
        self.cpu.put(vwf.BEAR_TAB, bytes(self.bear))
        self.cpu.write(self.CTX, 22, 4)
        self.cpu.write(self.CTX + 8, 14, 2)
        self.cpu.write(vwf.WIN_TAB + 22 * 28, 0x8009, 2)
        # Poison the global deliberately. The new code must never read it.
        self.cpu.write(vwf.G_RECORD, 0xDEADBEEF, 4)
        self.cpu.r[15] = 0x8C00F000

    def record(self, slot, chars, atlas=0x12340000, live=True):
        addr = vwf.LINE_RECORDS + slot * vwf.LINE_RECORD_STRIDE
        self.cpu.write(addr, len(chars), 2)
        self.cpu.put(addr + 4, struct.pack('<%dH' % len(chars), *chars))
        self.cpu.write(addr + 0x184, 0x8800 if live else 0, 2)
        self.cpu.write(addr + 0x188, atlas, 4)
        return addr

    def adjust(self, cell, index, atlas=0x12340000):
        self.cpu.put(self.NODE + 12, struct.pack('<f', 321.0))
        self.cpu.r[8:13] = [self.CTX, cell, index, atlas, self.NODE]
        self.cpu.pr = 0xFFFFFFFF
        self.cpu.run(self.code.labels['vwf_adjust'])
        self.assertEqual(self.cpu.r[15], 0x8C00F000)
        return struct.unpack_from('<f', self.cpu.mem,
                                  self.NODE + 12 - self.cpu.BASE)[0]

    def test_deferred_seven_row_menu_uses_own_atlas(self):
        chars = ([1, 2, 3, 0, 4, 5, 2] * 14)
        self.record(0, [5] * 98, atlas=0x77770000)
        self.record(1, [])  # stale empty record with the same old handle
        self.record(7, chars)
        for index in range(98):
            with self.subTest(index=index):
                start = index // 14 * 14
                expected = (self.bear[chars[start]]
                            + sum(self.adv[c] for c in chars[start:index])
                            - self.bear[chars[index]])
                self.assertEqual(self.adjust(index, index), expected)
                self.assertEqual(self.cpu.read(vwf.G_WIDEN, 1), 1)

    def test_dialogue_and_ap_window_keep_variable_width(self):
        for cols, chars in [(17, [1, 2, 3, 4, 5] * 7),
                            (11, [5, 1, 0, 2, 3, 4, 1, 2, 0, 4, 5])]:
            self.cpu.write(self.CTX + 8, cols, 2)
            self.record(0, chars)
            for index in range(len(chars)):
                start = index // cols * cols
                expected = (self.bear[chars[start]]
                            + sum(self.adv[c] for c in chars[start:index])
                            - self.bear[chars[index]])
                self.assertEqual(self.adjust(index, index), expected)

    def test_invalid_records_leave_quad_unchanged(self):
        self.record(0, [1] * 14, live=False)
        self.record(1, [], live=True)
        self.assertEqual(self.adjust(2, 2), 321.0)
        self.assertEqual(self.cpu.read(vwf.G_WIDEN, 1), 0)
        self.record(0, [1] * 14)
        for cell, index, atlas in [(0, 14, 0x12340000), (2, 1, 0x12340000),
                                   (2, 2, 0xFFFFFFFF), (2, 2, 0x98760000)]:
            self.assertEqual(self.adjust(cell, index, atlas), 321.0)
        self.cpu.write(vwf.LINE_RECORDS, 193, 2)
        self.assertEqual(self.adjust(2, 2), 321.0)

    def test_non_text_grid_is_untouched(self):
        self.record(0, [1] * 14)
        self.cpu.write(vwf.WIN_TAB + 22 * 28, 0x8001, 2)
        self.assertEqual(self.adjust(2, 2), 321.0)

    def test_height_fix_still_expands_quad_and_uv_to_sixteen_rows(self):
        self.record(0, [1] * 14)
        self.adjust(0, 0)
        self.cpu.put(self.NODE + 16, struct.pack('<f', 16.0))
        self.cpu.put(self.NODE + 32, struct.pack('<f', 30.0))
        self.cpu.write(self.NODE + 150, 0x40, 2)
        self.cpu.write(self.NODE + 158, 0x78, 2)
        for _ in range(2):  # second pass must be idempotent
            self.cpu.pr = 0xFFFFFFFF
            self.cpu.run(self.code.labels['uv_fix'])
            self.assertEqual(self.cpu.read(self.NODE + 158, 2), 0x80)
            self.assertEqual(self.cpu.read(self.NODE + 162, 2), 0x80)
            self.assertEqual(self.cpu.read(self.NODE + 32, 4),
                             int.from_bytes(struct.pack('<f', 32.0), 'little'))

    def test_captured_book_menu(self):
        path = Path(vwf.ROOT) / 'build' / 'book-menu-20260905-before.bin'
        if not path.exists():
            self.skipTest('optional local menu RAM capture is absent')
        self.cpu.mem[:] = path.read_bytes()
        self.cpu.put(vwf.CODE, self.code.assemble())
        # These identifiers/geometry were observed in this specific capture.
        ctx, window = 0x8C1E7A3C, 22
        self.assertEqual(self.cpu.read(ctx, 4), window)
        self.assertEqual(self.cpu.read(ctx + 8, 2), 14)
        self.assertEqual(self.cpu.read(ctx + 10, 2), 7)
        chars = [self.cpu.read(vwf.LINE_RECORDS + 4 + i * 2, 2) for i in range(98)]
        adv = lambda c: self.cpu.read(vwf.ADV_TAB + c, 1)
        bear = lambda c: self.cpu.read(vwf.BEAR_TAB + c, 1)
        node = self.cpu.read(vwf.WIN_TAB + window * 28 + 24, 4)
        corrected = 0
        for cell in range(98):
            index = self.cpu.read(node + 8, 2)
            atlas = self.cpu.read(node + 4, 4)
            old_x = self.cpu.read(node + 12, 4)
            self.cpu.r[8:13] = [ctx, cell, index, atlas, node]
            self.cpu.r[15], self.cpu.pr = 0x8C00F000, 0xFFFFFFFF
            self.cpu.run(self.code.labels['vwf_adjust'])
            start = index - cell % 14
            expected = (bear(chars[start]) + sum(adv(c) for c in chars[start:index])
                        - bear(chars[index]))
            expected_bits = int.from_bytes(struct.pack('<f', expected), 'little')
            self.assertEqual(self.cpu.read(node + 12, 4), expected_bits)
            corrected += old_x != expected_bits
            node = self.cpu.read(node + 164, 4)
        self.assertEqual(corrected, 82)


class HDVWFLayoutTests(VWFTests):
    """Exercise the emitted stock-atlas UI fixes, including native fallback."""

    def setUp(self):
        super().setUp()
        self.code = vwf.build_code(ui_fixes=True)
        self.cpu.put(vwf.CODE, self.code.assemble())

    def test_help_row_crosses_nonadjacent_record_boundary(self):
        chars = ([1, 2, 3, 4, 5, 0] * 64)
        previous = self.record(7, chars[:192], atlas=123)
        current = self.record(21, chars[192:], atlas=456)
        self.cpu.write(previous + 0x18C, current, 4)
        self.cpu.write(self.CTX + 8, 19, 2)
        # The captured help page begins at 171; its second row splits after
        # two letters at the 192-character boundary ("sh" / "ow item range").
        for cell in range(57):
            absolute = 171 + cell
            start = 171 + cell // 19 * 19
            index = absolute % 192
            expected = (self.bear[chars[start]]
                        + sum(self.adv[g] for g in chars[start:absolute])
                        - self.bear[chars[absolute]])
            with self.subTest(cell=cell):
                self.assertEqual(self.adjust(cell, index, 123 if absolute < 192 else 456), expected)

    def test_released_predecessor_is_not_used(self):
        previous = self.record(7, [1] * 192, atlas=123, live=False)
        current = self.record(21, [1] * 192, atlas=456)
        self.cpu.write(previous + 0x18C, current, 4)
        self.assertEqual(self.adjust(2, 0, 456), 321.0)

    def test_captured_item_help_spacing(self):
        path = Path(vwf.ROOT) / 'build/hd-ui/spacing-live-ram.bin'
        if not path.exists():
            self.skipTest('optional local item-help capture is absent')
        self.cpu.mem[:] = path.read_bytes()
        self.cpu.put(vwf.CODE, self.code.assemble())
        ctx = 0x8C1E77C8
        self.assertEqual(self.cpu.read(ctx, 4), 18)
        self.assertEqual(self.cpu.read(ctx+8, 2), 19)
        node = self.cpu.read(vwf.WIN_TAB + 18*28 + 24, 4)
        chars = [self.cpu.read(vwf.LINE_RECORDS + (i//192)*400 + 4 + (i%192)*2, 2)
                 for i in range(384)]
        adv = lambda g: self.cpu.read(vwf.ADV_TAB+g, 1)
        bear = lambda g: self.cpu.read(vwf.BEAR_TAB+g, 1)
        for cell in range(57):
            absolute = 171 + cell
            start = 171 + cell//19*19
            handle = self.cpu.read(node+4, 4)
            self.cpu.r[8:13] = [ctx, cell, absolute%192, handle, node]
            self.cpu.r[15], self.cpu.pr = 0x8C00F000, 0xFFFFFFFF
            self.cpu.run(self.code.labels['vwf_adjust'])
            expected = bear(chars[start]) + sum(adv(g) for g in chars[start:absolute]) - bear(chars[absolute])
            self.assertEqual(self.cpu.read(node+12, 4),
                             int.from_bytes(struct.pack('<f', expected), 'little'))
            node = self.cpu.read(node+164, 4)

    def test_yes_no_inset_is_idempotent_and_keeps_full_uvs(self):
        self.record(0, [1, 2, 3, 4, 5, 0])
        self.cpu.write(self.CTX + 8, 3, 2)
        self.cpu.write(self.CTX + 10, 2, 2)
        for cell in (0, 3):
            self.adjust(cell, cell)
            y = cell // 3 * 16
            self.cpu.put(self.NODE + 16, struct.pack('<f', float(y)))
            self.cpu.put(self.NODE + 32, struct.pack('<f', float(y + 14)))
            self.cpu.write(self.NODE + 150, 0x40, 2)
            self.cpu.write(self.NODE + 158, 0x78, 2)
            for _ in range(3):
                self.cpu.pr = 0xFFFFFFFF
                self.cpu.run(self.code.labels['uv_fix'])
                for offset, expected in ((16, y+2), (24, y+2), (32, y+13), (40, y+13)):
                    self.assertEqual(self.cpu.read(self.NODE+offset, 4),
                                     int.from_bytes(struct.pack('<f', expected), 'little'))
                self.assertEqual(self.cpu.read(self.NODE + 158, 2), 0x80)
                self.assertEqual(self.cpu.read(self.NODE + 162, 2), 0x80)

    def test_battle_menu_padding_is_scoped_and_idempotent(self):
        self.record(0, [1] * 72)
        self.cpu.write(self.CTX + 8, 9, 2)
        for rows, padding in ((8, 10), (7, 0), (3, 0)):
            self.cpu.write(self.CTX + 10, rows, 2)
            for cell in (0, 1, 9, 17, 63, 71):
                for _ in range(2):
                    self.assertEqual(self.adjust(cell, cell), (cell % 9)*self.adv[1]+padding)


if __name__ == '__main__':
    unittest.main()
