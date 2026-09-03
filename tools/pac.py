"""List and extract Black/Matrix AD's nested archives.

Two layers:

  CMP2  the whole .DAT file
        0x00  "CMP2"
        0x04  u32 flags (always 0x08000040)
        0x08  u32 group count
        0x0C  (u32 sector_count, u32 end_sector) pairs, sectors of 2048 bytes
        each group is a PAC archive at start_sector * 2048

  PAC   one group
        0x00  "PAC "
        0x04  u32 flags (always 0x10000000)
        0x08  u32 member count
        0x0C  u32 total size, in 2-byte units
        0x20  u32 member offsets, in 2-byte units, relative to the PAC start
        member i spans offsets[i]*2 .. offsets[i+1]*2, the last one running to
        the total size

The font is SYSTEM.DAT, group 1, member 4 - file offset 0x424E0, 589,840 bytes,
magic "MFD ".  See docs/text-engine.md.

    python tools/pac.py list extracted/SYSTEM.DAT
    python tools/pac.py extract extracted/SYSTEM.DAT outdir [group member]
"""

import os
import struct
import sys

SECTOR = 2048


def groups(data):
    """Yield (index, file offset, byte length) for each PAC group."""
    if data[:4] != b"CMP2":
        raise ValueError("not a CMP2 container")
    n = struct.unpack_from("<I", data, 8)[0]
    for i in range(n):
        count, end = struct.unpack_from("<2I", data, 12 + 8 * i)
        start = end - count
        yield i, start * SECTOR, count * SECTOR


def members(data, pac):
    """Yield (index, file offset, byte length) for each member of a PAC.

    The count at +8 counts *offsets*, and the last one is an end marker rather
    than a member, so there are count-1 members.
    """
    if data[pac:pac + 4] != b"PAC ":
        return
    n = struct.unpack_from("<I", data, pac + 8)[0]
    offs = [struct.unpack_from("<I", data, pac + 32 + 4 * i)[0] for i in range(n)]
    for i in range(n - 1):
        yield i, pac + offs[i] * 2, (offs[i + 1] - offs[i]) * 2


def sniff(data, off, size):
    """Best guess at what a member holds."""
    magic = data[off:off + 4]
    for tag, name in ((b"MFD ", "font sheet"), (b"PVRT", "PVR texture"),
                      (b"GBIX", "PVR texture"), (b"PSI2", "script"),
                      (b"PAC ", "nested PAC")):
        if magic == tag:
            return "%s (%s)" % (name, magic.decode("latin1").strip())
    if not any(data[off:off + min(size, 4096)]):
        return "empty"
    return "?"


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd, path = argv[1], argv[2]
    data = open(path, "rb").read()
    name = os.path.basename(path)

    if cmd == "list":
        print("%s  %d bytes" % (name, len(data)))
        for gi, goff, glen in groups(data):
            tag = data[goff:goff + 4]
            if tag != b"PAC ":
                print("  group %-2d @0x%08X  %9d bytes  (no PAC header: %r)"
                      % (gi, goff, glen, tag))
                continue
            mem = list(members(data, goff))
            print("  group %-2d @0x%08X  %9d bytes  %d members"
                  % (gi, goff, glen, len(mem)))
            for mi, moff, mlen in mem:
                print("      [%2d] @0x%08X  %9d bytes  %s"
                      % (mi, moff, mlen, sniff(data, moff, mlen)))
        return 0

    if cmd == "extract":
        outdir = argv[3]
        want_g = int(argv[4], 0) if len(argv) > 4 else None
        want_m = int(argv[5], 0) if len(argv) > 5 else None
        os.makedirs(outdir, exist_ok=True)
        count = 0
        for gi, goff, glen in groups(data):
            if want_g is not None and gi != want_g:
                continue
            for mi, moff, mlen in members(data, goff):
                if want_m is not None and mi != want_m:
                    continue
                out = os.path.join(outdir, "%s_g%02d_m%02d.bin"
                                   % (name.split(".")[0], gi, mi))
                open(out, "wb").write(data[moff:moff + mlen])
                print("wrote %s (%d bytes, %s)"
                      % (out, mlen, sniff(data, moff, mlen)))
                count += 1
        print("%d member(s) extracted" % count)
        return 0

    print("unknown command:", cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
