"""Check term controls and known speakers in translated script files.

The check is source-aware: every longest-matching glossary term in a Japanese
line must have a matching ``$$Japanese term ID$$`` in its English source.
Every translated TALK/NARR line must also resolve to a confirmed speaker.

    python tools/glossary.py check script/glossary.tsv script/en/*.en.tsv
"""

import io
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bmtext
import build_script
import terms

# The script word 0xB001 is an engine macro that renders the selected master's
# name. bmtext exposes it as a readable placeholder token.
# A route-specific name control is therefore source-backed even though the
# literal Japanese name is not stored in SCENARIO.DAT at that offset.
DYNAMIC_MASTER_NAME = bmtext.DYNAMIC_MASTER_NAME_TOKEN


def check(glossary_path, script_paths):
    expanded_paths = []
    for path in script_paths:
        matches = glob.glob(path)
        expanded_paths.extend(matches if matches else [path])
    script_paths = sorted(set(expanded_paths))
    glossary = terms.load_glossary(glossary_path)
    with open(build_script.SCENARIO, "rb") as f:
        data = f.read()
    source = {off: (kind, text)
              for off, kind, voice, text in bmtext.strings(data)}
    speaker_ranges = build_script.load_speakers()
    failures = []
    term_occurrences = 0
    speaker_lines = 0

    for script_path in script_paths:
        translations = build_script.load_en(script_path, resolve_terms=False)
        for off, raw_english in sorted(translations.items()):
            source_row = source.get(off)
            if source_row is None:
                # build_script/scriptpack already diagnose stale offsets.
                continue
            kind, japanese = source_row

            try:
                terms.expand_text(raw_english, glossary)
            except ValueError as exc:
                failures.append((script_path, off, str(exc),
                                 japanese, raw_english))

            required = terms.source_term_counts(japanese, glossary)
            supplied = terms.token_counts(raw_english)
            if DYNAMIC_MASTER_NAME in japanese:
                for term_id, count in supplied.items():
                    if (term_id in glossary and
                            glossary[term_id].get("category", "").strip() == "name"):
                        required[term_id] = max(required[term_id], count)
            term_occurrences += sum(required.values())
            for term_id in sorted(set(required) | set(supplied)):
                need = required[term_id]
                have = supplied[term_id]
                if need and not have:
                    failures.append((
                        script_path, off,
                        "term %s needs a control; use $$%s$$" %
                        (term_id, term_id),
                        japanese, raw_english))
                elif have and not need:
                    failures.append((
                        script_path, off,
                        "control $$%s$$ has no matching Japanese source term" %
                        term_id, japanese, raw_english))

            if kind in ("TALK", "NARR"):
                speaker_lines += 1
                try:
                    speaker = build_script.speaker_for(off, kind, speaker_ranges)
                except ValueError as exc:
                    speaker = ""
                    failures.append((script_path, off, str(exc),
                                     japanese, raw_english))
                if not speaker:
                    failures.append((
                        script_path, off,
                        "no confirmed speaker for translated %s line" % kind,
                        japanese, raw_english))

    if failures:
        for path, off, message, japanese, english in failures:
            print("%s:%08X: %s" % (path, off, message))
            print("    JP: %s" % japanese.replace("\n", " / "))
            print("    EN: %s" % english.replace("\n", " / "))
        print("translation metadata check failed: %d issue(s), "
              "%d term occurrence(s), %d voiced/narrated line(s) checked"
              % (len(failures), term_occurrences, speaker_lines))
        return 1

    print("translation metadata check passed: %d term occurrence(s), "
          "%d canonical term(s), %d voiced/narrated line(s) with known speakers"
          % (term_occurrences, len(glossary), speaker_lines))
    return 0


def main(argv):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    if len(argv) < 4 or argv[1] != "check":
        print("usage: python tools/glossary.py check GLOSSARY SCRIPT [SCRIPT ...]")
        return 2
    return check(argv[2], argv[3:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
