import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools/hd_ui'), str(ROOT / 'tests')]
import vga_compatibility as fix
import buddy_vga_buffer as budget
from sh4_runner import SH4


class VgaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not fix.PACKAGE.exists() or not fix.MANIFEST.exists():
            raise unittest.SkipTest('Requires local original discs, VGA input and frozen release manifest')
        cls.original, cls.candidate = fix.inputs()
        cls.manifest = json.loads(fix.MANIFEST.read_text())

    def issued(self, disc):
        data = (ROOT / f'build/dcp-v0.9.0/disc{disc}/target-inspection/files/1ST_READ.BIN').read_bytes()
        row = next(p for p in self.manifest['patches'] if p['disc'] == disc)
        self.assertEqual(hashlib.sha256(data).hexdigest(), row['target_files']['1ST_READ.BIN']['sha256'])
        return data

    def test_authenticates_both_discs_and_only_transplants_video_delta(self):
        for disc in (1, 2):
            before = self.issued(disc)
            after, delta = fix.patch(before, self.original, self.candidate)
            upstream = {i for i, (a, b) in enumerate(zip(self.original, self.candidate)) if a != b}
            self.assertEqual(len(upstream), 510)
            self.assertEqual(len(delta), 513)
            self.assertEqual(struct.unpack_from('<I', after, 0x278)[0], fix.previous.WRAPPER)
            self.assertEqual(after[0xcc:0xce], bytes.fromhex('10e4'))
            for i in range(len(before)):
                if i in upstream:
                    self.assertEqual(after[i], self.candidate[i])
                elif not 0x278 <= i < 0x27c:
                    self.assertEqual(after[i], before[i])

    def test_keeps_vga_budget_hook_and_abi_code(self):
        for disc in (1, 2):
            before = self.issued(disc)
            after, _ = fix.patch(before, self.original, self.candidate)
            offset = budget.HELPER - 0x8c010000
            self.assertEqual(after[offset:offset + len(budget.helper())], budget.helper())
            self.assertEqual(after[budget.CALL_POINTER:budget.CALL_POINTER+4],
                             struct.pack('<I', budget.HELPER))
            self.assertEqual(after[0x27c:0x284], before[0x27c:0x284])

    def test_diagnostic_variant_retains_old_helper_pointer(self):
        before = self.issued(1)
        after, delta = fix.patch(before, self.original, self.candidate, keep_startup=True)
        self.assertEqual(len(delta), 510)
        self.assertEqual(after[0x278:0x27c], before[0x278:0x27c])

    def test_rejects_video_overlap_unknown_startup_and_truncation(self):
        exe = self.issued(1)
        for offset in (0x92cde, 0xa3a58, 0xc9860, 0x278, fix.previous.HELPER-0x8c010000):
            changed = bytearray(exe); changed[offset] ^= 1
            with self.assertRaises(ValueError):
                fix.patch(changed, self.original, self.candidate)
        with self.assertRaises(ValueError):
            fix.patch(exe[:-1], self.original, self.candidate)
        with self.assertRaises(ValueError):
            fix.patch(exe, self.original, self.original)

    def test_upstream_cable_probe_runs_actual_instructions_all_gpio_ids(self):
        class CableCPU(SH4):
            def read(self, addr, size):
                if addr == 0xff800030:
                    self.assert_size = size
                    return self.gpio
                return super().read(addr, size)
        for cable in range(4):
            for other in (0, 0xfcff):
                cpu = CableCPU(); cpu.gpio = cable << 8 | other
                cpu.put(0x8c010000, self.candidate)
                cpu.r[15] = 0x8cff0000
                cpu.run(0x8c0d99a8)
                self.assertEqual(cpu.r[0], cable)
                self.assertEqual(bool(cpu.t), cable == 0)
                self.assertEqual(cpu.assert_size, 2)

    def test_video_timing_path_only_programs_vga_for_actual_vga_cable(self):
        class VideoCPU(SH4):
            def read(self, addr, size):
                if addr == 0xff800030:
                    return self.cable << 8
                if 0xa05f8000 <= addr < 0xa05f8200:
                    return self.registers.get(addr, 0)
                return super().read(addr, size)

            def write(self, addr, value, size):
                if 0xa05f8000 <= addr < 0xa05f8200:
                    self.registers[addr] = value & ((1 << (size*8))-1)
                    return
                return super().write(addr, value, size)
        for cable in range(4):
            cpu=VideoCPU();cpu.cable=cable;cpu.registers={}
            cpu.put(0x8c010000,self.candidate);cpu.r[15]=0x8cff0000
            cpu.write(0x8c2c5a18,0x10,4)
            # Stub the separately unchanged output-enable routine and original
            # non-VGA continuation; execute the complete new selection path.
            cpu.traps[0x8c0a2818]=lambda m: None
            cpu.traps[0x8c0d9ae4]=lambda m: None
            cpu.run(0x8c0d9860)
            self.assertEqual(cpu.r[15],0x8cff0000)
            self.assertEqual(cpu.read(0x8c2c5a18,4),0x10)
            if cable==0:
                self.assertEqual(cpu.registers[0xa05f80d0],0x100)
                self.assertEqual(cpu.registers[0xa05f80d8],0x020c0359)
                self.assertEqual(cpu.registers[0xa05f80f0],0x00280028)
            else:
                self.assertEqual(cpu.registers,{})

    def test_runner_new_immediate_ops_and_shift_preserve_t(self):
        cpu=SH4();cpu.r[0]=0x12340000;cpu.t=True
        cpu.put(0x8c010000,bytes.fromhex('03cb03ca28400b000900'))
        cpu.run(0x8c010000)
        self.assertEqual(cpu.r[0],0)
        self.assertTrue(cpu.t)
        cpu=SH4();cpu.r[1]=0x12345678;cpu.t=True
        cpu.put(0x8c010000,bytes.fromhex('19600b000900'))
        cpu.run(0x8c010000)
        self.assertEqual(cpu.r[0],0x56781234)
        self.assertTrue(cpu.t)

    def test_movie_framebuffer_setup_applies_vga_line_doubling(self):
        class VideoCPU(SH4):
            def read(self,addr,size):
                if addr==0xff800030:
                    return self.cable<<8
                return super().read(addr,size)

            def write(self,addr,value,size):
                if 0xa05f8000<=addr<0xa05f8200:
                    self.registers[addr]=value & ((1<<(size*8))-1)
                    return
                super().write(addr,value,size)
        for cable in range(4):
            for mode in (0x10,0x30):
                cpu=VideoCPU();cpu.cable=cable;cpu.registers={}
                cpu.put(0x8c010000,self.candidate);cpu.r[15]=0x8cff0000
                cpu.write(0x8c2c5a18,mode,4)
                cpu.traps[0x8c0a2818]=lambda m: None
                cpu.run(0x8c0d990a)
                value=cpu.registers[0xa05f8044]
                self.assertEqual(bool(value & 0x00800000),cable==0)
                self.assertEqual(bool(value & 2),cable==0 and mode==0x10)
                self.assertEqual(cpu.r[15],0x8cff0000)


if __name__ == '__main__':
    unittest.main()
