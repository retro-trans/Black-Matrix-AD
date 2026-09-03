"""Replace one script line in place, without repacking anything.

Script text is stored as little-endian u16s holding SJIS codepoints, preceded
by an opcode and a length in 2-byte units.  As long as the replacement has the
same number of units the record can simply be overwritten where it lies, which
is enough to get English on screen and look at it before the real script
injection exists.

English is written into the full-width SJIS slots that tools/latin.py redraws,
so the game's own character decoder needs no change.

    python tools/patchline.py find  "全く、アンタはアタシに"
    python tools/patchline.py put   0xBD56 "Honestly, you worry me sick!"

`put` pads with full-width spaces and refuses to write anything longer than
the record it replaces.  Use \\n for the in-box line break (0xA0FF).
"""

import os
import struct
import sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import latin
import widths

SCENARIO = os.path.join(ROOT, "extracted", "SCENARIO.DAT")
OUT = os.path.join(ROOT, "build", "SCENARIO.vwf.dat")
LINE_BREAK = 0xA0FF
SPACE = 0x8140

# Stability baseline: retain the stock logical grid widths while isolating a
# scene-transition failure in the expanded window lifecycle. The VWF remains
# enabled, but script wrapping must match the stock grids until visual width is
# decoupled from the number of nodes the engine allocates.
COLS = 17
NARR_COLS = 19
ROW_PIXELS = 17 * 28

# Stock Japanese symbol glyphs needed by diary date placeholders. Unlike the
# Latin punctuation above, these keep their original FONT.BIN artwork.
STOCK_SYMBOLS = {
    "○": 0x819B, "×": 0x817E, "△": 0x81A2, "◇": 0x819E,
    "◎": 0x819D, "□": 0x81A0, "■": 0x81A1, "◆": 0x819F,
    "〇": 0x815A, "▽": 0x81A4, "〜": 0x8160,
    "☆": 0x8199, "★": 0x819A, "●": 0x819C,
    "♂": 0x8189, "♀": 0x818A, "▲": 0x81A3, "▼": 0x81A5,
}


def to_sjis(ch):
    """One character to the full-width SJIS codepoint the font provides."""
    if ch == "\n":
        return LINE_BREAK
    if ch in (" ", "\u3000"):
        return SPACE
    if ch == "\u30fb":
        return 0x8145
    if "0" <= ch <= "9":
        return 0x824F + (ord(ch) - ord("0"))
    if "A" <= ch <= "Z":
        return 0x8260 + (ord(ch) - ord("A"))
    if "a" <= ch <= "z":
        return 0x8281 + (ord(ch) - ord("a"))
    if ch in latin.PUNCT:
        return latin.PUNCT[ch]
    if ch in latin.EXTRA:
        return latin.EXTRA[ch]
    if ch in STOCK_SYMBOLS:
        return STOCK_SYMBOLS[ch]
    raise ValueError("no full-width slot for %r" % ch)


def _font_image():
    redrawn = os.path.join(ROOT, "build", "FONT.vwf.bin")
    return redrawn if os.path.exists(redrawn) else os.path.join(ROOT, "extracted", "FONT.BIN")


@lru_cache(maxsize=1)
def advances():
    """Return SJIS-codepoint advances measured from the installed font."""
    data = open(_font_image(), "rb").read()
    result = {}
    for ch in latin.charmap():
        code = to_sjis(ch)
        result[code] = widths.advance(data, latin.sjis_to_index(code))
    result[SPACE] = widths.SPACE_ADVANCE
    result[0x8145] = widths.advance(data, latin.sjis_to_index(0x8145))
    for code in STOCK_SYMBOLS.values():
        result[code] = widths.advance(data, latin.sjis_to_index(code))
    return result


def text_width(text, advance_map=None):
    advance_map = advances() if advance_map is None else advance_map
    return sum(advance_map.get(to_sjis(ch), widths.SPACE_ADVANCE) for ch in text)


def wrap(text, cols=COLS, max_pixels=ROW_PIXELS):
    """Break `text` on spaces using glyph advances and the cell-node limit.

    A word longer than either limit is left alone rather than split mid-word,
    which makes an exceptional overflow visible instead of silently mangling
    the text.
    """
    advance_map = advances()
    rows = []
    for para in text.split("\n"):
        row = ""
        for word in para.split(" "):
            if not row:
                row = word
            else:
                candidate = row + " " + word
                if len(candidate) <= cols and text_width(candidate, advance_map) <= max_pixels:
                    row = candidate
                else:
                    rows.append(row)
                    row = word
        rows.append(row)

    # A break after a row that is already full skips a whole row: the engine
    # computes the next row as (cell / cols + 1) * cols, and after exactly
    # `cols` characters the cursor has already moved on, so the break moves it
    # again.  A full row needs no break - the engine wraps there by itself, and
    # dropping the space at the same time keeps the next row flush left.
    out = []
    for i, row in enumerate(rows):
        out.append(row)
        if i < len(rows) - 1 and len(row) < cols:
            out.append("\n")
    return "".join(out)


def load():
    src = OUT if os.path.exists(OUT) else SCENARIO
    return bytearray(open(src, "rb").read()), src


def swapped(text):
    b = text.encode("shift_jis")
    return b"".join(bytes([b[i + 1], b[i]]) for i in range(0, len(b), 2))


def find(text):
    data, src = load()
    pat = swapped(text)
    i = data.find(pat)
    while i >= 0:
        op, ln = struct.unpack("<HH", data[i - 4:i])
        print("offset 0x%X  opcode %04X  %d units" % (i, op, ln))
        i = data.find(pat, i + 2)
    return 0


def put(off, text):
    data, src = load()
    op, ln = struct.unpack("<HH", data[off - 4:off])
    if op not in (0x0014, 0x0015, 0x001D):
        print("0x%X is not preceded by a text opcode (found %04X)" % (off, op))
        return 1
    text = wrap(text)
    words = [to_sjis(c) for c in text]
    if len(words) > ln:
        print("%d characters will not fit in a %d unit record:" % (len(words), ln))
        for r in text.split("\n"):
            print("    %2d  %r" % (len(r), r))
        return 1
    words += [SPACE] * (ln - len(words))
    data[off:off + 2 * ln] = b"".join(struct.pack("<H", w) for w in words)

    out_dir = os.path.dirname(OUT)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    open(OUT, "wb").write(bytes(data))
    print("patched 0x%X (%d units) in %s -> %s"
          % (off, ln, os.path.basename(src), os.path.basename(OUT)))
    for r in text.split("\n"):
        print("  %2d/%d  %r" % (len(r), COLS, r))
    return 0


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    if argv[1] == "find":
        return find(argv[2])
    if argv[1] == "put":
        return put(int(argv[2], 0), argv[3].replace("\\n", "\n"))
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
