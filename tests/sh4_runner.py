"""Small, strict integer SH-4 runner for the emitted VWF leaf routines.

Not a Dreamcast emulator: unsupported instructions and unmapped memory fail.
This checks the actual encoded branches, delay slots, table loads and stores.
"""


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
            elif w & 0xFF00 in (0x8900, 0x8B00):
                if self.t == (w & 0xFF00 == 0x8900):
                    next_pc = pc + 4 + 2 * signed(w & 255, 8)
            elif op == 0xA:
                self.pending = pc + 4 + 2 * signed(w & 4095, 12)
            elif op == 0xD:
                r[n] = self.read((pc & ~3) + 4 + 4 * (w & 255), 4)
            elif op == 0xE:
                r[n] = signed(w & 255, 8)
            elif op == 7:
                r[n] += signed(w & 255, 8)
            elif w & 0xFF00 == 0x8800:
                self.t = signed(r[0]) == signed(w & 255, 8)
            elif w & 0xFF00 == 0x8500:
                r[0] = signed(self.read(r[m] + low * 2, 2), 16)
            elif op == 6 and low in (0, 1, 2):
                size = 1 << low
                r[n] = signed(self.read(r[m], size), size * 8)
            elif op == 6 and low == 3:
                r[n] = r[m]
            elif op == 6 and low == 6:
                value = self.read(r[m], 4)
                if n != m:
                    r[m] += 4
                r[n] = value
            elif op == 6 and low in (12, 13):
                r[n] = r[m] & (255 if low == 12 else 65535)
            elif op == 2 and low in (0, 1, 2):
                self.write(r[n], r[m], 1 << low)
            elif op == 2 and low == 8:
                self.t = (r[n] & r[m]) == 0
            elif op == 3 and low == 0:
                self.t = r[n] == r[m]
            elif op == 3 and low == 2:
                self.t = r[n] >= r[m]
            elif op == 3 and low == 3:
                self.t = signed(r[n]) >= signed(r[m])
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
