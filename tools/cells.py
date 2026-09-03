"""Inspect the text-window cell nodes in a live RAM dump.

The layout routine at 0x8C0603B4 fetches a per-cell node through
0x8C06BC44(window_id, cell_index) and reads the on-screen position out of it:

    FMOV.S @(12,R4),FR3   -> command +36    ; X
    FMOV.S @(16,R4),FR3   -> command +40    ; Y

0x8C06BC44 indexes a 28-byte table at 0x8C22B4D8 (192 entries), requires the
entry flag 0x8000, bounds-checks cell_index against the count at entry+4, then
walks a linked list from entry+24 following +164 for cell_index steps.

    python tools/cells.py windows extracted/RAM3.BIN
    python tools/cells.py cells   extracted/RAM3.BIN <window_id> [count]
"""

import struct
import sys

RAM_BASE = 0x8C000000
WIN_TABLE = 0x8C22B4D8
WIN_STRIDE = 28
WIN_MAX = 192
NODE_NEXT = 164
NODE_X = 12
NODE_Y = 16


class Ram:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()

    def ok(self, addr, size=4):
        off = addr - RAM_BASE
        return 0 <= off and off + size <= len(self.data)

    def u16(self, addr):
        off = addr - RAM_BASE
        return struct.unpack_from("<H", self.data, off)[0]

    def u32(self, addr):
        off = addr - RAM_BASE
        return struct.unpack_from("<I", self.data, off)[0]

    def f32(self, addr):
        off = addr - RAM_BASE
        return struct.unpack_from("<f", self.data, off)[0]

    def blob(self, addr, size):
        off = addr - RAM_BASE
        return self.data[off:off + size]


def windows(ram):
    print("id   flags  count  head        entry")
    live = 0
    for i in range(WIN_MAX):
        base = WIN_TABLE + i * WIN_STRIDE
        if not ram.ok(base, WIN_STRIDE):
            break
        flags = ram.u32(base)
        count = ram.u32(base + 4)
        head = ram.u32(base + 24)
        if flags == 0 and count == 0 and head == 0:
            continue
        live += 1
        mark = "*" if (flags & 0x8000) else " "
        print("%3d%s %08X %5d  %08X    %s" % (
            i, mark, flags, count, head,
            ram.blob(base, WIN_STRIDE).hex()))
    print("\n%d non-empty entries ('*' = flag 0x8000 set)" % live)


def cells(ram, wid, limit):
    base = WIN_TABLE + wid * WIN_STRIDE
    flags = ram.u32(base)
    count = ram.u32(base + 4)
    node = ram.u32(base + 24)
    print("window %d: flags=%08X count=%d head=%08X" % (wid, flags, count, node))
    if limit is None:
        limit = count if count else 32
    print("\n  #   node        X         Y     +0        +4        +8        +20       +24")
    seen = set()
    for i in range(limit):
        if not node or not ram.ok(node, NODE_NEXT + 4):
            print("  %3d  %08X  <out of range>" % (i, node))
            break
        if node in seen:
            print("  %3d  %08X  <cycle>" % (i, node))
            break
        seen.add(node)
        print("  %3d  %08X  %8.2f  %8.2f  %08X  %08X  %08X  %08X  %08X" % (
            i, node, ram.f32(node + NODE_X), ram.f32(node + NODE_Y),
            ram.u32(node), ram.u32(node + 4), ram.u32(node + 8),
            ram.u32(node + 20), ram.u32(node + 24)))
        node = ram.u32(node + NODE_NEXT)


def dump_node(ram, addr, size=176):
    print("node %08X" % addr)
    for off in range(0, size, 16):
        words = [ram.u32(addr + off + k) for k in range(0, 16, 4)]
        floats = [ram.f32(addr + off + k) for k in range(0, 16, 4)]
        print("  +%3d  %s   %s" % (
            off,
            " ".join("%08X" % w for w in words),
            " ".join("%10.3f" % f for f in floats)))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    cmd, path = sys.argv[1], sys.argv[2]
    ram = Ram(path)
    if cmd == "windows":
        windows(ram)
    elif cmd == "cells":
        wid = int(sys.argv[3], 0)
        limit = int(sys.argv[4], 0) if len(sys.argv) > 4 else None
        cells(ram, wid, limit)
    elif cmd == "node":
        dump_node(ram, int(sys.argv[3], 0))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
