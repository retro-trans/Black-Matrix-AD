"""Repack translated text into a fixed-size or relocatable SCENARIO.DAT.

SCENARIO.DAT is a CMP2 table of independently loaded, sector-aligned PSI2
programs.  Text records inside a PSI2 program are variable length, so making
one record longer moves every statement after it.  This tool rebuilds the
affected programs, relocates every branch-target operand found by decoding
the statement stream with the interpreter's real grammar (tools/psi2.py),
then rebuilds the CMP2 sector table.  Both the original and the rebuilt
program must decode cleanly, with every branch target on a statement
boundary, or the build stops.

The original file occupies exactly the sectors before SOUND.DAT and cannot
grow in place. With ``--expand`` the output ends at its physical CMP2 payload
instead of being padded to the original extent; inject.py can relocate that
file into verified free ISO space when the complete translation outgrows its
old allocation.

    python tools/scriptpack.py script/en/intro.en.tsv
    python tools/scriptpack.py --out build/SCENARIO.vwf.dat script/en/*.en.tsv
"""

import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bmtext
import build_script
import patchline
import psi2

SECTOR = 2048
SCENARIO = os.path.join(ROOT, "extracted", "SCENARIO.DAT")
OUT = os.path.join(ROOT, "build", "SCENARIO.vwf.dat")
PSI_MAGIC = b"PSI22.00"
MAX_LINE_UNITS = 192

# Statement 0x1D is a menu choice. Its handler (0x8C08C8E6) copies each option
# into a buffer with a fixed 15-word stride and caps the copy at 15 units, so a
# stored option longer than this is truncated on screen and, worse, makes the
# whole menu over-read into the next option. Keep every choice option at or
# under this many stored u16 units.
MENU_CHOICE_STATEMENT = 0x1D
MENU_CHOICE_MAX_UNITS = 15

# Every choice-menu option whose stored count exceeds MENU_CHOICE_MAX_UNITS,
# collected across all repacked groups so the build can report them together.
# This is a warning rather than a hard failure only because the English script
# still carries a backlog of pre-existing over-limit menu options (mostly in
# not-yet-play-tested ch2-4 menus). Once that backlog is cleared, promote this
# to a build-stopping error.
MENU_OVERSIZE = []


def align_sector(n):
    return (n + SECTOR - 1) // SECTOR * SECTOR


def cmp2_entries(data):
    if data[:4] != b"CMP2":
        raise ValueError("SCENARIO.DAT is not a CMP2 container")
    count = struct.unpack_from("<I", data, 8)[0]
    if 12 + count * 8 > len(data):
        raise ValueError("CMP2 group table is truncated")
    return [struct.unpack_from("<II", data, 12 + i * 8)
            for i in range(count)]


def split_groups(data):
    groups = []
    previous_end = 0
    for i, (count, end) in enumerate(cmp2_entries(data)):
        # The runtime starts each group at the preceding table entry's end;
        # the current entry supplies its sector count and new cumulative end.
        # In original archives this equals end-count, but enforcing the real
        # invariant prevents non-contiguous/shared entries that validate on
        # disk yet make the game load the wrong group.
        if end != previous_end + count:
            raise ValueError("CMP2 group %d is non-contiguous: previous end "
                             "%d + count %d != end %d"
                             % (i, previous_end, count, end))
        start = previous_end * SECTOR
        finish = end * SECTOR
        if finish > len(data):
            raise ValueError("CMP2 group %d extends past the file" % i)
        groups.append(data[start:finish])
        previous_end = end
    return groups


def encode_text(text, cols=patchline.COLS):
    wrapped = patchline.wrap(text, cols=cols)
    words = [patchline.to_sjis(ch) for ch in wrapped]
    if len(words) > MAX_LINE_UNITS:
        raise ValueError("translated line has %d units; runtime limit is %d"
                         % (len(words), MAX_LINE_UNITS))
    return wrapped, b"".join(struct.pack("<H", word) for word in words)


def preserve_record_alignment(encoded, old_length):
    """Keep following PSI instructions at their original modulo-4 offset.

    PSI's typed-operand reader aligns 32-bit payloads from the current program
    pointer. The compiler places padding relative to each instruction's
    original address, so moving a later instruction by two bytes makes the
    runtime align into the middle of its value. Text records are u16 arrays;
    an invisible trailing full-width space changes their size by two bytes and
    restores the original parity without adding an opcode outside the record.
    """
    units = len(encoded) // 2
    if (units - old_length) & 1:
        encoded += struct.pack("<H", patchline.SPACE)
        units += 1
    if units > MAX_LINE_UNITS:
        raise ValueError("alignment padding makes translated line %d units; "
                         "runtime limit is %d" % (units, MAX_LINE_UNITS))
    return encoded


def _position_mapper(changes):
    """Map a byte position in the original PSI2 program to its new position."""
    def mapped(pos):
        delta = 0
        for start, old_end, replacement in changes:
            if pos < start:
                break
            if start < pos < old_end:
                raise ValueError("offset %X points inside replaced text at %X"
                                 % (pos, start))
            if pos >= old_end:
                delta += len(replacement) - (old_end - start)
        return pos + delta
    return mapped


def repack_psi(program, replacements):
    """Return (sector-padded program, old->new text offsets, relocated refs)."""
    if program[:8] != PSI_MAGIC:
        raise ValueError("translated offsets do not belong to a PSI22.00 group")
    final_record = struct.unpack_from("<I", program, 12)[0]
    used_end = final_record + 16
    if not (16 <= final_record and used_end <= len(program)):
        raise ValueError("invalid PSI2 final-record offset %X" % final_record)
    if any(program[used_end:]):
        raise ValueError("PSI2 group has nonzero data after its final record")

    # Decode the statement stream with the interpreter's real grammar.  This
    # yields every branch-target operand (st 0x02/0x03 jumps and st 0x1D
    # choice targets, stored as file offset minus 0x10) and proves that each
    # lands on a statement boundary before anything is moved.
    walked = psi2.walk(program)

    records = {}
    text_records = []
    for off, kind, voice, text in bmtext.strings(program[:used_end]):
        length = struct.unpack_from("<H", program, off + 2)[0]
        records[off] = (kind, length, text)
        text_records.append((off, kind, length))

    walked_texts = set(walked.texts)
    for off in replacements:
        if off not in walked_texts:
            raise ValueError("translated offset %X is not a text statement "
                             "in the decoded program" % off)

    # Choice-menu records (statement 0x1D) are stored by the interpreter in a
    # fixed 15-word-per-option buffer (handler 0x8C08C8E6), but the menu's
    # column width comes from the *uncapped* longest option. A stored count
    # above 15 makes every row over-read one word into the next option's slot,
    # painting that option's leading glyph at the far right of every row (the
    # stale "V" of "Virtue" seen in the occult-library menu). Collect any such
    # option below so the build can report it.
    choice_offsets = {pos for pos in walked.boundaries
                      if struct.unpack_from("<H", program, pos)[0]
                      == MENU_CHOICE_STATEMENT}

    changes = []
    expected = {}
    for off, text in sorted(replacements.items()):
        if off not in records:
            raise ValueError("offset %X is not a text record in its PSI2 group" % off)
        kind, old_length, old_text = records[off]
        # Only dialogue/narration receive extra native cell nodes. Preserve
        # the existing wrapping of independent menu and prompt records.
        cols = (patchline.NARR_COLS if kind == "NARR" else
                patchline.COLS if kind == "TALK" else 17)
        wrapped, encoded = encode_text(text, cols=cols)
        encoded = preserve_record_alignment(encoded, old_length)
        if off in choice_offsets and len(encoded) // 2 > MENU_CHOICE_MAX_UNITS:
            MENU_OVERSIZE.append((off, len(encoded) // 2, wrapped))
        replacement = program[off:off + 2] + struct.pack("<H", len(encoded) // 2) + encoded
        old_end = off + 4 + old_length * 2
        if (len(replacement) - (old_end - off)) % 4:
            raise ValueError("translated record at %X changes PSI alignment" % off)
        changes.append((off, old_end, replacement))
        expected[off] = (kind, wrapped, encoded)

    mapped = _position_mapper(changes)

    rebuilt = bytearray()
    cursor = 0
    for start, old_end, replacement in changes:
        if start < cursor:
            raise ValueError("overlapping text records at %X" % start)
        rebuilt += program[cursor:start]
        rebuilt += replacement
        cursor = old_end
    rebuilt += program[cursor:used_end]

    # Header+0x0C stores the used program length minus 16, not a relocatable
    # instruction address. It can therefore fall inside the final text record
    # (for example group 8 ends with a text payload spanning 0x2CC..0x2EA
    # while this field is 0x2E0). Recompute it from the rebuilt byte length;
    # treating it as a position made valid final-line replacements fail.
    struct.pack_into("<I", rebuilt, 12, len(rebuilt) - 16)

    # Relocate every branch-target operand.  Stored values are file offsets
    # minus TARGET_BIAS; the operand fields themselves also move with the
    # stream.  Alignment padding survives because each replacement preserves
    # its size modulo 4.
    relocated = 0
    for field_pos, stored in walked.targets:
        new_field = mapped(field_pos)
        new_stored = mapped(stored + psi2.TARGET_BIAS) - psi2.TARGET_BIAS
        struct.pack_into("<I", rebuilt, new_field, new_stored)
        if new_stored != stored:
            relocated += 1

    # Re-decode the rebuilt program.  walk() re-checks the whole grammar and
    # that every relocated branch target lands on a statement boundary.
    try:
        rewalked = psi2.walk(bytes(rebuilt))
    except ValueError as e:
        raise ValueError("rebuilt PSI2 group does not decode: %s" % e)
    new_boundaries = rewalked.boundaries
    for field_pos, stored in walked.targets:
        old_file = stored + psi2.TARGET_BIAS
        if mapped(old_file) not in new_boundaries:
            raise ValueError("relocated branch target %X -> %X is not a "
                             "statement boundary"
                             % (old_file, mapped(old_file)))

    new_records = {off: kind for off, kind, voice, text
                   in bmtext.strings(bytes(rebuilt))}
    new_texts = set(rewalked.texts)
    offset_map = {}
    for old_off, (wanted_kind, wrapped, encoded) in expected.items():
        new_off = mapped(old_off)
        got_kind = new_records.get(new_off)
        got_length = struct.unpack_from("<H", rebuilt, new_off + 2)[0]
        got_text = bytes(rebuilt[new_off + 4:new_off + 4 + got_length * 2])
        if got_kind != wanted_kind or got_length != len(encoded) // 2 or got_text != encoded:
            raise ValueError("translated record verification failed at %X -> %X"
                             % (old_off, new_off))
        if new_off not in new_texts:
            raise ValueError("translated record at %X -> %X is not a text "
                             "statement in the rebuilt program"
                             % (old_off, new_off))
        offset_map[old_off] = new_off

    padded = bytes(rebuilt).ljust(align_sector(len(rebuilt)), b"\x00")
    return padded, offset_map, relocated, len(rebuilt) - used_end


def load_translations(paths):
    translations = {}
    for path in paths:
        for off, text in build_script.load_en(path).items():
            if off in translations and translations[off] != text:
                raise ValueError("conflicting translations for offset %X" % off)
            translations[off] = text
    return translations


def rebuild(source, translations, fixed_size=True):
    entries = cmp2_entries(source)
    groups = split_groups(source)
    if not groups or len(groups[0]) < 12 + len(groups) * 8:
        raise ValueError("CMP2 header group is too small")

    by_group = {}
    for absolute in translations:
        found = None
        for i, (count, end) in enumerate(entries):
            start = (end - count) * SECTOR
            if start <= absolute < end * SECTOR:
                found = (i, absolute - start)
                break
        if found is None:
            raise ValueError("translation offset %X is outside CMP2 groups" % absolute)
        i, relative = found
        by_group.setdefault(i, {})[relative] = translations[absolute]

    rebuilt_groups = list(groups)
    local_maps = {}
    relocated_refs = 0
    text_growth = 0
    for i, replacements in sorted(by_group.items()):
        rebuilt, offsets, refs, growth = repack_psi(groups[i], replacements)
        rebuilt_groups[i] = rebuilt
        local_maps[i] = offsets
        relocated_refs += refs
        text_growth += growth

    header_sectors = max(entries[0][0],
                         int(math.ceil((12 + len(groups) * 8) / float(SECTOR))))
    header = bytearray(groups[0][:header_sectors * SECTOR])
    if len(header) < header_sectors * SECTOR:
        header += b"\x00" * (header_sectors * SECTOR - len(header))
    out = bytearray(header)
    new_entries = [(header_sectors, header_sectors)]
    placeholders = 0
    new_starts = {0: 0}

    for i in range(1, len(rebuilt_groups)):
        group = rebuilt_groups[i]
        if len(group) == SECTOR and group == b"\x11" * SECTOR:
            placeholders += 1
        start = len(out) // SECTOR
        out += group
        count = len(group) // SECTOR
        new_entries.append((count, start + count))
        new_starts[i] = start * SECTOR

    for i, (count, end) in enumerate(new_entries):
        struct.pack_into("<II", out, 12 + i * 8, count, end)

    physical_size = len(out)
    if fixed_size:
        if physical_size > len(source):
            raise ValueError("repacked SCENARIO.DAT is %d bytes too large; "
                             "use --expand and relocate it"
                             % (physical_size - len(source)))
        out += b"\x00" * (len(source) - len(out))

    # Validate every logical group through the rebuilt table.  Untouched
    # groups must be identical; translated groups were verified above.
    check_groups = split_groups(bytes(out))
    if len(check_groups) != len(groups):
        raise ValueError("rebuilt CMP2 group count changed")
    for i, old in enumerate(groups):
        if i == 0:
            continue
        if i not in by_group and check_groups[i] != old:
            raise ValueError("untouched CMP2 group %d changed" % i)
        if i in by_group and check_groups[i] != rebuilt_groups[i]:
            raise ValueError("rebuilt CMP2 group %d does not round-trip" % i)

    absolute_map = {}
    for i, offsets in local_maps.items():
        old_start = (entries[i][1] - entries[i][0]) * SECTOR
        new_start = new_starts[i]
        for old_local, new_local in offsets.items():
            absolute_map[old_start + old_local] = new_start + new_local

    return (bytes(out), absolute_map, placeholders, relocated_refs,
            text_growth, physical_size)


def main(argv):
    args = list(argv[1:])
    out_path = OUT
    fixed_size = True
    if "--expand" in args:
        args.remove("--expand")
        fixed_size = False
    if "--out" in args:
        p = args.index("--out")
        try:
            out_path = args[p + 1]
        except IndexError:
            raise SystemExit("--out needs a path")
        del args[p:p + 2]
    if not args:
        print(__doc__)
        return 1

    translations = load_translations(args)
    source = open(SCENARIO, "rb").read()
    result, offsets, placeholders, refs, growth, physical = rebuild(
        source, translations, fixed_size=fixed_size)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    open(out_path, "wb").write(result)

    moved = sum(old != new for old, new in offsets.items())
    extent = "fixed ISO extent" if fixed_size else "expandable physical extent"
    print("wrote %s (%d bytes, %s)" % (out_path, len(result), extent))
    print("  %d translated records, %d moved to new offsets" % (len(offsets), moved))
    print("  text/program growth: %+d bytes; relocated branch targets: %d"
          % (growth, refs))
    print("  %d placeholder groups retained; physical payload %d bytes"
          % (placeholders, physical))

    if MENU_OVERSIZE:
        print("  WARNING: %d choice-menu option(s) exceed the runtime's "
              "%d-unit limit and will render a stale glyph at the right edge "
              "of every row of their menu (fix by shortening the label):"
              % (len(MENU_OVERSIZE), MENU_CHOICE_MAX_UNITS))
        for off, stored, wrapped in sorted(MENU_OVERSIZE):
            print("    %06X  %2d units  %r" % (off, stored, wrapped))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
