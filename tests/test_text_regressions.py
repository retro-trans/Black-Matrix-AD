"""Run with python -m unittest discover -s tests -v. No emulator required."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import psi2
import scriptpack
import vwf
import patchline
import textlayout
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


class ExpandedGridTests(unittest.TestCase):
    def test_allocator_stub_and_pitch_leave_other_grids_unchanged(self):
        stub = vwf.build_record_stub()
        blob = stub.assemble()
        self.assertLessEqual(len(blob), vwf.PLACE_END - vwf.PLACE_DEAD)
        for columns in (3, 5, 11, 14, 15, 17, 19, 32, 33, 34, 38, 39, 42):
            cpu = SH4()
            cpu.put(vwf.PLACE_DEAD, blob)
            # Stop at the original allocator: its arguments and PR must survive.
            cpu.put(vwf.GRID_CREATE, bytes.fromhex('0b000900'))  # RTS; NOP
            cpu.r[4:7] = [0x8C100000, columns, 3]
            cpu.run(stub.labels['column_stub'])
            self.assertEqual(cpu.r[4:7], [0x8C100000,
                             {17: 33, 19: 33}.get(columns, columns), 3])
            self.assertEqual(cpu.pr, 0xFFFFFFFF)
            cpu.r[11] = 0x8C100000
            cpu.write(cpu.r[11] + 8, columns, 2)
            cpu.run(stub.labels['pitch_stub'])
            self.assertEqual(cpu.r[9], {33:14}.get(columns,28))
        self.assertLessEqual(33 * 3, textlayout.TRANSITION_CELLS)
        self.assertLessEqual(33 * 2, textlayout.TRANSITION_CELLS)
        for old, new, pitch in ((17, 33, 14), (19, 33, 14)):
            self.assertLessEqual((new - 1) * pitch + 28, old * 28)

    def test_allocation_hooks_installed_and_native_close_untouched(self):
        path = Path(vwf.ROOT) / 'extracted/1ST_READ.BIN'
        if not path.exists(): self.skipTest('requires original executable')
        original = path.read_bytes()
        exe, _, stub, _, _ = vwf.apply()
        for address, label in ((vwf.TEXT_CREATE_CALL, 'column_stub'),
                               (vwf.GRID_PITCH_CALL, 'pitch_stub')):
            instruction = struct.unpack_from('<H', exe, address-vwf.LOAD_BASE)[0]
            self.assertEqual(instruction >> 12, 0xB)
            disp = instruction & 0xFFF
            if disp & 0x800: disp -= 0x1000
            self.assertEqual(address + 4 + disp * 2, stub.labels[label])
            offset = address-vwf.LOAD_BASE
            self.assertEqual(exe[offset+2:offset+4], original[offset+2:offset+4])
        for address in vwf.TEXT_CREATE_PTRS:
            self.assertEqual(struct.unpack_from('<I',exe,address-vwf.LOAD_BASE)[0],
                             stub.labels['column_stub'])
        offset = vwf.TEXT_CLOSE_PTR-vwf.LOAD_BASE
        self.assertEqual(exe[offset:offset+4], original[offset:offset+4])

    def test_wrapper_matches_grid_and_screenshot_uses_two_rows(self):
        self.assertTrue(vwf.EXPAND_TEXT_GRIDS)
        self.assertEqual((patchline.COLS, patchline.NARR_COLS), (33,33))
        sample = 'Hmph! Why are you being so needy...?'
        wrapped = patchline.wrap(sample)
        self.assertEqual(wrapped, 'Hmph! Why are you being so\nneedy...?')
        for row in wrapped.split('\n'):
            self.assertLessEqual(len(row), patchline.COLS)
            self.assertLessEqual(patchline.text_width(row), patchline.ROW_PIXELS)
        # A full cell row wraps naturally: no extra explicit break/blank row.
        self.assertEqual(patchline.wrap('i'*33 + ' next'), 'i'*33+'next')

    def test_text_row_spacing_is_gated_and_does_not_stretch_glyphs(self):
        stub=vwf.build_record_stub()
        for cols in (3,11,14,15,17,19,32,33,34,38,39):
            cpu=SH4()
            cpu.put(vwf.PLACE_DEAD,stub.assemble())
            cpu.r[11]=0x8C100000
            cpu.write(cpu.r[11]+8,cols,2)
            for row in range(3):
                cpu.r[0]=row
                cpu.run(stub.labels['row_pitch_stub'])
                self.assertEqual(cpu.r[0],row*(18 if cols == 33 else 16))
                self.assertEqual(cpu.pr,0xFFFFFFFF)
                self.assertEqual(cpu.r[11],0x8C100000)
        # Three 16px glyph rows begin at 0,18,36; bottom edge is 52px.
        self.assertEqual(2*textlayout.TEXT_ROW_PITCH+16,52)
        source=Path(vwf.ROOT)/'extracted/1ST_READ.BIN'
        if not source.exists(): self.skipTest('requires original executable')
        original=source.read_bytes()
        exe,_,stub,_,_=vwf.apply()
        offset=vwf.ROW_PITCH_CALL-vwf.LOAD_BASE
        self.assertEqual(original[offset:offset+4],vwf.ROW_PITCH_CALL_OLD)
        instruction=struct.unpack_from('<H',exe,offset)[0]
        self.assertEqual(instruction>>12,0xB)
        disp=instruction&0xFFF
        if disp&0x800:disp-=0x1000
        self.assertEqual(vwf.ROW_PITCH_CALL+4+2*disp,stub.labels['row_pitch_stub'])
        self.assertEqual(exe[offset+2:offset+4],bytes.fromhex('0900'))
        # Compact/menu branch and original float conversion are untouched.
        self.assertEqual(exe[0x50558:0x505AA],original[0x50558:0x505AA])
        self.assertEqual(exe[offset+4:offset+12],original[offset+4:offset+12])


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
                            (33, [1, 2, 3, 4, 5] * 19),
                            (38, [1, 2, 3, 4, 5] * 15),
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


if __name__ == '__main__':
    unittest.main()
