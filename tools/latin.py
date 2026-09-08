"""Redraw the Latin glyphs in FONT.BIN as narrow, proportional forms.

The game ships full-width Latin: `Ａ` is 22 pixels of ink in a 24-pixel cell.
The variable-width patch already spaces glyphs by their ink, so that alone
only buys 1.7x.  Replacing the letterforms with real narrow ones takes the
same sentence from 980 pixels at the fixed 28-pixel pitch to about 215.

Glyphs are written into the full-width SJIS slots, so English text is encoded
as full-width SJIS and needs no change to the game's character decoder:

    0-9   SJIS 824F-8258   glyph 143-152
    A-Z   SJIS 8260-8279   glyph 160-185
    a-z   SJIS 8281-829A   glyph 193-218
    punctuation             the full-width ASCII forms, see PUNCT

Metrics are bounded by what reaches the screen: the VWF patch samples all
16 rows, so rows 0..15 are available. `choose_baseline` fits that band, preferring the
baseline of the font being replaced (y=11) so English and Japanese sit on the
same line, and moving up only when a font's descenders are deeper.

Only ink value 1 is written.  Values 2 and 3 are the font's anti-aliasing, but
which of them is the lighter shade depends on a palette that has not been
read, and value 1 is unambiguously the solid ink (it is 94% of all inked
pixels, and 95% of the pixels in the interior of a stroke).  Aliased text at a
9-pixel cap height is crisp rather than mushy, so this loses little.

    python tools/latin.py preview            # PNG of the result, zoomed
    python tools/latin.py build              # write build/FONT.vwf.bin
    python tools/latin.py build --font tahoma.ttf --size 12

The default source is the bundled Bizin Gothic Regular v0.0.4, licensed under
SIL OFL 1.1; see assets/fonts/bizin-gothic/LICENSE.txt and README.md. The
converted artwork is the BMAD Latin bitmap trial. A --font override may use
an absolute font path or a filename from the Windows fonts directory.
"""

import os
import sys
import string

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import fontdump as fd

from PIL import Image, ImageDraw, ImageFont

FONTS = r"C:\Windows\Fonts"
# Keep the font local to the project; no system-wide installation is needed.
DEFAULT_FONT = os.path.join(ROOT, 'assets', 'fonts', 'bizin-gothic',
                            'BizinGothic-Regular.ttf')
DEFAULT_SIZE = 19
MAX_INK_WIDTH = fd.GLYPH_W - 1
THRESHOLD = 110

BASELINE = 11                 # last row of a capital
MAX_ROW = 15                  # tools/vwf.py widens the sample to all 16 rows
CELL_W, CELL_H = fd.GLYPH_W, fd.GLYPH_H
LEFT = 1                      # leave one column before the ink
SS = 4                        # supersample before thresholding
# User-selected fuller letterforms; retain the 16-row height budget.
WIDE = 1.5

# ASCII to the full-width SJIS codepoint the script will be encoded with.
PUNCT = {
    "!": 0x8149, '"': 0x8168, "#": 0x8194, "$": 0x8190, "%": 0x8193,
    "&": 0x8195, "'": 0x8166, "(": 0x8169, ")": 0x816A, "*": 0x8196,
    "+": 0x817B, ",": 0x8143, "-": 0x817C, ".": 0x8144, "/": 0x815E,
    ":": 0x8146, ";": 0x8147, "<": 0x8183, "=": 0x8181, ">": 0x8184,
    "?": 0x8148, "@": 0x8197, "[": 0x816D, "]": 0x816E, "_": 0x8151,
    "~": 0x8160,
}
# Curly quotes and the dashes English text actually wants.
EXTRA = {
    "\u2018": 0x8165, "\u2019": 0x8166, "\u201c": 0x8167, "\u201d": 0x8168,
    "\u2014": 0x815C, "\u2013": 0x815C, "\u2026": 0x8163,
}


def sjis_to_index(code):
    for lo, hi, add in ((0x8140, 0x81BF, 0x7EC0),
                        (0x8240, 0x83BF, 0x7E40),
                        (0x889F, 0x9872, 0x7961)):
        if lo <= code <= hi:
            return (code + add) & 0xFFFF
    raise ValueError("SJIS %04X is not in a mapped range" % code)


def charmap(punct=True):
    """{character: glyph index} for everything this tool redraws."""
    m = {}
    for i in range(10):
        m[chr(ord("0") + i)] = sjis_to_index(0x824F + i)
    for i in range(26):
        m[chr(ord("A") + i)] = sjis_to_index(0x8260 + i)
        m[chr(ord("a") + i)] = sjis_to_index(0x8281 + i)
    if punct:
        for ch, code in PUNCT.items():
            m[ch] = sjis_to_index(code)
        for ch, code in EXTRA.items():
            m[ch] = sjis_to_index(code)
    return m


# --- glyph encoding --------------------------------------------------------

def blank_record():
    return bytearray(fd.GLYPH)


def set_pixel(rec, x, y, v):
    """Write one pixel into a 128-byte glyph record.

    The inverse of fontdump.pixel: two 16x16 twiddled tiles, 2bpp, four
    pixels per byte, most significant pair leftmost.
    """
    plane, xx = (0, x) if x < 16 else (1, x - 16)
    i = fd._TWIDDLE[y][xx]
    o = plane * fd.PLANE + (i >> 2)
    shift = 6 - 2 * (i & 3)
    rec[o] = (rec[o] & ~(3 << shift)) | ((v & 3) << shift)


PAD = 24


def _gray(font, ch, wide):
    """Greyscale render of one character, with the pen at (PAD * wide, PAD).

    Drawn at SS times the target size and scaled back down, which both gives
    the threshold something better than a 1-bit rasteriser to work from and
    makes a horizontal stretch possible: the vertical scale stays SS:1 while
    the horizontal one becomes SS/wide, so `wide` widens the letterforms
    without touching the metrics that matter.
    """
    w, h = CELL_W + 2 * PAD, CELL_H + 2 * PAD
    big = Image.new("L", (w * SS, h * SS), 0)
    # anchor "ls" puts the pen on the baseline, which is how the metrics of
    # the font being replaced are defined
    ImageDraw.Draw(big).text((PAD * SS, PAD * SS), ch, fill=255,
                             font=font, anchor="ls")
    return big.resize((int(round(w * wide)), h), Image.LANCZOS)


def _ink(font, ch, threshold, wide=WIDE, max_width=None):
    """Ink pixels of one character, relative to the pen at (0, baseline)."""
    img = _gray(font, ch, wide)
    if max_width is not None:
        if not 1 <= max_width < CELL_W:
            raise ValueError('ink width must fit the glyph cell with its left margin')
        bbox = img.point(lambda v: 255 if v >= threshold else 0).getbbox()
        if bbox and bbox[2] - bbox[0] > max_width:
            # Wide punctuation (especially em dashes) must obey the same cap.
            # Resample only X, retaining all vertical rows and the baseline.
            img = img.crop((bbox[0], 0, bbox[2], img.height)).resize(
                (max_width, img.height), Image.Resampling.LANCZOS)
    px = img.load()
    penx = int(round(PAD * wide))
    # y is relative to the pen: the last row of a capital comes out at -1
    return [(x - penx, y - PAD) for y in range(img.height) for x in range(img.width)
            if px[x, y] >= threshold]


def choose_baseline(font, chars, threshold=THRESHOLD, wide=WIDE, max_width=None):
    """The lowest baseline that still fits every ascender and descender.

    Only rows 0..15 of the cell reach the screen, so a font whose descenders
    are deeper than the one it replaces has to sit higher.  Preferring the
    original baseline keeps English and Japanese on the same line when both
    are on screen.
    """
    top, bottom = 0, -1
    for ch in chars:
        ink = _ink(font, ch, threshold, wide, max_width)
        if not ink:
            continue
        top = min(top, min(y for _, y in ink))
        bottom = max(bottom, max(y for _, y in ink))
    # cell row = relative row + baseline + 1, so a capital ends on `baseline`
    base = min(BASELINE, MAX_ROW - 1 - bottom)
    if base + 1 + top < 0:
        base = -1 - top
    return base


def render_glyph(font, ch, baseline, threshold=THRESHOLD, wide=WIDE, max_width=None):
    """Draw one character into a fresh glyph record, or None if it is blank."""
    ink = _ink(font, ch, threshold, wide, max_width)
    if not ink:
        return None, 0
    x0 = min(x for x, _ in ink)

    rec = blank_record()
    clipped = 0
    for x, y in ink:
        gx, gy = x - x0 + LEFT, y + baseline + 1
        if 0 <= gx < CELL_W and 0 <= gy <= MAX_ROW:
            set_pixel(rec, gx, gy, 1)
        else:
            clipped += 1
    return rec, clipped


def build(font_name=DEFAULT_FONT, size=DEFAULT_SIZE, punct=True,
          threshold=THRESHOLD, mark=False, wide=WIDE, max_width=MAX_INK_WIDTH):
    """`mark` draws a bar across rows 14 and 15 of every glyph.

    Those rows are blank in every stock glyph and are only visible if the
    patch has widened the renderer's sample from 14 rows to 16, so the bar
    showing up on screen is a direct yes/no answer to whether that worked in
    a given window.
    """
    data = bytearray(open(os.path.join(ROOT, "extracted", "FONT.BIN"), "rb").read())
    m = charmap(punct)
    # Fit letters/digits first: oversized quotes/brackets must not shrink the
    # entire alphabet. All letters retain one size and natural proportions.
    body_chars = [ch for ch in m if ch in string.ascii_letters + string.digits]
    for size in range(size, 6, -1):
        font = ImageFont.truetype(os.path.join(FONTS, font_name), size * SS)
        top, bottom = 0, -1
        for ch in body_chars:
            ink = _ink(font, ch, threshold, wide, max_width)
            if not ink:
                continue
            top = min(top, min(y for _, y in ink))
            bottom = max(bottom, max(y for _, y in ink))
        if bottom - top + 1 <= MAX_ROW + 1:
            break
    baseline = choose_baseline(font, body_chars, threshold, wide, max_width)
    clipped = {}
    for ch, index in sorted(m.items(), key=lambda kv: kv[1]):
        glyph_font = font
        # Keep punctuation on the common baseline, reducing only an outlier's
        # point size until it fits. Never crop descenders or stretch Y alone.
        if ch not in body_chars:
            for glyph_size in range(size, 6, -1):
                glyph_font = ImageFont.truetype(os.path.join(FONTS, font_name), glyph_size * SS)
                ink = _ink(glyph_font, ch, threshold, wide, max_width)
                if all(0 <= y + baseline + 1 <= MAX_ROW for _, y in ink):
                    break
        rec, lost = render_glyph(glyph_font, ch, baseline, threshold, wide, max_width)
        if rec is None:
            continue
        if lost:
            clipped[ch] = lost
        if mark:
            for x in range(2, 12):
                set_pixel(rec, x, 14, 1)
                set_pixel(rec, x, 15, 1)
        o = fd.HEADER + index * fd.GLYPH
        data[o:o + fd.GLYPH] = rec
    return bytes(data), m, clipped, baseline


# --- preview ---------------------------------------------------------------

def preview(data, text, path, zoom=4, gap=0):
    """Render `text` out of a font image using the game's own decoder.

    Going back through fontdump.pixel is the point: it checks the encoder
    round-trips, rather than showing what PIL drew.
    """
    m = charmap()
    cells = []
    for ch in text:
        if ch == " ":
            cells.append(None)
            continue
        if ch not in m:
            continue
        cells.append(m[ch])

    # lay the glyphs out with the same pen the patch uses
    pen = 0
    placed = []
    for index in cells:
        if index is None:
            pen += 6
            continue
        cols = [x for x, y, v in fd.pixels(data, 0, index) if v]
        if not cols:
            pen += 6
            continue
        lo, hi = min(cols), max(cols)
        placed.append((index, pen - lo))
        pen += (hi - lo + 1) + 1 + gap

    W, H = pen + 4, CELL_H
    img = Image.new("L", (W, H), 0)
    px = img.load()
    for index, ox in placed:
        for x, y, v in fd.pixels(data, 0, index):
            if v and 0 <= ox + x < W:
                px[ox + x, y] = 255 if v == 1 else 160
    return img.resize((W * zoom, H * zoom), Image.NEAREST), pen


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "preview"
    font_name = DEFAULT_FONT
    size = DEFAULT_SIZE
    if "--font" in argv:
        font_name = argv[argv.index("--font") + 1]
    if "--size" in argv:
        size = int(argv[argv.index("--size") + 1])
    punct = "--no-punct" not in argv

    wide = float(argv[argv.index("--wide") + 1]) if "--wide" in argv else WIDE
    max_width = int(argv[argv.index('--max-width')+1]) if '--max-width' in argv else MAX_INK_WIDTH
    data, m, clipped, baseline = build(font_name, size, punct,
                                       mark="--mark" in argv, wide=wide, max_width=max_width)

    if clipped:
        raise ValueError('glyphs would clip: %r' % clipped)

    out_dir = os.path.join(ROOT, "build")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    if cmd == "preview":
        sample = ("Handgloves 0123 The quick brown fox jumps over the lazy dog. "
                  "Why, what's that? (A test!)")
        img, width = preview(data, sample, None, zoom=4)
        p = os.path.join(out_dir, "latin_preview.png")
        img.convert("RGB").save(p)
        print("wrote %s" % p)
        print("%d characters, %d pixels with the patch's own pen"
              % (len(sample), width))
        print("the same text at the fixed 28px pitch: %d pixels" % (len(sample) * 28))
        print("baseline y=%d (the font it replaces uses %d)" % (baseline, BASELINE))
        return 0

    if cmd == "build":
        p = os.path.join(out_dir, "FONT.vwf.bin")
        open(p, "wb").write(data)
        print("wrote %s (%d bytes, %d glyphs redrawn from %s %dpx, baseline y=%d)"
              % (p, len(data), len(m), font_name, size, baseline))
        return 0

    if cmd == "install":
        # The sheet is stored raw inside SYSTEM.DAT; see docs/text-engine.md.
        SYSTEM_OFF = 0x424E0
        src = os.path.join(ROOT, "extracted", "SYSTEM.DAT")
        dat = bytearray(open(src, "rb").read())
        if bytes(dat[SYSTEM_OFF:SYSTEM_OFF + 4]) != b"MFD ":
            print("SYSTEM.DAT does not hold the font at %X" % SYSTEM_OFF)
            return 1
        dat[SYSTEM_OFF:SYSTEM_OFF + len(data)] = data
        q = os.path.join(out_dir, "SYSTEM.vwf.dat")
        open(q, "wb").write(bytes(dat))
        r = os.path.join(out_dir, "FONT.vwf.bin")
        open(r, "wb").write(data)
        print("wrote %s and %s" % (r, q))
        print("  %d glyphs from %s, requested %dpx, stretch %.2f, baseline y=%d"
              % (len(m), font_name, size, wide, baseline))
        print('  ink width capped at %dpx; bitmap height budget %dpx' % (max_width, CELL_H))
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
