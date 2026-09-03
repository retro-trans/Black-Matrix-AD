"""Measure per-glyph ink extents in FONT.BIN and emit a width table.

Any variable-width scheme needs to know how wide each glyph actually draws.
The cell is 24x16 but almost nothing fills it, so this walks the pixels and
records the leftmost and rightmost inked column per glyph.

    python tools/widths.py report          # summary + the Latin range
    python tools/widths.py table out.bin   # 4608-byte advance table
    python tools/widths.py show 160 26     # ASCII art for a range

Advance = ink width + 1 column of side bearing, clamped to the 24-wide cell.
Blank glyphs get a space advance.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fontdump as fd

FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "extracted", "FONT.BIN")
SPACE_ADVANCE = 8
BEARING = 1


def extents(data, index):
    """(left, right) inked columns, or None when the glyph is blank."""
    lo, hi = None, None
    for x, y, v in fd.pixels(data, 0, index):
        if v:
            if lo is None or x < lo:
                lo = x
            if hi is None or x > hi:
                hi = x
    return None if lo is None else (lo, hi)


def advance(data, index):
    e = extents(data, index)
    if e is None:
        return SPACE_ADVANCE
    return min(fd.GLYPH_W, (e[1] - e[0] + 1) + BEARING)


def sjis_of(index):
    for lo, hi, add in ((0x8140, 0x81BF, 0x7EC0),
                        (0x8240, 0x83BF, 0x7E40),
                        (0x889F, 0x9872, 0x7961)):
        c = (index - add) & 0xFFFF
        if lo <= c <= hi:
            return c
    return None


def label(index):
    c = sjis_of(index)
    if c is None:
        return "?"
    try:
        return bytes([c >> 8, c & 0xFF]).decode("shift_jis")
    except Exception:
        return "?"


def main(argv):
    data = open(FONT, "rb").read()
    cmd = argv[1] if len(argv) > 1 else "report"

    if cmd == "report":
        import collections
        hist = collections.Counter()
        blanks = 0
        for i in range(4608):
            e = extents(data, i)
            if e is None:
                blanks += 1
            else:
                hist[e[1] - e[0] + 1] += 1
        print("glyphs: 4608, blank: %d" % blanks)
        print("ink width histogram (width: count):")
        for w in sorted(hist):
            print("   %2d px : %5d" % (w, hist[w]))
        print()
        print("Latin capitals and lowercase (index: char, ink, advance):")
        for first, n, name in ((143, 10, "digits"), (160, 26, "A-Z"), (193, 26, "a-z")):
            row = []
            for i in range(first, first + n):
                e = extents(data, i)
                row.append("%s=%d" % (label(i), advance(data, i)))
            print("  %-8s %s" % (name, " ".join(row)))
        widths = [advance(data, i) for i in range(160, 186)] + \
                 [advance(data, i) for i in range(193, 219)]
        print()
        print("full-width cell is %d px; mean Latin advance %.1f px -> %.2fx more"
              " characters per line" % (fd.GLYPH_W, sum(widths) / float(len(widths)),
                                        fd.GLYPH_W / (sum(widths) / float(len(widths)))))
        return 0

    if cmd == "table":
        out = bytes(advance(data, i) for i in range(4608))
        open(argv[2], "wb").write(out)
        print("wrote %s (%d bytes, one advance per glyph)" % (argv[2], len(out)))
        return 0

    if cmd == "show":
        first, n = int(argv[2], 0), int(argv[3], 0)
        ramp = " .:#"
        for i in range(first, first + n):
            e = extents(data, i)
            print("index %d  %s  ink=%s advance=%d"
                  % (i, label(i), e, advance(data, i)))
            for y in range(fd.GLYPH_H):
                print("   |" + "".join(
                    ramp[fd.pixel(data, 0, i, x, y)] for x in range(fd.GLYPH_W)) + "|")
        return 0

    print("unknown command:", cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
