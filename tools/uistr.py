"""List and patch the UI string table inside 1ST_READ.BIN.

The config screen's help lines are not in any archive - they sit in the
executable as a run of length-prefixed records:

    u16 count, then `count` u16 characters (SJIS codepoints, stored little
    endian, which is the same byte-swapped form the script uses)

The table starts at 0x882D4 in the file (0x8C0982D4 in RAM).  It is walked
sequentially, so a record can be rewritten in place as long as the count does
not change.

    python tools/uistr.py list [count]
    python tools/uistr.py put <file offset> "Type slower"
    python tools/uistr.py put-prefix <file offset> <preserved tail> "AP: LOW! "

`put` edits build/1ST_READ.vwf.bin when it exists, so it stacks on top of the
VWF patch rather than replacing it.  English goes into the full-width SJIS
slots that tools/latin.py redraws.

`put-prefix` does the same but retains a requested number of words at the end
of the record. This is for messages whose trailing words are runtime fields.
"""

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bmtext
import patchline

TABLE = 0x882D4
LOAD_BASE = 0x8C010000
ORIG = os.path.join(ROOT, "extracted", "1ST_READ.BIN")
PATCHED = os.path.join(ROOT, "build", "1ST_READ.vwf.bin")


def load():
    src = PATCHED if os.path.exists(PATCHED) else ORIG
    return bytearray(open(src, "rb").read()), src


def walk(data, start=TABLE, limit=40):
    off = start
    for _ in range(limit):
        if off + 2 > len(data):
            return
        n = struct.unpack_from("<H", data, off)[0]
        if n == 0 or n > 200 or off + 2 + 2 * n > len(data):
            return
        chars = [struct.unpack_from("<H", data, off + 2 + 2 * k)[0]
                 for k in range(n)]
        yield off + 2, n, "".join(bmtext.decode_char(c) for c in chars)
        off += 2 + 2 * n


def main(argv):
    data, src = load()
    cmd = argv[1] if len(argv) > 1 else "list"

    if cmd == "list":
        limit = int(argv[2], 0) if len(argv) > 2 else 20
        print("reading %s" % os.path.basename(src))
        for off, n, text in walk(data, limit=limit):
            print("  0x%06X (RAM %08X)  %2d  %s"
                  % (off, LOAD_BASE + off, n, text))
        return 0

    if cmd == "put":
        off = int(argv[2], 0)
        text = argv[3]
        n = struct.unpack_from("<H", data, off - 2)[0]
        if len(text) > n:
            print("%d characters will not fit in a %d character record"
                  % (len(text), n))
            return 1
        words = [patchline.to_sjis(c) for c in text]
        words += [patchline.SPACE] * (n - len(words))
        data[off:off + 2 * n] = b"".join(struct.pack("<H", w) for w in words)
        out_dir = os.path.dirname(PATCHED)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        open(PATCHED, "wb").write(bytes(data))
        print("patched 0x%X (%d chars) in %s -> %s"
              % (off, n, os.path.basename(src), os.path.basename(PATCHED)))
        print("  %r" % text)
        return 0

    if cmd == "put-prefix":
        off = int(argv[2], 0)
        preserve = int(argv[3], 0)
        text = argv[4]
        n = struct.unpack_from("<H", data, off - 2)[0]
        available = n - preserve
        if preserve < 0 or available < 0:
            print("cannot preserve %d words in a %d character record"
                  % (preserve, n))
            return 1
        if len(text) > available:
            print("%d characters will not fit in the %d-character prefix"
                  % (len(text), available))
            return 1
        words = [patchline.to_sjis(c) for c in text]
        words += [patchline.SPACE] * (available - len(words))
        data[off:off + 2 * available] = b"".join(
            struct.pack("<H", w) for w in words)
        out_dir = os.path.dirname(PATCHED)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        open(PATCHED, "wb").write(bytes(data))
        print("patched prefix 0x%X (%d chars, preserved %d) in %s -> %s"
              % (off, available, preserve, os.path.basename(src),
                 os.path.basename(PATCHED)))
        print("  %r" % text)
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
