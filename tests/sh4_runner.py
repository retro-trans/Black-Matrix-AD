"""Small, strict SH-4 runner for the emitted VWF leaf routines.

Not a Dreamcast emulator: unsupported instructions and unmapped memory fail.
This checks the actual encoded branches, delay slots, table loads and stores.
Single-precision FPU data moves/constants and FADD support sprite geometry;
other unsupported arithmetic/instructions still fail.
"""
import struct


def signed(value, bits=32):
    return (value & ((1 << (bits - 1)) - 1)) - (value & (1 << (bits - 1)))


class SH4:
    BASE = 0x8C000000

    def __init__(self):
        self.mem = bytearray(16 * 1024 * 1024)
        self.r = [0] * 16
        self.pr = 0xFFFFFFFF
        self.t = False
        self.macl = 0
        self.pc = 0
        self.pending = None
        self.traps = {}  # Explicit test doubles for separately verified SDK calls.
        self.fr = [0] * 16  # raw single-precision bits; data movement only

    def offset(self, addr, size):
        off = addr - self.BASE
        if not 0 <= off <= len(self.mem) - size:
            raise AssertionError('unmapped access %08X (%d)' % (addr, size))
        return off

    def put(self, addr, data):
        off = self.offset(addr, len(data))
        self.mem[off:off + len(data)] = data

    def read(self, addr, size):
        off = self.offset(addr, size)
        return int.from_bytes(self.mem[off:off + size], 'little')

    def write(self, addr, value, size):
        self.put(addr, (value & ((1 << (size * 8)) - 1)).to_bytes(size, 'little'))

    def run(self, entry, limit=20000):
        self.pc = entry
        self.pending = None
        for _ in range(limit):
            if self.pc == 0xFFFFFFFF:
                return
            if self.pc in self.traps:
                self.traps[self.pc](self)
                self.pc = self.pr
                continue
            pc = self.pc
            w = self.read(pc, 2)
            n, m, low, op = (w >> 8) & 15, (w >> 4) & 15, w & 15, w >> 12
            r = self.r
            old_pending = self.pending
            self.pending = None
            next_pc = pc + 2
            if w == 0x0009:
                pass
            elif w == 0x000B:
                self.pending = self.pr
            elif w & 0xF0FF == 0x402B:
                self.pending = r[n]  # JMP @Rn, with its delay slot
            elif w & 0xFF00 in (0x8900, 0x8B00):
                if self.t == (w & 0xFF00 == 0x8900):
                    next_pc = pc + 4 + 2 * signed(w & 255, 8)
            elif w & 0xFF00 in (0x8D00, 0x8F00):
                if self.t == (w & 0xFF00 == 0x8D00):
                    self.pending = pc + 4 + 2 * signed(w & 255, 8)
            elif op == 0xA:
                self.pending = pc + 4 + 2 * signed(w & 4095, 12)
            elif op == 0xB:
                self.pr = pc + 4
                self.pending = pc + 4 + 2 * signed(w & 4095, 12)
            elif w & 0xF0FF in (0x400B, 0x402B):
                if w & 255 == 0x0B:
                    self.pr = pc + 4
                self.pending = r[n]
            elif op == 0xD:
                r[n] = self.read((pc & ~3) + 4 + 4 * (w & 255), 4)
            elif op == 9:
                r[n] = signed(self.read(pc + 4 + 2 * (w & 255), 2), 16)
            elif op == 0xE:
                r[n] = signed(w & 255, 8)
            elif op == 7:
                r[n] += signed(w & 255, 8)
            elif w & 0xFF00 == 0x8800:
                self.t = signed(r[0]) == signed(w & 255, 8)
            elif w & 0xFF00 == 0x8500:
                r[0] = signed(self.read(r[m] + low * 2, 2), 16)
            elif w & 0xFF00 == 0x8400:
                r[0] = signed(self.read(r[m] + low, 1), 8)
            elif w & 0xFF00 == 0xC800:
                self.t = (r[0] & (w & 255)) == 0
            elif w & 0xFF00 == 0xC900:
                r[0] &= w & 255
            elif w & 0xFF00 == 0xCA00:
                r[0] ^= w & 255
            elif w & 0xFF00 == 0xCB00:
                r[0] |= w & 255
            elif w & 0xFF00 == 0xC700:
                r[0] = (pc & ~3) + 4 + 4 * (w & 255)
            elif op == 0xF and (w & 0xFF) == 0x8D:
                self.fr[n] = 0  # FLDI0 FRn
            elif op == 0xF and (w & 0xFF) == 0x9D:
                self.fr[n] = 0x3F800000  # FLDI1 FRn
            elif op == 0xF and low == 12:
                self.fr[n] = self.fr[m]  # FMOV FRm,FRn
            elif op == 0xF and low in (0, 1):
                a = struct.unpack('<f', struct.pack('<I', self.fr[n]))[0]
                b = struct.unpack('<f', struct.pack('<I', self.fr[m]))[0]
                self.fr[n] = struct.unpack('<I', struct.pack('<f', a+b if low==0 else a-b))[0]
            elif op == 0xF and low == 8:
                self.fr[n] = self.read(r[m], 4)  # FMOV.S @Rm,FRn
            elif op == 0xF and low == 10:
                self.write(r[n], self.fr[m], 4)  # FMOV.S FRm,@Rn
            elif op == 0xF and low == 7:
                self.write(r[0] + r[n], self.fr[m], 4)  # FRm,@(R0,Rn)
            elif w & 0xFF00 == 0x8100:
                self.write(r[m] + low * 2, r[0], 2)
            elif w & 0xFF00 == 0x8000:
                self.write(r[m] + low, r[0], 1)
            elif op == 6 and low in (0, 1, 2):
                size = 1 << low
                r[n] = signed(self.read(r[m], size), size * 8)
            elif op == 5:
                r[n] = self.read(r[m] + low * 4, 4)
            elif op == 6 and low == 3:
                r[n] = r[m]
            elif op == 6 and low == 7:
                r[n] = ~r[m]
            elif op == 6 and low == 9:
                r[n] = (r[m] << 16) | (r[m] >> 16)  # SWAP.W
            elif op == 6 and low in (4, 5, 6):
                size = 1 << (low - 4)
                value = signed(self.read(r[m], size),size*8)
                if n != m:
                    r[m] += size
                r[n] = value
            elif op == 6 and low in (12, 13):
                r[n] = r[m] & (255 if low == 12 else 65535)
            elif op == 6 and low in (14, 15):
                r[n] = signed(r[m],8 if low==14 else 16)
            elif op == 2 and low in (0, 1, 2):
                self.write(r[n], r[m], 1 << low)
            elif op == 2 and low == 8:
                self.t = (r[n] & r[m]) == 0
            elif op == 2 and low == 9:
                r[n] &= r[m]
            elif op == 2 and low == 10:
                r[n] ^= r[m]
            elif op == 2 and low == 11:
                r[n] |= r[m]
            elif op == 2 and low == 14:
                self.macl = (r[n] & 65535) * (r[m] & 65535)
            elif op == 2 and low == 6:
                r[n] -= 4
                self.write(r[n], r[m], 4)
            elif op == 1:
                self.write(r[n] + low * 4, r[m], 4)
            elif op == 3 and low == 0:
                self.t = r[n] == r[m]
            elif op == 3 and low == 2:
                self.t = r[n] >= r[m]
            elif op == 3 and low == 3:
                self.t = signed(r[n]) >= signed(r[m])
            elif op == 3 and low == 6:
                self.t = r[n] > r[m]
            elif op == 3 and low == 7:
                self.t = signed(r[n]) > signed(r[m])
            elif op == 3 and low == 12:
                r[n] += r[m]
            elif op == 3 and low == 8:
                r[n] -= r[m]
            elif op == 0 and low == 7:
                self.macl = (r[n] * r[m]) & 0xFFFFFFFF
            elif w & 0xF0FF == 0x001A:
                r[n] = self.macl
            elif op == 0 and low in (12, 13, 14):
                size = 1 << (low - 12)
                r[n] = signed(self.read(r[m] + r[0], size), size * 8)
            elif op == 0 and low in (4, 5, 6):
                self.write(r[n] + r[0], r[m], 1 << (low - 4))
            elif w & 0xF0FF in (0x4000, 0x4008):
                r[n] <<= 1 if w & 255 == 0 else 2
            elif w & 0xF0FF in (0x4018, 0x4028):
                r[n] <<= 8 if w & 255 == 0x18 else 16
            elif w & 0xF0FF == 0x4019:
                r[n] >>= 8
            elif w & 0xF0FF in (0x4001, 0x4009):
                if w & 255 == 1:
                    self.t = bool(r[n] & 1)
                r[n] >>= 1 if w & 255 == 1 else 2
            elif w & 0xF0FF == 0x4010:
                r[n] = (r[n]-1) & 0xFFFFFFFF
                self.t = r[n] == 0  # DT Rn
            elif w & 0xF0FF in (0x4011, 0x4015):
                self.t = signed(r[n]) >= (0 if w & 255 == 0x11 else 1)
            elif w & 0xF0FF == 0x4022:
                r[n] -= 4
                self.write(r[n], self.pr, 4)
            elif w & 0xF0FF == 0x4026:
                self.pr = self.read(r[n], 4)
                r[n] += 4
            else:
                raise AssertionError('unsupported SH-4 %04X at %08X' % (w, pc))
            self.r = [v & 0xFFFFFFFF for v in r]
            self.pc = old_pending if old_pending is not None else next_pc
        raise AssertionError('SH-4 step limit reached at %08X' % self.pc)
