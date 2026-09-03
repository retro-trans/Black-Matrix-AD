"""
Merge an English TSV against the Japanese pulled live from SCENARIO.DAT.

    python tools/build_script.py script/en/intro.en.tsv 0x6C00 0xE100

Writes a bilingual TSV next to the English one and reports:
  * lines present in the ROM range but with no English yet
  * English rows whose offset no longer matches a text opcode (stale offsets)
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmtext
import terms

SCENARIO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "extracted", "SCENARIO.DAT")
SPEAKERS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "script", "speakers.tsv")


def unescape(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append("\n" if s[i + 1] == "n" else s[i + 1])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def escape(s):
    return s.replace("\\", "\\\\").replace("\n", "\\n")


def load_en(path, resolve_terms=True):
    rows = {}
    for line in io.open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        offset, english = line.split("\t", 1)
        english = unescape(english)
        rows[int(offset, 16)] = terms.expand_text(english) if resolve_terms else english
    return rows


def load_speakers(path=SPEAKERS):
    """Load evidence-backed speaker ranges used to annotate bilingual TSVs."""
    if not os.path.exists(path):
        return []
    rows = []
    with io.open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or line.startswith("start_offset\t"):
                continue
            fields = line.split("\t")
            if len(fields) < 4:
                raise ValueError("bad speaker row: %s" % line)
            known_name = fields[4].strip() if len(fields) > 4 else ""
            rows.append((int(fields[0], 16), int(fields[1], 16),
                         fields[2], fields[3], known_name))
    return rows


def speaker_for(off, kind, ranges):
    matches = [(key, known_name)
               for lo, hi, applies_to, key, known_name in ranges
               if lo <= off <= hi and (applies_to == "*" or applies_to == kind)]
    if len(matches) > 1:
        raise ValueError("multiple speaker profiles match %08X: %s" %
                         (off, ", ".join(key for key, name in matches)))
    if not matches:
        return ""
    key, known_name = matches[0]
    if not known_name:
        raise ValueError("speaker profile %s at %08X has no confirmed name" %
                         (key, off))
    return known_name


def main(argv):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    en_path = argv[1]
    lo = int(argv[2], 0) if len(argv) > 2 else 0
    hi = int(argv[3], 0) if len(argv) > 3 else 1 << 62

    data = open(SCENARIO, "rb").read()
    jp = {off: (kind, voice, text) for off, kind, voice, text in bmtext.strings(data)}
    en = load_en(en_path)
    speakers = load_speakers()

    out_path = os.path.normpath(en_path).replace(os.sep + "en" + os.sep, os.sep)
    out_path = out_path.replace(".en.tsv", ".bilingual.tsv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("offset\tkind\tvoice\tspeaker\tjapanese\tenglish\n")
        for off in sorted(o for o in jp if lo <= o <= hi):
            kind, voice, text = jp[off]
            f.write("%08X\t%s\t%s\t%s\t%s\t%s\n" % (
                off, kind, "%04X" % voice if voice is not None else "",
                speaker_for(off, kind, speakers), escape(text),
                escape(en.get(off, ""))))

    missing = [o for o in sorted(jp) if lo <= o <= hi and o not in en]
    stale = [o for o in sorted(en) if o not in jp]
    print("wrote %s" % out_path)
    print("range %06X-%06X: %d lines, %d translated, %d missing"
          % (lo, hi, sum(1 for o in jp if lo <= o <= hi),
             sum(1 for o in jp if lo <= o <= hi and o in en), len(missing)))
    for off in missing:
        print("  MISSING %08X %s | %s" % (off, jp[off][0], jp[off][2].replace("\n", " / ")))
    for off in stale:
        print("  STALE   %08X (no text opcode at this offset)" % off)
    return 1 if (missing or stale) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
