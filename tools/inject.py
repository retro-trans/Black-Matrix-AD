"""Write a replacement file back into the GD-ROM data track, in place.

redream JIT-compiles SH-4 blocks, so poking code into its live RAM has no
effect - the translated block is already cached.  Code patches therefore have
to reach the emulator through the disc.  A full image rebuild is not needed
while a replacement is no larger than the file it replaces: the high-density
track is plain MODE1/2352, so the file's own sectors can simply be rewritten
where they lie.

    python tools/inject.py list   build/disc/track3.bin
    python tools/inject.py put    build/disc/track3.bin 1ST_READ.BIN patched.bin
    python tools/inject.py relocate build/disc/track3.bin SCENARIO.DAT scenario.dat
    python tools/inject.py get    build/disc/track3.bin 1ST_READ.BIN out.bin

MODE1 sectors carry EDC/ECC after the 2048 user bytes.  Those are not
recomputed: redream does not check them.  A real console would, so anything
destined for hardware needs an EDC/ECC pass added here.
"""

import os
import struct
import sys

RAW_SECTOR = 2352
DATA_OFFSET = 16
HIGH_DENSITY_LBA = 45000
# User-data sectors 45022..111774 were verified to be entirely zero in the
# source image. Metadata occupies 45000..45021 and the root directory/first
# file begins at 111775, so this leaves a very large, deterministic expansion
# area without moving any other game file.
RELOCATION_LBA = 50000
RELOCATION_LIMIT = 111775


def _sector(f, lba):
    f.seek((lba - HIGH_DENSITY_LBA) * RAW_SECTOR + DATA_OFFSET)
    return f.read(2048)


def _extent(f, lba, size):
    return b"".join(_sector(f, lba + i)
                    for i in range((size + 2047) // 2048))[:size]


def _root_directory(f):
    pvd = _sector(f, HIGH_DENSITY_LBA + 16)
    if pvd[1:6] != b"CD001":
        raise ValueError("no ISO9660 volume descriptor at LBA 45016")
    root = pvd[156:190]
    return struct.unpack("<I", root[2:6])[0], struct.unpack("<I", root[10:14])[0]


def iso_records(f):
    """Yield file metadata plus its root-directory record location."""
    root_lba, root_size = _root_directory(f)
    data = _extent(f, root_lba, root_size)
    i = 0
    while i < len(data):
        record_pos = i
        rec_len = data[i]
        if rec_len == 0:
            i = (i // 2048 + 1) * 2048
            continue
        rec = data[i:i + rec_len]
        name_len = rec[32]
        name = rec[33:33 + name_len]
        i += rec_len
        if name_len == 1 and name in (b"\x00", b"\x01"):
            continue
        yield (name.decode("latin1").split(";")[0],
               struct.unpack("<I", rec[2:6])[0],
               struct.unpack("<I", rec[10:14])[0],
               root_lba + record_pos // 2048, record_pos % 2048)


def iso_files(f):
    """Yield (name, lba, size) for every file in the high-density track."""
    for name, lba, size, record_lba, record_offset in iso_records(f):
        yield name, lba, size


def find(f, name):
    for n, lba, size in iso_files(f):
        if n.upper() == name.upper():
            return lba, size
    raise KeyError("%s is not in the image" % name)


def find_record(f, name):
    for row in iso_records(f):
        if row[0].upper() == name.upper():
            return row
    raise KeyError("%s is not in the image" % name)


def _write_extent(f, lba, payload, sector_count=None):
    sector_count = sector_count or ((len(payload) + 2047) // 2048)
    for i in range(sector_count):
        chunk = payload[i * 2048:(i + 1) * 2048].ljust(2048, b"\x00")
        f.seek((lba - HIGH_DENSITY_LBA + i) * RAW_SECTOR + DATA_OFFSET)
        f.write(chunk)


def _update_record(f, record_lba, record_offset, lba, size):
    base = ((record_lba - HIGH_DENSITY_LBA) * RAW_SECTOR + DATA_OFFSET +
            record_offset)
    f.seek(base + 2)
    f.write(struct.pack("<I", lba) + struct.pack(">I", lba))
    f.write(struct.pack("<I", size) + struct.pack(">I", size))


def relocate(track, name, src):
    """Relocate SCENARIO.DAT into verified free ISO space and resize it."""
    if name.upper() != "SCENARIO.DAT":
        raise ValueError("only SCENARIO.DAT may use the reserved relocation area")
    payload = open(src, "rb").read()
    sectors = (len(payload) + 2047) // 2048
    target_end = RELOCATION_LBA + sectors
    if target_end > RELOCATION_LIMIT:
        raise ValueError("%s needs %d sectors; reserved range holds %d" %
                         (src, sectors, RELOCATION_LIMIT - RELOCATION_LBA))

    with open(track, "r+b") as f:
        found_name, old_lba, old_size, record_lba, record_offset = find_record(f, name)
        old_sectors = (old_size + 2047) // 2048

        # Prove the target does not overlap another ISO file, even if the disc
        # layout differs from the source image used to choose the reservation.
        for other_name, other_lba, other_size in iso_files(f):
            if other_name.upper() == name.upper():
                continue
            other_end = other_lba + (other_size + 2047) // 2048
            if RELOCATION_LBA < other_end and other_lba < target_end:
                raise ValueError("relocation would overlap %s at LBA %d" %
                                 (other_name, other_lba))

        # A first relocation may only consume zero user-data sectors. On a
        # subsequent build, the currently allocated prefix belongs to us;
        # only newly grown tail sectors still need the zero-space proof.
        owned = old_sectors if old_lba == RELOCATION_LBA else 0
        for i in range(owned, sectors):
            if any(_sector(f, RELOCATION_LBA + i)):
                raise ValueError("reserved relocation sector %d is not empty" %
                                 (RELOCATION_LBA + i))

        _write_extent(f, RELOCATION_LBA, payload)
        if old_lba == RELOCATION_LBA and old_sectors > sectors:
            _write_extent(f, RELOCATION_LBA + sectors, b"",
                          old_sectors - sectors)
        _update_record(f, record_lba, record_offset,
                       RELOCATION_LBA, len(payload))

    print("relocated %s to LBA %d (%d bytes, %d sectors)" %
          (name, RELOCATION_LBA, len(payload), sectors))


def put(track, name, src):
    payload = open(src, "rb").read()
    with open(track, "r+b") as f:
        lba, size = find(f, name)
        if len(payload) > size:
            raise ValueError("%s is %d bytes; %s holds %d - would overrun the "
                             "next file" % (src, len(payload), name, size))
        if len(payload) < size:
            payload += b"\x00" * (size - len(payload))
        for i in range((size + 2047) // 2048):
            f.seek((lba - HIGH_DENSITY_LBA + i) * RAW_SECTOR + DATA_OFFSET)
            f.write(payload[i * 2048:(i + 1) * 2048].ljust(2048, b"\x00"))
    print("wrote %s into %s at LBA %d (%d bytes)" % (src, name, lba, size))


def get(track, name, dst):
    with open(track, "rb") as f:
        lba, size = find(f, name)
        data = _extent(f, lba, size)
    open(dst, "wb").write(data)
    print("read %s (LBA %d, %d bytes) to %s" % (name, lba, size, dst))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd, track = argv[1], argv[2]
    if cmd == "list":
        with open(track, "rb") as f:
            for n, lba, size in iso_files(f):
                print("%-14s LBA %7d  %9d bytes  (%d sectors)"
                      % (n, lba, size, (size + 2047) // 2048))
        return 0
    if cmd == "put":
        put(track, argv[3], argv[4])
        return 0
    if cmd == "relocate":
        relocate(track, argv[3], argv[4])
        return 0
    if cmd == "get":
        get(track, argv[3], argv[4])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
