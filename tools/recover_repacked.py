"""Recover translated TSV text from a previously repacked SCENARIO image.

This is a safety tool for recovering source rows after an accidental TSV
overwrite.  PSI text records retain their order when repacked, so records in
an original and rebuilt CMP2 group can be aligned by sequence.  The tool also
inverts the VWF Latin encoding and restores required glossary controls.

    python tools/recover_repacked.py BUILD_SCENARIO GROUP [ROUTE_NAME_TERM]
"""

import io
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bmtext
import latin
import patchline
import scriptpack
import terms


def decode_vwf_record(program, offset, kind):
    length = struct.unpack_from("<H", program, offset + 2)[0]
    inverse = {patchline.to_sjis(ch): ch for ch in latin.EXTRA}
    # Prefer ordinary ASCII for slots shared by straight and curly closing
    # quotes; this also makes glossary values containing apostrophes recover
    # exactly (for example, "shepherd's purse").
    inverse.update({patchline.to_sjis(ch): ch for ch in latin.PUNCT})
    inverse.update({patchline.to_sjis(ch): ch
                    for ch in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"})
    inverse[patchline.SPACE] = " "
    inverse[patchline.LINE_BREAK] = "\n"
    inverse.update({code: ch for ch, code in patchline.STOCK_SYMBOLS.items()})
    words = struct.unpack_from("<%dH" % length, program, offset + 4)
    cols = patchline.NARR_COLS if kind == "NARR" else patchline.COLS
    decoded = []
    column = 0
    for word in words:
        if word == patchline.LINE_BREAK:
            decoded.append("\n")
            column = 0
            continue
        # patchline.wrap deliberately omits both the break and separating
        # space after an exactly full row because the engine wraps at `cols`
        # nodes automatically. Restore that source-space during recovery.
        if column == cols:
            decoded.append(" ")
            column = 0
        decoded.append(inverse.get(word, bmtext.decode_char(word)))
        column += 1
    return "".join(decoded)


def restore_control(text, term_id, preferred, count):
    pattern = re.compile(re.escape(preferred), re.IGNORECASE)
    for _ in range(count):
        text, changed = pattern.subn("$$%s$$" % term_id, text, count=1)
        if not changed:
            raise ValueError("cannot restore $$%s$$ from %r" %
                             (term_id, text))
    return text


def recover(build_path, group_index, route_term=None):
    source_path = os.path.join(ROOT, "extracted", "SCENARIO.DAT")
    source = open(source_path, "rb").read()
    built = open(build_path, "rb").read()
    source_groups = scriptpack.split_groups(source)
    built_groups = scriptpack.split_groups(built)
    original = list(bmtext.strings(source_groups[group_index]))
    rebuilt = list(bmtext.strings(built_groups[group_index]))
    if len(original) != len(rebuilt):
        raise ValueError("group %d record count changed: %d -> %d" %
                         (group_index, len(original), len(rebuilt)))

    entries = scriptpack.cmp2_entries(source)
    count, end = entries[group_index]
    absolute_start = (end - count) * scriptpack.SECTOR
    glossary = terms.load_glossary()
    rows = []
    for source_row, built_row in zip(original, rebuilt):
        old_off, old_kind, voice, japanese = source_row
        new_off, new_kind, voice, ignored = built_row
        if old_kind != new_kind:
            raise ValueError("group %d record kind mismatch at %X" %
                             (group_index, old_off))
        english = decode_vwf_record(built_groups[group_index], new_off, old_kind)
        english = re.sub(r"\s*\n\s*", " ", english).rstrip()
        required = terms.source_term_counts(japanese, glossary)
        for term_id in sorted(required,
                              key=lambda key: len(glossary[key]["preferred_english"]),
                              reverse=True):
            english = restore_control(
                english, term_id, glossary[term_id]["preferred_english"],
                required[term_id])
        if bmtext.DYNAMIC_MASTER_NAME_TOKEN in japanese:
            if not route_term:
                raise ValueError("group %d needs a route-name term" % group_index)
            english = restore_control(
                english, route_term, glossary[route_term]["preferred_english"], 1)
        rows.append("%08X\t%s" % (absolute_start + old_off, english))
    return rows


def main(argv):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="strict")
    if len(argv) not in (3, 4):
        print(__doc__)
        return 2
    build_path = argv[1]
    group_index = int(argv[2], 0)
    route_term = argv[3] if len(argv) == 4 else None
    for row in recover(build_path, group_index, route_term):
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
