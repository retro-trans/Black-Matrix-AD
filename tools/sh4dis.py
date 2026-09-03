"""A small SH-4 disassembler, enough to read Black/Matrix AD's game code.

The Dreamcast runs SH-4 little-endian with fixed 16-bit instructions, so
decoding is a straight table walk.  PC-relative loads are resolved inline and
annotated with the literal they pull, which is what makes the text-drawing
code readable without a full toolchain.

    python tools/sh4dis.py extracted/1ST_READ.BIN 0x50100 0x60
    python tools/sh4dis.py extracted/1ST_READ.BIN 0x50100 0x60 --xref 0x8C060000

1ST_READ.BIN is loaded at 0x8C010000 on a retail Dreamcast, so a file offset
maps to memory as offset + 0x8C010000.
"""

import struct
import sys

LOAD_BASE = 0x8C010000


def s8(v):
    return v - 0x100 if v & 0x80 else v


def s12(v):
    return v - 0x1000 if v & 0x800 else v


def disasm_one(data, off, load_base=LOAD_BASE):
    """Return (text, target) for the instruction at file offset `off`.

    `target` is a file offset when the instruction references one (branch or
    PC-relative load), else None.
    """
    w = data[off] | (data[off + 1] << 8)
    pc = off
    n = (w >> 8) & 0xF
    m = (w >> 4) & 0xF
    d4 = w & 0xF
    d8 = w & 0xFF
    d12 = w & 0xFFF
    op = w >> 12

    def lit32(disp):
        addr = ((pc & ~3) + 4) + disp * 4
        if addr + 4 <= len(data):
            return addr, struct.unpack_from("<I", data, addr)[0]
        return addr, None

    def lit16(disp):
        addr = (pc + 4) + disp * 2
        if addr + 2 <= len(data):
            v = struct.unpack_from("<H", data, addr)[0]
            return addr, v - 0x10000 if v & 0x8000 else v
        return addr, None

    if op == 0x0:
        if w == 0x0009:
            return "NOP", None
        if w == 0x000B:
            return "RTS", None
        if w == 0x0008:
            return "CLRT", None
        if w == 0x0018:
            return "SETT", None
        if w == 0x0028:
            return "CLRMAC", None
        if w == 0x002B:
            return "RTE", None
        if w == 0x0019:
            return "DIV0U", None
        if d4 == 0x4:
            return "MOV.B   R%d,@(R0,R%d)" % (m, n), None
        if d4 == 0x5:
            return "MOV.W   R%d,@(R0,R%d)" % (m, n), None
        if d4 == 0x6:
            return "MOV.L   R%d,@(R0,R%d)" % (m, n), None
        if d4 == 0x7:
            return "MUL.L   R%d,R%d" % (m, n), None
        if d4 == 0xC:
            return "MOV.B   @(R0,R%d),R%d" % (m, n), None
        if d4 == 0xD:
            return "MOV.W   @(R0,R%d),R%d" % (m, n), None
        if d4 == 0xE:
            return "MOV.L   @(R0,R%d),R%d" % (m, n), None
        if d4 == 0xF:
            return "MAC.L   @R%d+,@R%d+" % (m, n), None
        if (w & 0xF0FF) == 0x0029:
            return "MOVT    R%d" % n, None
        if (w & 0xF0FF) == 0x000A:
            return "STS     MACH,R%d" % n, None
        if (w & 0xF0FF) == 0x001A:
            return "STS     MACL,R%d" % n, None
        if (w & 0xF0FF) == 0x002A:
            return "STS     PR,R%d" % n, None
        if (w & 0xF0FF) == 0x0002:
            return "STC     SR,R%d" % n, None
        if (w & 0xF0FF) == 0x0023:
            return "BRAF    R%d" % n, None
        if (w & 0xF0FF) == 0x0003:
            return "BSRF    R%d" % n, None
        if (w & 0xF0FF) == 0x0083:
            return "PREF    @R%d" % n, None
        return ".word   %04X" % w, None

    if op == 0x1:
        return "MOV.L   R%d,@(%d,R%d)" % (m, d4 * 4, n), None

    if op == 0x2:
        names = {0x0: "MOV.B   R%d,@R%d", 0x1: "MOV.W   R%d,@R%d",
                 0x2: "MOV.L   R%d,@R%d", 0x4: "MOV.B   R%d,@-R%d",
                 0x5: "MOV.W   R%d,@-R%d", 0x6: "MOV.L   R%d,@-R%d",
                 0x7: "DIV0S   R%d,R%d", 0x8: "TST     R%d,R%d",
                 0x9: "AND     R%d,R%d", 0xA: "XOR     R%d,R%d",
                 0xB: "OR      R%d,R%d", 0xC: "CMP/STR R%d,R%d",
                 0xD: "XTRCT   R%d,R%d", 0xE: "MULU.W  R%d,R%d",
                 0xF: "MULS.W  R%d,R%d"}
        if d4 in names:
            return names[d4] % (m, n), None
        return ".word   %04X" % w, None

    if op == 0x3:
        names = {0x0: "CMP/EQ  R%d,R%d", 0x2: "CMP/HS  R%d,R%d",
                 0x3: "CMP/GE  R%d,R%d", 0x4: "DIV1    R%d,R%d",
                 0x5: "DMULU.L R%d,R%d", 0x6: "CMP/HI  R%d,R%d",
                 0x7: "CMP/GT  R%d,R%d", 0x8: "SUB     R%d,R%d",
                 0xA: "SUBC    R%d,R%d", 0xB: "SUBV    R%d,R%d",
                 0xC: "ADD     R%d,R%d", 0xD: "DMULS.L R%d,R%d",
                 0xE: "ADDC    R%d,R%d", 0xF: "ADDV    R%d,R%d"}
        if d4 in names:
            return names[d4] % (m, n), None
        return ".word   %04X" % w, None

    if op == 0x4:
        one = {0x00: "SHLL    R%d", 0x01: "SHLR    R%d", 0x04: "ROTL    R%d",
               0x05: "ROTR    R%d", 0x08: "SHLL2   R%d", 0x09: "SHLR2   R%d",
               0x0B: "JSR     @R%d", 0x10: "DT      R%d", 0x11: "CMP/PZ  R%d",
               0x15: "CMP/PL  R%d", 0x18: "SHLL8   R%d", 0x19: "SHLR8   R%d",
               0x1B: "TAS.B   @R%d", 0x20: "SHAL    R%d", 0x21: "SHAR    R%d",
               0x22: "STS.L   PR,@-R%d", 0x24: "ROTCL   R%d", 0x25: "ROTCR  R%d",
               0x26: "LDS.L   @R%d+,PR", 0x28: "SHLL16  R%d", 0x29: "SHLR16 R%d",
               0x2A: "LDS     R%d,PR", 0x2B: "JMP     @R%d",
               0x0A: "LDS     R%d,MACH", 0x1A: "LDS     R%d,MACL",
               0x0E: "LDC     R%d,SR", 0x02: "STS.L   MACH,@-R%d",
               0x12: "STS.L   MACL,@-R%d"}
        low = w & 0xFF
        if low in one:
            return one[low] % n, None
        if d4 == 0xC:
            return "SHAD    R%d,R%d" % (m, n), None
        if d4 == 0xD:
            return "SHLD    R%d,R%d" % (m, n), None
        return ".word   %04X" % w, None

    if op == 0x5:
        return "MOV.L   @(%d,R%d),R%d" % (d4 * 4, m, n), None

    if op == 0x6:
        names = {0x0: "MOV.B   @R%d,R%d", 0x1: "MOV.W   @R%d,R%d",
                 0x2: "MOV.L   @R%d,R%d", 0x3: "MOV     R%d,R%d",
                 0x4: "MOV.B   @R%d+,R%d", 0x5: "MOV.W   @R%d+,R%d",
                 0x6: "MOV.L   @R%d+,R%d", 0x7: "NOT     R%d,R%d",
                 0x8: "SWAP.B  R%d,R%d", 0x9: "SWAP.W  R%d,R%d",
                 0xA: "NEGC    R%d,R%d", 0xB: "NEG     R%d,R%d",
                 0xC: "EXTU.B  R%d,R%d", 0xD: "EXTU.W  R%d,R%d",
                 0xE: "EXTS.B  R%d,R%d", 0xF: "EXTS.W  R%d,R%d"}
        return names[d4] % (m, n), None

    if op == 0x7:
        return "ADD     #%d,R%d" % (s8(d8), n), None

    if op == 0x8:
        sub = (w >> 8) & 0xF
        if sub == 0x0:
            return "MOV.B   R0,@(%d,R%d)" % (d4, m), None
        if sub == 0x1:
            return "MOV.W   R0,@(%d,R%d)" % (d4 * 2, m), None
        if sub == 0x4:
            return "MOV.B   @(%d,R%d),R0" % (d4, m), None
        if sub == 0x5:
            return "MOV.W   @(%d,R%d),R0" % (d4 * 2, m), None
        if sub == 0x8:
            return "CMP/EQ  #%d,R0" % s8(d8), None
        if sub in (0x9, 0xB, 0xD, 0xF):
            name = {0x9: "BT ", 0xB: "BF ", 0xD: "BT/S", 0xF: "BF/S"}[sub]
            tgt = pc + 4 + s8(d8) * 2
            return "%-7s %08X" % (name, load_base + tgt), tgt
        return ".word   %04X" % w, None

    if op == 0x9:
        addr, val = lit16(d8)
        txt = "MOV.W   @(%08X,PC),R%d" % (load_base + addr, n)
        if val is not None:
            txt += "   ; = %d (0x%X)" % (val, val & 0xFFFF)
        return txt, addr

    if op == 0xA:
        tgt = pc + 4 + s12(d12) * 2
        return "BRA     %08X" % (load_base + tgt), tgt

    if op == 0xB:
        tgt = pc + 4 + s12(d12) * 2
        return "BSR     %08X" % (load_base + tgt), tgt

    if op == 0xC:
        sub = (w >> 8) & 0xF
        table = {0x0: "MOV.B   R0,@(%d,GBR)", 0x1: "MOV.W   R0,@(%d,GBR)",
                 0x2: "MOV.L   R0,@(%d,GBR)", 0x4: "MOV.B   @(%d,GBR),R0",
                 0x5: "MOV.W   @(%d,GBR),R0", 0x6: "MOV.L   @(%d,GBR),R0"}
        if sub in table:
            mul = {0x0: 1, 0x4: 1, 0x1: 2, 0x5: 2, 0x2: 4, 0x6: 4}[sub]
            return table[sub] % (d8 * mul), None
        if sub == 0x3:
            return "TRAPA   #%d" % d8, None
        if sub == 0x7:
            addr = ((pc & ~3) + 4) + d8 * 4
            return "MOVA    @(%08X,PC),R0" % (load_base + addr), addr
        imm = {0x8: "TST", 0x9: "AND", 0xA: "XOR", 0xB: "OR"}
        if sub in imm:
            return "%-7s #%d,R0" % (imm[sub], d8), None
        return ".word   %04X" % w, None

    if op == 0xD:
        addr, val = lit32(d8)
        txt = "MOV.L   @(%08X,PC),R%d" % (load_base + addr, n)
        if val is not None:
            txt += "   ; = %08X" % val
        return txt, addr

    if op == 0xE:
        return "MOV     #%d,R%d" % (s8(d8), n), None

    return ".word   %04X" % w, None


def disassemble(data, start, length, load_base=LOAD_BASE, literals=()):
    out = []
    lit = set(literals)
    off = start
    while off < start + length and off + 1 < len(data):
        if off in lit:
            out.append("%08X  %04X       .long   %08X"
                       % (load_base + off, 0,
                          struct.unpack_from("<I", data, off)[0]))
            off += 4
            continue
        w = data[off] | (data[off + 1] << 8)
        text, _ = disasm_one(data, off, load_base)
        out.append("%08X  %04X       %s" % (load_base + off, w, text))
        off += 2
    return out


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 1
    data = open(argv[1], "rb").read()
    start = int(argv[2], 0)
    length = int(argv[3], 0)
    for line in disassemble(data, start, length):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
