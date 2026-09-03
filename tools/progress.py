"""Report authoritative full-game script translation coverage by PSI group."""

import glob
import io
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bmtext
import build_script
import scriptpack


def group_for_offset(offset, entries):
    for index, (count, end) in enumerate(entries):
        start = (end - count) * scriptpack.SECTOR
        finish = end * scriptpack.SECTOR
        if start <= offset < finish:
            return index
    return None


def main(argv):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    with open(build_script.SCENARIO, "rb") as f:
        data = f.read()
    entries = scriptpack.cmp2_entries(data)
    rows = list(bmtext.strings(data))
    paths = sorted(glob.glob(os.path.join(ROOT, "script", "en", "*.en.tsv")))
    translations = scriptpack.load_translations(paths)

    source_offsets = {off for off, kind, voice, text in rows}
    stale = sorted(set(translations) - source_offsets)
    if stale:
        raise ValueError("stale translation offsets: %s" %
                         ", ".join("%08X" % off for off in stale))

    total = Counter(kind for off, kind, voice, text in rows)
    done = Counter(kind for off, kind, voice, text in rows if off in translations)
    print("translation files: %d" % len(paths))
    print("all text: %d / %d translated (%.2f%%)" % (
        sum(done.values()), sum(total.values()),
        100.0 * sum(done.values()) / sum(total.values())))
    for kind in ("TALK", "NARR", "PICK"):
        print("  %-4s %5d / %5d" % (kind, done[kind], total[kind]))

    by_group = {}
    for off, kind, voice, text in rows:
        group = group_for_offset(off, entries)
        counts = by_group.setdefault(group, [Counter(), Counter(), off, off])
        counts[0][kind] += 1
        if off in translations:
            counts[1][kind] += 1
        counts[2] = min(counts[2], off)
        counts[3] = max(counts[3], off)

    print("\ngroups containing translated text:")
    for group in sorted(by_group):
        all_counts, done_counts, first, last = by_group[group]
        if not sum(done_counts.values()):
            continue
        print("  %3d %08X-%08X  %3d/%3d  T=%d N=%d P=%d" % (
            group, first, last, sum(done_counts.values()),
            sum(all_counts.values()), done_counts["TALK"],
            done_counts["NARR"], done_counts["PICK"]))

    print("\nnext untranslated groups:")
    shown = 0
    for group in sorted(by_group):
        all_counts, done_counts, first, last = by_group[group]
        if sum(done_counts.values()) == sum(all_counts.values()):
            continue
        print("  %3d %08X-%08X  remaining %d (T=%d N=%d P=%d)" % (
            group, first, last,
            sum(all_counts.values()) - sum(done_counts.values()),
            all_counts["TALK"] - done_counts["TALK"],
            all_counts["NARR"] - done_counts["NARR"],
            all_counts["PICK"] - done_counts["PICK"]))
        shown += 1
        if shown == 12:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
