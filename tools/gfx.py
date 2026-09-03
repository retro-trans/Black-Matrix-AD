"""Small image helpers for poking at Black/Matrix AD graphics data.

No third-party deps: PNGs are written by hand with zlib.

    python tools/gfx.py pvr extracted/PARAMETA.DAT 0x7D1B0 out.png
    python tools/gfx.py font1 extracted/1ST_READ.BIN 0x40000 16 out.png
"""

import struct
import sys
import zlib


def write_png(path, width, height, rows_rgb):
    """rows_rgb: list of bytearray, each width*3 bytes."""
    raw = b"".join(b"\x00" + bytes(r) for r in rows_rgb)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    open(path, "wb").write(png)


def untwiddle_index(x, y):
    """Morton / Z-order index used by PowerVR square-twiddled textures."""
    n = 0
    for bit in range(16):
        n |= ((x >> bit) & 1) << (2 * bit)
        n |= ((y >> bit) & 1) << (2 * bit + 1)
    return n


def decode_pvr(data, offset):
    """Return (width, height, rows_rgb) for a PVRT at `offset`."""
    assert data[offset:offset + 4] == b"PVRT", "no PVRT here"
    px_fmt = data[offset + 8]
    dt_fmt = data[offset + 9]
    width, height = struct.unpack("<HH", data[offset + 12:offset + 16])
    body = offset + 16
    twiddled = dt_fmt in (0x01, 0x02, 0x03, 0x0D)

    def to_rgb(v):
        if px_fmt == 0x00:                      # ARGB1555
            r = (v >> 10) & 0x1F, (v >> 5) & 0x1F, v & 0x1F
            return ((r[0] * 255) // 31, (r[1] * 255) // 31, (r[2] * 255) // 31)
        if px_fmt == 0x01:                      # RGB565
            return (((v >> 11) & 0x1F) * 255 // 31,
                    ((v >> 5) & 0x3F) * 255 // 63,
                    (v & 0x1F) * 255 // 31)
        # ARGB4444
        a = ((v >> 12) & 0xF) * 255 // 15
        r = ((v >> 8) & 0xF) * 255 // 15
        g = ((v >> 4) & 0xF) * 255 // 15
        b = (v & 0xF) * 255 // 15
        return (r * a // 255, g * a // 255, b * a // 255)

    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            i = untwiddle_index(x, y) if twiddled else (y * width + x)
            v = struct.unpack_from("<H", data, body + 2 * i)[0]
            row += bytes(to_rgb(v))
        rows.append(row)
    return width, height, rows


def render_1bpp(data, offset, glyph, count, cols=32, invert=False):
    """Render `count` 1bpp glyph tiles of `glyph`x`glyph` as a contact sheet."""
    stride = (glyph + 7) // 8
    per = stride * glyph
    rows_n = (count + cols - 1) // cols
    W, H = cols * (glyph + 1), rows_n * (glyph + 1)
    rows = [bytearray(b"\x20" * (W * 3)) for _ in range(H)]
    for g in range(count):
        gx, gy = (g % cols) * (glyph + 1), (g // cols) * (glyph + 1)
        base = offset + g * per
        for y in range(glyph):
            for x in range(glyph):
                byte = data[base + y * stride + x // 8] if base + y * stride + x // 8 < len(data) else 0
                bit = (byte >> (7 - (x % 8))) & 1
                if invert:
                    bit ^= 1
                v = 255 if bit else 0x20
                p = ((gy + y) * W + gx + x) * 3
                rows[gy + y][gx * 3 + x * 3:gx * 3 + x * 3 + 3] = bytes((v, v, v))
    return W, H, rows


def render_raw16(data, offset, width, height, fmt="argb1555"):
    """Render untwiddled 16bpp pixel data straight out of a .DAT."""
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            i = offset + 2 * (y * width + x)
            v = data[i] | (data[i + 1] << 8) if i + 1 < len(data) else 0
            if fmt == "rgb565":
                row += bytes((((v >> 11) & 0x1F) * 255 // 31,
                              ((v >> 5) & 0x3F) * 255 // 63,
                              (v & 0x1F) * 255 // 31))
            else:
                row += bytes((((v >> 10) & 0x1F) * 255 // 31,
                              ((v >> 5) & 0x1F) * 255 // 31,
                              (v & 0x1F) * 255 // 31))
        rows.append(row)
    return rows


def render_4bpp(data, offset, glyph, count, cols=32):
    """Render `count` 4bpp (16 grey level) glyph tiles as a contact sheet."""
    per = (glyph * glyph) // 2
    rows_n = (count + cols - 1) // cols
    W, H = cols * (glyph + 1), rows_n * (glyph + 1)
    rows = [bytearray(b" " * (W * 3)) for _ in range(H)]
    for g in range(count):
        gx, gy = (g % cols) * (glyph + 1), (g // cols) * (glyph + 1)
        base = offset + g * per
        for y in range(glyph):
            for x in range(glyph):
                i = base + (y * glyph + x) // 2
                if i >= len(data):
                    continue
                nib = (data[i] & 0x0F) if (x % 2 == 0) else (data[i] >> 4)
                v = nib * 17
                off = (gx + x) * 3
                rows[gy + y][off:off + 3] = bytes((v, v, v))
    return W, H, rows


def render_2bpp(data, offset, glyph, count, cols=32, levels=(0x20, 0x88, 0xC8, 0xFF)):
    """Render `count` 2bpp glyph tiles (4 pixels per byte, LSB first)."""
    stride = (glyph * 2) // 8
    per = stride * glyph
    rows_n = (count + cols - 1) // cols
    W, H = cols * (glyph + 1), rows_n * (glyph + 1)
    rows = [bytearray(W * 3) for _ in range(H)]
    for g in range(count):
        gx, gy = (g % cols) * (glyph + 1), (g // cols) * (glyph + 1)
        base = offset + g * per
        for y in range(glyph):
            for x in range(glyph):
                i = base + y * stride + x // 4
                if i >= len(data):
                    continue
                px = (data[i] >> (2 * (x % 4))) & 3
                v = levels[px]
                o = (gx + x) * 3
                rows[gy + y][o:o + 3] = bytes((v, v, v))
    return W, H, rows


def upscale(rows, width, factor):
    if factor <= 1:
        return rows
    out = []
    for r in rows:
        big = bytearray()
        for x in range(width):
            big += bytes(r[x * 3:x * 3 + 3]) * factor
        out.extend([big] * factor)
    return out


def main(argv):
    cmd = argv[1]
    data = open(argv[2], "rb").read()
    if cmd == "pvr":
        w, h, rows = decode_pvr(data, int(argv[3], 0))
        write_png(argv[4], w, h, rows)
        print("wrote %s (%dx%d)" % (argv[4], w, h))
    elif cmd == "font1":
        offset, glyph = int(argv[3], 0), int(argv[4])
        count = int(argv[6]) if len(argv) > 6 else 512
        w, h, rows = render_1bpp(data, offset, glyph, count)
        write_png(argv[5], w, h, rows)
        print("wrote %s (%dx%d, %d glyphs of %dpx)" % (argv[5], w, h, count, glyph))
    elif cmd == "raw16":
        offset, w, h = int(argv[3], 0), int(argv[4]), int(argv[5])
        fmt = argv[7] if len(argv) > 7 else "argb1555"
        write_png(argv[6], w, h, render_raw16(data, offset, w, h, fmt))
        print("wrote %s (%dx%d %s @%08X)" % (argv[6], w, h, fmt, offset))
    elif cmd == "font2":
        offset, glyph = int(argv[3], 0), int(argv[4])
        count = int(argv[6]) if len(argv) > 6 else 256
        scale = int(argv[7]) if len(argv) > 7 else 1
        w, h, rows = render_2bpp(data, offset, glyph, count)
        rows = upscale(rows, w, scale)
        write_png(argv[5], w * scale, h * scale, rows)
        print("wrote %s (%dx%d, %d glyphs of %dpx 2bpp x%d)"
              % (argv[5], w * scale, h * scale, count, glyph, scale))
    elif cmd == "font4":
        offset, glyph = int(argv[3], 0), int(argv[4])
        count = int(argv[6]) if len(argv) > 6 else 256
        w, h, rows = render_4bpp(data, offset, glyph, count)
        write_png(argv[5], w, h, rows)
        print("wrote %s (%dx%d, %d glyphs of %dpx 4bpp)" % (argv[5], w, h, count, glyph))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
