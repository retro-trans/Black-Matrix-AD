"""
Black/Matrix AD (Dreamcast) — script text extraction.

Findings about the on-disc format:
  * Disc is a GD-ROM dump; the high-density data track starts at LBA 45000
    and holds a plain ISO9660 volume (BLACKMATRIXAD).
  * SCENARIO.DAT is a "CMP2" container: u32 magic, u32 flags, u32 group_count,
    then group_count (count, running_total) u32 pairs. Payload blocks begin at
    0x1800, each 2048-aligned and tagged "PSI22.00".
  * Script text is stored as **byte-swapped Shift-JIS**: each character is a
    little-endian u16 holding the big-endian SJIS codepoint. Searching for raw
    SJIS finds nothing, which is why this looked encrypted at first.
  * Text opcodes (all u16 LE):
        0x0014 <len> <len chars>   narration / inner monologue (no portrait)
        0x0015 <len> <len chars>   spoken dialogue (portrait box)
        0x001D <len> <len chars> <u32 target>
                                   selectable menu choice + branch target
        0x001A 0x0001 0x0000 <u32> voice-clip id for the next line
        0x0018 0x0017              end of text / wait for input
    <len> counts 2-byte units, line breaks included.
  * 0xA0FF is the in-box line break.
  * ~20 codepoints live in unassigned SJIS gaps (0x8246, 0x8247, 0x824B,
    0x824D, 0x824E, 0x825C, 0x827D-0x827F, 0x8280, 0x829B-0x829D, 0x81AF,
    0x81B2-0x81B4, 0x81B7, 0x8240). These are gaiji: JIS level-2 kanji the
    font keeps as custom glyphs. See GAIJI below for the mapping inferred
    from context.
"""

import io
import os
import struct
import sys

RAW_SECTOR = 2352
DATA_OFFSET = 16
HIGH_DENSITY_LBA = 45000
LINE_BREAK = 0xA0FF
DYNAMIC_MASTER_NAME = 0xB001
DYNAMIC_MASTER_NAME_TOKEN = "{MASTER_NAME}"

# JIS level-2 kanji the game keeps as custom font glyphs, in unassigned SJIS
# slots. Readings deduced from surrounding text, not from the font bitmap.
GAIJI = {
    0x8240: "扈",   # 跋扈する
    0x8246: "?",
    0x8247: "戮",   # 大量殺戮
    0x824B: "?",
    0x824D: "綺",   # 綺麗な水辺
    0x824E: "?",
    0x825C: "痺",   # 手足が完全に痺れ
    0x827D: "躰",   # 何て躰が重いんだ
    0x827E: "炒",   # 炒めて・焼いて / カカオの実を炒って
    0x827F: "悸",   # 動悸が激しくなって
    0x8280: "哺",   # 哺乳類
    0x829B: "蕪",   # ネギや大根・蕪
    0x829C: "籠",   # 駕籠の鳥
    0x829D: "嗅",   # 血の匂いを嗅いでいると
    0x81AF: "?",
    0x81B2: "蠅",   # 体にたかる蠅
    0x81B3: "驕",   # 『驕り』/ 七つの美徳：驕り
    0x81B4: "?",
    0x81B7: "跋",   # 跋扈する
}


def iso_files(bin_path):
    """Yield (name, lba, size) for every file in the GD-ROM data track."""
    with open(bin_path, "rb") as f:
        def sector(lba):
            f.seek((lba - HIGH_DENSITY_LBA) * RAW_SECTOR + DATA_OFFSET)
            return f.read(2048)

        def extent(lba, size):
            return b"".join(sector(lba + i) for i in range((size + 2047) // 2048))[:size]

        pvd = sector(HIGH_DENSITY_LBA + 16)
        if pvd[1:6] != b"CD001":
            raise ValueError("no ISO9660 volume descriptor at LBA 45016")
        root = pvd[156:190]
        data = extent(struct.unpack("<I", root[2:6])[0],
                      struct.unpack("<I", root[10:14])[0])
        i = 0
        while i < len(data):
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
                   struct.unpack("<I", rec[10:14])[0])


def extract_file(bin_path, lba, size, out_path):
    with open(bin_path, "rb") as f, open(out_path, "wb") as out:
        remaining = size
        for i in range((size + 2047) // 2048):
            f.seek((lba - HIGH_DENSITY_LBA + i) * RAW_SECTOR + DATA_OFFSET)
            out.write(f.read(2048)[:min(2048, remaining)])
            remaining -= 2048


def decode_char(word):
    if word == LINE_BREAK:
        return "\n"
    if word == DYNAMIC_MASTER_NAME:
        return DYNAMIC_MASTER_NAME_TOKEN
    if word in GAIJI:
        return GAIJI[word]
    hi, lo = word >> 8, word & 0xFF
    if hi == 0:
        return chr(lo) if 0x20 <= lo <= 0x7E else "{%02X}" % lo
    try:
        return bytes([hi, lo]).decode("shift_jis")
    except UnicodeDecodeError:
        return "{%04X}" % word


def _printable(word):
    return (word in (LINE_BREAK, DYNAMIC_MASTER_NAME) or word in GAIJI or (word >> 8) >= 0x81
            or ((word >> 8) == 0 and 0x20 <= (word & 0xFF) <= 0x7E))


def strings(data):
    """Yield (offset, kind, voice_id, text) for every text opcode in `data`."""
    i, n, voice = 0, len(data), None
    word = lambda p: data[p] | (data[p + 1] << 8)
    while i + 4 <= n:
        op = word(i)
        if op == 0x001A and i + 12 <= n and word(i + 2) == 1 and word(i + 4) == 0:
            voice = struct.unpack("<I", data[i + 8:i + 12])[0]
            i += 12
            continue
        if op in (0x0014, 0x0015, 0x001D, 0x0020):
            length = word(i + 2)
            if 0 < length <= 0x200 and i + 4 + 2 * length <= n:
                chars = [word(i + 4 + 2 * k) for k in range(length)]
                if all(map(_printable, chars)):
                    kind = {
                        0x0014: "NARR", 0x0015: "TALK",
                        0x001D: "PICK", 0x0020: "PROMPT",
                    }[op]
                    yield (i, kind, voice, "".join(map(decode_char, chars)))
                    voice = None
                    i += 4 + 2 * length + (4 if op == 0x001D else 0)
                    continue
        i += 2


def main(argv):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if len(argv) < 2:
        print(__doc__)
        print("usage: bmtext.py list <disc.bin>")
        print("       bmtext.py unpack <disc.bin> <outdir> [NAME.DAT ...]")
        print("       bmtext.py dump <FILE.DAT> [start] [end]")
        return 1
    cmd = argv[1]
    if cmd == "list":
        for name, lba, size in iso_files(argv[2]):
            print("%10d  %8d  %s" % (size, lba, name))
    elif cmd == "unpack":
        bin_path, outdir, wanted = argv[2], argv[3], set(argv[4:])
        os.makedirs(outdir, exist_ok=True)
        for name, lba, size in iso_files(bin_path):
            if wanted and name not in wanted:
                continue
            extract_file(bin_path, lba, size, os.path.join(outdir, name))
            print("extracted %s (%d bytes)" % (name, size))
    elif cmd == "dump":
        data = open(argv[2], "rb").read()
        lo = int(argv[3], 0) if len(argv) > 3 else 0
        hi = int(argv[4], 0) if len(argv) > 4 else len(data)
        for offset, kind, voice, text in strings(data):
            if lo <= offset <= hi:
                print("%08X %s v=%s | %s" % (
                    offset, kind, "%04X" % voice if voice is not None else "----",
                    text.replace("\n", " / ")))
    else:
        print("unknown command:", cmd)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
