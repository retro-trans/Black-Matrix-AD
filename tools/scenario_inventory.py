"""Read-only SCENARIO.DAT inventory reporter.

Prints Markdown to stdout.  It intentionally changes no scenario, translation,
glossary, or speaker data.  Use, for example:

    python tools/scenario_inventory.py > docs/scenario-inventory.md
"""

from __future__ import print_function

import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bmtext

SECTOR = 2048
SCENARIO = os.path.join(ROOT, "extracted", "SCENARIO.DAT")
PSI_MAGIC = b"PSI22.00"


# The exact groups in the opening's six alternate master routes establish this
# relationship.  The PSI opcode name has not been reverse engineered, so these
# are deliberately named resource clusters rather than asserted portrait IDs.
MASTER_RESOURCE = {
    0x23: "Domina", 0x24: "Domina", 0x25: "Domina", 0x26: "Domina",
    0x76: "Domina",
    0x27: "Prica", 0x28: "Prica", 0x29: "Prica", 0x2A: "Prica",
    0x77: "Prica",
    0x2B: "Courreges", 0x2C: "Courreges", 0x2D: "Courreges", 0x2E: "Courreges",
    0x78: "Courreges",
    0x2F: "Michette", 0x30: "Michette", 0x31: "Michette", 0x32: "Michette",
    0x79: "Michette",
    0x33: "Prague", 0x34: "Prague", 0x35: "Prague", 0x36: "Prague",
    0x7A: "Prague",
    0x37: "Zero", 0x38: "Zero", 0x39: "Zero", 0x3A: "Zero",
    0x7B: "Zero",
}

# These programs contain no portrait-resource cue, so the evidence is kept
# separately from the resource map.  The strong first-person markers below,
# plus the unchanged six-route storage order, identify the diary author.
DIARY_AUTHORS = {
    28: ("Domina", "私 / あたし達; the remaining first slot in the six-master order; "
         "warm, anxious prose about Abel recovering."),
    29: ("Prica", "childlike all-hiragana writing and repeated おにいちゃん."),
    30: ("Courreges", "ボク throughout; self-described girlhood and fish-cooking reference."),
    31: ("Michette", "writes ミシェット by name and repeatedly addresses カインおにいちゃん."),
    32: ("Prague", "アタシ / アンタ throughout; her mature, self-reproachful register."),
    33: ("Zero", "俺 / お前 throughout; masculine register and the diary's intimate care details."),
}


def cmp2_entries(data):
    if data[:4] != b"CMP2":
        raise ValueError("SCENARIO.DAT is not CMP2")
    count = struct.unpack_from("<I", data, 8)[0]
    return [struct.unpack_from("<II", data, 12 + i * 8) for i in range(count)]


def clean(text):
    """Make decoded text compact and safe in a Markdown table cell."""
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def immediate_after_typed_0a(program, used_end, text_ranges):
    """Return small immediate values in 0A/11/01 instruction forms.

    PSI aligns typed u32 operands.  In the known master-route programs this
    exact form changes among the six face-resource families.  We ignore bytes
    inside text records so Shift-JIS data cannot create spurious instructions.
    """
    def in_text(pos):
        return any(lo <= pos < hi for lo, hi in text_ranges)

    values = []
    for pos in range(16, used_end - 12, 2):
        if in_text(pos):
            continue
        if struct.unpack_from("<HHH", program, pos) != (0x000A, 0x0011, 0x0001):
            continue
        payload = (pos + 6 + 3) & ~3
        if payload + 4 > used_end or in_text(payload):
            continue
        value = struct.unpack_from("<I", program, payload)[0]
        # Face/resource values observed in the confirmed six-master routes are
        # compact indexes.  Keep this conservative to avoid generic operands.
        if value in MASTER_RESOURCE:
            values.append(value)
    return values


def evidence_for(index, records, cue_names):
    """Return a deliberately conservative group-level identity note."""
    explicit = {
        9: "CONFIRMED: opening alternate route — Domina (existing exact line evidence).",
        10: "CONFIRMED: opening alternate route — Prica (existing exact line evidence).",
        11: "CONFIRMED: opening alternate route — Courreges (existing exact line evidence).",
        12: "CONFIRMED: opening alternate route — Michette (existing exact line evidence).",
        13: "CONFIRMED: opening alternate route — Prague (existing exact line evidence).",
        14: "CONFIRMED: opening alternate route — Zero (existing exact line evidence).",
        15: "CONFIRMED: recovery account — Domina; first six-master post-intro program.",
        16: "CONFIRMED: recovery account — Prica; existing exact line evidence.",
        17: "CONFIRMED: recovery account — Courreges; existing exact line evidence.",
        18: "CONFIRMED: recovery account — Michette; existing exact line evidence.",
        19: "CONFIRMED: recovery account — Prague; route order, 33/35/36 cluster, アタシ/アンタ register.",
        20: "CONFIRMED: recovery account — Zero; route order, 37/39/3A cluster, オレ/オマエ register.",
        22: "CONFIRMED homogeneous bath encounter — Domina; 23/26 cluster. NARR reaction is Abel.",
        23: "CONFIRMED homogeneous bath encounter — Prica; 27/28 cluster and おにいちゃん. NARR reaction is Abel.",
        24: "CONFIRMED homogeneous bath encounter — Courreges; 2B/2C/2E cluster. NARR reaction is Abel.",
        25: "CONFIRMED homogeneous bath encounter — Michette; 2F/30/32 cluster. NARR reaction is Abel.",
        26: "CONFIRMED homogeneous bath encounter — Prague; 33/35/36 cluster and アタシ register. NARR reaction is Abel.",
        27: "CONFIRMED homogeneous bath encounter — Zero; 37/3A cluster. NARR reaction is Abel.",
        28: "CONFIRMED diary author — Domina; pronouns/register plus first route slot.",
        29: "CONFIRMED diary author — Prica; child orthography and おにいちゃん.",
        30: "CONFIRMED diary author — Courreges; ボク register.",
        31: "CONFIRMED diary author — Michette; self-name and カインおにいちゃん.",
        32: "CONFIRMED diary author — Prague; アタシ / アンタ register.",
        33: "CONFIRMED diary author — Zero; 俺 / お前 register.",
    }
    if index in explicit:
        return explicit[index]

    # Recurring six-way optional scenes are good scene leads, but a group can
    # still contain an unportrayed second speaker.  They are not translation
    # authorization without per-line review.
    six_way = ((46, 51), (52, 57), (59, 64), (65, 70), (82, 87),
               (88, 93), (98, 103), (107, 112), (113, 118))
    if any(lo <= index <= hi for lo, hi in six_way) and len(cue_names) == 1:
        return ("LIKELY route-specific %s scene; recurring %s resource cluster. "
                "Review each TALK boundary before translating." %
                ("master", next(iter(cue_names))))
    if cue_names:
        return ("PARTIAL evidence: %s resource cue(s) occur; group may include "
                "additional speakers — unknown until line-level scene review." %
                ", ".join(sorted(cue_names)))
    if records:
        return "UNKNOWN: text-bearing PSI; no established identity cue."
    return "No text record."


def main():
    data = open(SCENARIO, "rb").read()
    entries = cmp2_entries(data)
    kinds = collections.Counter()
    text_groups = 0
    total = collections.Counter()
    rows = []

    for index, (sectors, end_sector) in enumerate(entries):
        start = (end_sector - sectors) * SECTOR
        end = end_sector * SECTOR
        group = data[start:end]
        if index == 0:
            group_kind = "CMP2 header"
            used = "—"
            records = []
            cues = []
        elif group[:8] == PSI_MAGIC:
            group_kind = "PSI2"
            used_end = struct.unpack_from("<I", group, 12)[0] + 16
            used = "%X" % used_end
            records = list(bmtext.strings(group[:used_end]))
            text_ranges = [(off, off + 4 + 2 * struct.unpack_from("<H", group, off + 2)[0])
                           for off, _kind, _voice, _text in records]
            cues = immediate_after_typed_0a(group, used_end, text_ranges)
        elif group == b"\x11" * len(group):
            group_kind = "0x11 placeholder"
            used = "—"
            records = []
            cues = []
        else:
            group_kind = "non-PSI data"
            used = "—"
            records = []
            cues = []

        kinds[group_kind] += 1
        counts = collections.Counter(record[1] for record in records)
        total.update(counts)
        if records:
            text_groups += 1
        cue_names = {MASTER_RESOURCE[value] for value in cues}
        first = clean(records[0][3]) if records else "—"
        last = clean(records[-1][3]) if records else "—"
        cue_text = "/".join("%02X" % value for value in sorted(set(cues))) or "—"
        rows.append((index, start, end - 1, sectors, group_kind, used,
                     counts, first, last, cue_text,
                     evidence_for(index, records, cue_names)))

    print("# SCENARIO.DAT dialogue inventory")
    print()
    print("Generated from `extracted/SCENARIO.DAT` (%d bytes) by the read-only "
          "`tools/scenario_inventory.py` on the workspace snapshot. Byte ranges "
          "are CMP2 logical ranges: duplicated placeholder ranges, if any, remain "
          "logical entries rather than being silently collapsed." % len(data))
    print()
    print("## Format and scope")
    print()
    print("- CMP2 declares **%d logical groups**: %s." %
          (len(entries), ", ".join("%d %s" % (count, name)
                                   for name, count in sorted(kinds.items()))))
    print("- **%d PSI2 groups contain text**, for **%d TALK**, **%d NARR**, and "
          "**%d PICK** records. Empty PSI2 programs and non-PSI groups remain in "
          "the table to make every index auditable." %
          (text_groups, total["TALK"], total["NARR"], total["PICK"]))
    print("- `used` is the PSI2 end pointer plus its 16-byte header, in local bytes; "
          "the allocated range is sector-padded.")
    print("- `cue` lists conservative small immediates found in the aligned PSI form "
          "`000A 0011 0001 <aligned u32>`, excluding text payload. It is evidence "
          "only, not a claimed opcode name.")
    print()
    print("## Existing-tool audit")
    print()
    print("- `tools/bmtext.py` correctly supplies the CMP2/PSI2 structure and extracts "
          "`0014` NARR, `0015` TALK, and `001D` PICK records. Its preceding `001A` "
          "value is mostly zero and cannot identify a speaker.")
    print("- `tools/build_script.py` and `tools/glossary.py` already enforce the project "
          "rule: a translated TALK/NARR line must resolve to a confirmed range in "
          "`script/speakers.tsv`. This inventory does not modify that file or loosen "
          "the gate.")
    print("- `tools/scriptpack.py` rebuilds text records and labels; it does not currently "
          "decode scene, portrait, or speaker metadata. The reporter is read-only and "
          "adds only audit evidence, not a new script format assumption.")
    print()
    print("## Identity evidence and translation gate")
    print()
    print("The pre-existing exact speaker evidence for the six opening routes establishes "
          "the recurring resource families below. In each known route, the family "
          "appears with that master’s distinctive Japanese register. This makes the "
          "identity correlation strong; it does **not** prove that `000A` itself is a "
          "portrait command, nor does it identify an unportrayed second speaker in a "
          "mixed group.")
    print()
    print("No literal character-name ID field was found near these records. The strongest "
          "candidate is therefore a **portrait/face-resource selector**, not a name "
          "selector: the same aligned `000A/0011/0001` form changes to a member of a "
          "single six-master family in every known alternate route, and its immediate "
          "value switches with the on-screen expression. A runtime trace or portrait "
          "capture is still required before assigning a new non-master character from "
          "this opcode alone.")
    print()
    print("| speaker | correlated resource family | independent route/register check |")
    print("|---|---|---|")
    print("| Domina | 23–26, 76 | 私 / アナタ; opening route |")
    print("| Prica | 27–2A, 77 | あたし / おにいちゃん; opening route |")
    print("| Courreges | 2B–2E, 78 | ボク / キミ; opening route |")
    print("| Michette | 2F–32, 79 | playful 私 / キミ; Kain and stuffed-friend language |")
    print("| Prague | 33–36, 7A | アタシ / アンタ; owner/slave language |")
    print("| Zero | 37–3A, 7B | オレ / オマエ; rough male register |")
    print()
    print("### Diary authors: groups 28–33")
    print()
    print("These six programs contain only NARR records and no reliable portrait cue. "
          "They are nevertheless now **confirmed author-attributable**: their exact "
          "first-person markers identify five authors directly and leave Domina as the "
          "only matching first route slot. The order is the same six-master order used "
          "by the confirmed opening (9–14), recovery accounts (15–20), and bath scenes "
          "(22–27): Domina → Prica → Courreges → Michette → Prague → Zero.")
    print()
    print("The current PSI parser finds no PICK in 28–33 and no decoded cross-CMP group "
          "branch; their selection is therefore an external route/event-dispatch concern, "
          "not a local diary-script branch. The repeated archive order is corroboration, "
          "not the sole identity proof.")
    print()
    print("| group / range | author | confidence | direct in-script evidence | independent corroboration |")
    print("|---|---|---|---|---|")
    diary_ranges = {
        28: "28 / `015800–0167FF`", 29: "29 / `016800–016FFF`",
        30: "30 / `017000–017FFF`", 31: "31 / `018000–018FFF`",
        32: "32 / `019000–0197FF`", 33: "33 / `019800–01A7FF`",
    }
    for index in range(28, 34):
        author, evidence = DIARY_AUTHORS[index]
        if index == 31:
            external = ("[Japanese player record](https://susukinohara.hatenablog.com/entry/2024/09/25/233037) "
                        "specifically recalls Michette asking Kain to marry her.")
        elif index == 33:
            external = ("[GameFAQs AD guide](https://gamefaqs.gamespot.com/dreamcast/576042-black-matrix-ad/faqs/23743) "
                        "identifies the diary as a Zero-master item; the Japanese player record separately "
                        "recalls Zero's diary care scene.")
        else:
            external = ("[Japanese player record](https://susukinohara.hatenablog.com/entry/2024/09/25/233037) "
                        "confirms six distinct master diaries and their Valentine context.")
        print("| %s | %s | confirmed | %s | %s |" %
              (diary_ranges[index], author, evidence, external))
    print()
    print("### Next safe batches after groups 16–17")
    print()
    print("1. **18** (`010000–010FFF`): Michette recovery account. Existing exact speaker "
          "evidence covers its TALK records; the two NARR reaction beats are Abel.")
    print("2. **19** (`011000–0117FF`): Prague recovery account. Homogeneous TALK block; "
          "the 33/35/36 family and アタシ/アンタ language independently agree.")
    print("3. **20** (`011800–011FFF`): Zero recovery account. Homogeneous TALK block; the "
          "37/3A family and オレ/オマエ language independently agree.")
    print("4. After those, **22–27** (`012800–0157FF`) are six homogeneous bath-encounter "
          "programs in the same Domina → Prica → Courreges → Michette → Prague → Zero "
          "order. Their sparse NARR `……` reactions are Abel in context. These are safe "
          "as six separate, evidence-backed batches.")
    print()
    print("Groups **28–33 are now safe as six author-confirmed diary batches**. The lack "
          "of a portrait cue is no longer a blocker because each author's textual voice "
          "is direct and independently cross-checked. For future portraitless NARR, do "
          "not apply this shortcut: require an equally unique self-reference/register, "
          "or capture the diary/item screen with its owner visible.")
    print()
    print("## Complete logical-group table")
    print()
    print("| PSI group | global byte range | sectors | kind / used | TALK | NARR | PICK | first Japanese text | last Japanese text | cue | likely scene / speaker status |")
    print("|---:|---|---:|---|---:|---:|---:|---|---|---|---|")
    for (index, start, finish, sectors, group_kind, used, counts, first, last,
         cue_text, note) in rows:
        kind_used = group_kind if used == "—" else "%s / %s" % (group_kind, used)
        print("| %03d | `%06X–%06X` | %d | %s | %d | %d | %d | %s | %s | %s | %s |" %
              (index, start, finish, sectors, kind_used, counts["TALK"],
               counts["NARR"], counts["PICK"], first, last, cue_text, note))


if __name__ == "__main__":
    main()
