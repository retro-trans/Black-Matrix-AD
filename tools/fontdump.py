"""Pull the font sheet out of a Dreamcast RAM dump or emulator save state.

Per docs/text-engine.md the sheet is installed at a fixed address:

    font base   0x8C75F800          (RAM offset 0x75F800)
    glyph N     base + 16 + N*128
    record      two 16x16 planes, 64 bytes each, 2bpp, 4 px/byte, MSB pair left
    length      4608*128 + 16 = 589840

Usage:
    python tools/fontdump.py verify <dump>            # is the font where we expect?
    python tools/fontdump.py find   <dump>            # search, for states with headers
    python tools/fontdump.py extract <dump> [offset]  # write font.bin + a PNG sheet

`dump` can be a raw 16 MB main-RAM dump, or any file containing one (a save
state); `find` locates the sheet by content so a container header does not
matter.  A gzip-compressed state is decompressed automatically.
"""

import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx

RAM_BASE = 0x8C000000
FONT_ADDR = 0x8C75F800
FONT_OFF = FONT_ADDR - RAM_BASE          # 0x75F800
GLYPH = 128
COUNT = 4608
HEADER = 16
FONT_LEN = COUNT * GLYPH + HEADER
PLANE = 64
LEVELS = (0x10, 0x70, 0xB8, 0xFF)


def load(path):
    data = open(path, "rb").read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def glyph(data, base, index, plane=0):
    o = base + HEADER + index * GLYPH + plane * PLANE
    return data[o:o + PLANE]


def nz(b):
    return sum(1 for x in b if x)


GLYPH_W, GLYPH_H = 24, 16


def _morton(a, b):
    n = 0
    for i in range(8):
        n |= ((a >> i) & 1) << (2 * i)
        n |= ((b >> i) & 1) << (2 * i + 1)
    return n


# Pixel order inside a tile: PowerVR twiddled, y interleaved into the low bits.
_TWIDDLE = [[_morton(y, x) for x in range(16)] for y in range(16)]


def pixel(data, base, index, x, y):
    """One pixel (0..3) of glyph `index`.

    A glyph is 24x16 stored as two 16x16 twiddled tiles of 64 bytes: tile 0
    covers x 0..15, tile 1 covers x 16..23 (its right half is unused).
    Four pixels per byte, most significant pair leftmost.
    """
    plane, xx = (0, x) if x < 16 else (1, x - 16)
    o = base + HEADER + index * GLYPH + plane * PLANE
    i = _TWIDDLE[y][xx]
    return (data[o + (i >> 2)] >> (6 - 2 * (i & 3))) & 3


def pixels(data, base, index):
    """Yield (x, y, value 0..3) across a whole glyph."""
    for y in range(GLYPH_H):
        for x in range(GLYPH_W):
            yield x, y, pixel(data, base, index, x, y)


def verify(data, base, explain=False):
    """True if `base` looks like the font sheet."""
    if base < 0 or base + FONT_LEN > len(data):
        return False
    checks = []
    # index 0 is SJIS 8140, the full-width space
    checks.append(("index 0 blank", nz(glyph(data, base, 0)) == 0))
    # 143..152 are the full-width digits
    digits = [glyph(data, base, 143 + i) for i in range(10)]
    checks.append(("digits inked", all(nz(d) >= 8 for d in digits)))
    # a digit has clear space top and bottom
    z = digits[0]
    checks.append(("zero shaped", nz(z[:8]) == 0 and nz(z[16:56]) > 6))
    # 512 is the first kanji
    checks.append(("index 512 dense", nz(glyph(data, base, 512)) >= 24))
    if explain:
        for name, ok in checks:
            print("    %-18s %s" % (name, "ok" if ok else "FAIL"))
    return all(ok for _, ok in checks)


def find(data):
    """Locate the sheet by content, for dumps that are not raw RAM."""
    hits = []
    if verify(data, FONT_OFF):
        hits.append(FONT_OFF)
    blank = b"\x00" * GLYPH
    i = 0
    while True:
        j = data.find(blank, i)
        if j < 0 or j + FONT_LEN > len(data):
            break
        base = j - HEADER
        if base not in hits and verify(data, base):
            hits.append(base)
        i = j + 4
    return hits


def sheet_png(data, base, path, first=0, count=256, cols=16, scale=2):
    cw, ch = GLYPH_W + 1, GLYPH_H + 1
    rows_n = (count + cols - 1) // cols
    W, H = cols * cw, rows_n * ch
    rows = [bytearray(W * 3) for _ in range(H)]
    for k in range(count):
        gx, gy = (k % cols) * cw, (k // cols) * ch
        for x, y, v in pixels(data, base, first + k):
            p = (gx + x) * 3
            c = LEVELS[v]
            rows[gy + y][p:p + 3] = bytes((c, c, c))
    big = gfx.upscale(rows, W, scale)
    gfx.write_png(path, W * scale, H * scale, big)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd, path = argv[1], argv[2]
    data = load(path)
    print("%s: %d bytes" % (os.path.basename(path), len(data)))

    if cmd == "verify":
        base = int(argv[3], 0) if len(argv) > 3 else FONT_OFF
        print("checking base %08X (RAM %08X):" % (base, RAM_BASE + base))
        ok = verify(data, base, explain=True)
        print("  ->", "FONT FOUND" if ok else "not the font")
        return 0 if ok else 1

    if cmd == "find":
        hits = find(data)
        if not hits:
            print("  no font sheet found")
            return 1
        for h in hits:
            print("  font at file offset %08X (RAM %08X)" % (h, RAM_BASE + h))
        return 0

    if cmd == "extract":
        base = int(argv[3], 0) if len(argv) > 3 else None
        if base is None:
            hits = find(data)
            if not hits:
                print("  no font sheet found; pass an offset explicitly")
                return 1
            base = hits[0]
        if not verify(data, base):
            print("  warning: %08X does not pass the checks, extracting anyway" % base)
        out_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "extracted")
        os.makedirs(out_dir, exist_ok=True)
        raw = os.path.join(out_dir, "FONT.BIN")
        open(raw, "wb").write(data[base:base + FONT_LEN])
        print("  wrote %s (%d bytes)" % (raw, FONT_LEN))
        for plane in (0, 1):
            png = os.path.join(out_dir, "font_plane%d.png" % plane)
            sheet_png(data, base, png, first=0, count=512, plane=plane)
            print("  wrote %s" % png)
        return 0

    print("unknown command:", cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
