"""A minimal SH-4 assembler - just enough to write the VWF hook.

Only the instruction forms the patch actually uses are encoded.  Labels are
resolved in a second pass, and PC-relative literals (MOV.L/MOV.W @(disp,PC))
are pooled automatically and emitted at the end of the routine, which is the
fiddly part of writing SH-4 by hand.

Everything it produces is meant to be read back with tools/sh4dis.py - build
the patch, disassemble the result, and check the listing says what you meant.

    a = Asm(0x8C0F5468)
    a.mov_l_pc("node_lookup", 3)      # MOV.L @(disp,PC),R3
    a.jsr(3); a.nop()
    ...
    a.label("out"); a.rts(); a.nop()
    code = a.assemble()
"""

import struct


def _chk(v, lo, hi, what):
    if not (lo <= v <= hi):
        raise ValueError("%s out of range: %d (allowed %d..%d)" % (what, v, lo, hi))
    return v


class Asm(object):
    """Assemble a straight-line routine that starts at `org`."""

    def __init__(self, org):
        self.org = org
        self.items = []          # (kind, payload) in emission order
        self.labels = {}
        self.pool_l = []         # 32-bit literals, in insertion order
        self.pool_w = []         # 16-bit literals

    # --- bookkeeping ------------------------------------------------------

    def label(self, name):
        if name in self.labels:
            raise ValueError("duplicate label: %s" % name)
        self.items.append(("label", name))
        return self

    def _w(self, word):
        self.items.append(("w", word & 0xFFFF))
        return self

    def _rel(self, kind, target, base):
        """A branch whose displacement is only known after layout."""
        self.items.append(("rel", [kind, target, base, False]))
        return self

    def _lit(self, kind, key):
        self.items.append(("lit", (kind, key)))
        return self

    def long_(self, name, value):
        """Declare a 32-bit literal reachable with mov_l_pc(name, rn)."""
        for i, (n, _) in enumerate(self.pool_l):
            if n == name:
                return self
        self.pool_l.append((name, value))
        return self

    def word_(self, name, value):
        """Declare a small constant reachable with mov_w_pc(name, rn).

        Kept in the 32-bit pool even though the values are small: MOV.W
        @(disp,PC) only reaches 510 bytes ahead, MOV.L reaches 1020, and the
        routine is long enough that the difference decides whether the pool
        can be reached at all.  Every constant here is small and positive, so
        loading it as a long is equivalent.
        """
        return self.long_(name, value & 0xFFFF)

    # --- data movement ----------------------------------------------------

    def mov(self, m, n):                  # MOV Rm,Rn
        return self._w(0x6003 | (n << 8) | (m << 4))

    def mov_i(self, imm, n):              # MOV #imm,Rn
        _chk(imm, -128, 127, "MOV #imm")
        return self._w(0xE000 | (n << 8) | (imm & 0xFF))

    def mov_l_pc(self, name, n):          # MOV.L @(disp,PC),Rn
        return self._lit(("l", n), name)

    def mov_w_pc(self, name, n):          # a small constant; see word_()
        return self._lit(("l", n), name)

    def mov_l_at(self, m, n):             # MOV.L @Rm,Rn
        return self._w(0x6002 | (n << 8) | (m << 4))

    def mov_w_at(self, m, n):             # MOV.W @Rm,Rn
        return self._w(0x6001 | (n << 8) | (m << 4))

    def mov_l_atd(self, disp, m, n):      # MOV.L @(disp,Rm),Rn
        return self._w(0x5000 | (n << 8) | (m << 4) | _chk(disp // 4, 0, 15, "disp"))

    def mov_w_atd_r0(self, disp, m):      # MOV.W @(disp,Rm),R0
        return self._w(0x8500 | (m << 4) | _chk(disp // 2, 0, 15, "disp"))

    def mov_l_store(self, m, n):          # MOV.L Rm,@Rn
        return self._w(0x2002 | (n << 8) | (m << 4))

    def mov_w_store(self, m, n):          # MOV.W Rm,@Rn
        return self._w(0x2001 | (n << 8) | (m << 4))

    def mov_b_store(self, m, n):          # MOV.B Rm,@Rn
        return self._w(0x2000 | (n << 8) | (m << 4))

    def mov_b_at(self, m, n):             # MOV.B @Rm,Rn
        return self._w(0x6000 | (n << 8) | (m << 4))

    def mov_l_stored(self, m, disp, n):   # MOV.L Rm,@(disp,Rn)
        return self._w(0x1000 | (n << 8) | (m << 4) | _chk(disp // 4, 0, 15, "disp"))

    def mov_w_stored_r0(self, disp, n):   # MOV.W R0,@(disp,Rn)
        return self._w(0x8100 | (n << 4) | _chk(disp // 2, 0, 15, "disp"))

    def mov_l_inc(self, m, n):            # MOV.L @Rm+,Rn
        return self._w(0x6006 | (n << 8) | (m << 4))

    def mov_l_dec(self, m, n):            # MOV.L Rm,@-Rn
        return self._w(0x2006 | (n << 8) | (m << 4))

    def mov_l_r0(self, m, n):             # MOV.L @(R0,Rm),Rn
        return self._w(0x000E | (n << 8) | (m << 4))

    def mov_w_r0(self, m, n):             # MOV.W @(R0,Rm),Rn
        return self._w(0x000D | (n << 8) | (m << 4))

    def mov_b_r0(self, m, n):             # MOV.B @(R0,Rm),Rn
        return self._w(0x000C | (n << 8) | (m << 4))

    def mov_l_str_r0(self, m, n):         # MOV.L Rm,@(R0,Rn)
        return self._w(0x0006 | (n << 8) | (m << 4))

    def mov_w_str_r0(self, m, n):         # MOV.W Rm,@(R0,Rn)
        return self._w(0x0005 | (n << 8) | (m << 4))

    # --- arithmetic / logic ----------------------------------------------

    def add(self, m, n):                  # ADD Rm,Rn
        return self._w(0x300C | (n << 8) | (m << 4))

    def add_i(self, imm, n):              # ADD #imm,Rn
        _chk(imm, -128, 127, "ADD #imm")
        return self._w(0x7000 | (n << 8) | (imm & 0xFF))

    def sub(self, m, n):                  # SUB Rm,Rn
        return self._w(0x3008 | (n << 8) | (m << 4))

    def mul_l(self, m, n):                # MUL.L Rm,Rn
        return self._w(0x0007 | (n << 8) | (m << 4))

    def sts_macl(self, n):                # STS MACL,Rn
        return self._w(0x001A | (n << 8))

    def extu_w(self, m, n):               # EXTU.W Rm,Rn
        return self._w(0x600D | (n << 8) | (m << 4))

    def extu_b(self, m, n):               # EXTU.B Rm,Rn
        return self._w(0x600C | (n << 8) | (m << 4))

    def shll(self, n):                    # SHLL Rn
        return self._w(0x4000 | (n << 8))

    def shll2(self, n):                   # SHLL2 Rn
        return self._w(0x4008 | (n << 8))

    def tst(self, m, n):                  # TST Rm,Rn
        return self._w(0x2008 | (n << 8) | (m << 4))

    # --- compares ---------------------------------------------------------

    def cmp_eq(self, m, n):               # CMP/EQ Rm,Rn
        return self._w(0x3000 | (n << 8) | (m << 4))

    def cmp_eq_i(self, imm):              # CMP/EQ #imm,R0
        return self._w(0x8800 | (imm & 0xFF))

    def cmp_hs(self, m, n):               # CMP/HS Rm,Rn  (unsigned n >= m)
        return self._w(0x3002 | (n << 8) | (m << 4))

    def cmp_ge(self, m, n):               # CMP/GE Rm,Rn  (signed n >= m)
        return self._w(0x3003 | (n << 8) | (m << 4))

    def cmp_pz(self, n):                  # CMP/PZ Rn
        return self._w(0x4011 | (n << 8))

    def cmp_pl(self, n):                  # CMP/PL Rn
        return self._w(0x4015 | (n << 8))

    # --- control flow -----------------------------------------------------

    def bt(self, target):
        return self._rel("b8", target, 4)

    def bf(self, target):
        return self._rel("b8f", target, 4)

    def bra(self, target):
        return self._rel("b12", target, 4)

    def bsr(self, target):
        return self._rel("b12s", target, 4)

    def jsr(self, n):
        return self._w(0x400B | (n << 8))

    def jmp(self, n):
        return self._w(0x402B | (n << 8))

    def rts(self):
        return self._w(0x000B)

    def nop(self):
        return self._w(0x0009)

    def sts_l_pr(self, n):                # STS.L PR,@-Rn
        return self._w(0x4022 | (n << 8))

    def lds_l_pr(self, n):                # LDS.L @Rn+,PR
        return self._w(0x4026 | (n << 8))

    # --- assembly ---------------------------------------------------------

    def assemble(self):
        # BT and BF only reach 127 words.  A conditional that cannot reach its
        # target is rewritten as the opposite condition branching over an
        # unconditional BRA, which reaches 2047.  That changes the size of the
        # instruction, so layout has to be redone until nothing else moves.
        for _ in range(8):
            placed, pc = self._layout()
            if not self._relax(placed):
                break
        else:
            raise ValueError("branch relaxation did not settle")
        return self._emit(placed, pc)

    def _layout(self):
        pc = self.org
        placed = []
        for kind, payload in self.items:
            if kind == "label":
                self.labels[payload] = pc
                placed.append((kind, payload, pc))
            else:
                placed.append((kind, payload, pc))
                pc += 6 if (kind == "rel" and payload[3]) else 2
        return placed, pc

    def _relax(self, placed):
        """Mark any conditional branch that cannot reach; True if any changed."""
        changed = False
        for kind, payload, at in placed:
            if kind != "rel":
                continue
            bkind, target, base, expanded = payload
            if bkind not in ("b8", "b8f") or expanded:
                continue
            if target not in self.labels:
                raise ValueError("undefined label: %s" % target)
            disp = (self.labels[target] - (at + base)) // 2
            if not -128 <= disp <= 127:
                payload[3] = True
                changed = True
        return changed

    def _emit(self, placed, pc):

        pool_base = (pc + 3) & ~3
        long_at = {}
        addr = pool_base
        for name, _ in self.pool_l:
            long_at[name] = addr
            addr += 4
        word_at = {}
        for name, _ in self.pool_w:
            word_at[name] = addr
            addr += 2
        self.pool_end = addr

        # pass 2: encode
        out = bytearray()
        for kind, payload, at in placed:
            if kind == "label":
                continue
            if kind == "w":
                word = payload
            elif kind == "rel":
                bkind, target, base, expanded = payload
                if target not in self.labels:
                    raise ValueError("undefined label: %s" % target)
                if expanded:
                    # opposite condition over a BRA, then the delay slot
                    over = (0x8B00 if bkind == "b8" else 0x8900) | 1
                    far = (self.labels[target] - (at + 2 + 4)) // 2
                    _chk(far, -2048, 2047, "long branch to %s" % target)
                    out += struct.pack("<HHH", over, 0xA000 | (far & 0xFFF), 0x0009)
                    continue
                disp = (self.labels[target] - (at + base)) // 2
                if bkind in ("b8", "b8f"):
                    _chk(disp, -128, 127, "branch to %s" % target)
                    word = (0x8900 if bkind == "b8" else 0x8B00) | (disp & 0xFF)
                else:
                    _chk(disp, -2048, 2047, "branch to %s" % target)
                    word = (0xA000 if bkind == "b12" else 0xB000) | (disp & 0xFFF)
            elif kind == "lit":
                (size, rn), name = payload
                if size == "l":
                    if name not in long_at:
                        raise ValueError("undeclared long literal: %s" % name)
                    disp = (long_at[name] - ((at & ~3) + 4)) // 4
                    _chk(disp, 0, 255, "literal %s" % name)
                    word = 0xD000 | (rn << 8) | disp
                else:
                    if name not in word_at:
                        raise ValueError("undeclared word literal: %s" % name)
                    disp = (word_at[name] - (at + 4)) // 2
                    _chk(disp, 0, 255, "literal %s" % name)
                    word = 0x9000 | (rn << 8) | disp
            else:
                raise ValueError("bad item %r" % kind)
            out += struct.pack("<H", word)

        # pad to the pool, then emit it
        while self.org + len(out) < pool_base:
            out += b"\x00\x00"
        for _, value in self.pool_l:
            out += struct.pack("<I", value & 0xFFFFFFFF)
        for _, value in self.pool_w:
            out += struct.pack("<H", value & 0xFFFF)
        return bytes(out)
