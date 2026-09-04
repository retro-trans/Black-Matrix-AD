"""Canonical glossary term codes used by translated script sources.

English TSV files may contain ``$$Japanese term ID$$``. The marker is never
written to the game: it is resolved to `preferred_english` from
script/glossary.tsv before wrapping and encoding. Changing one glossary value
therefore changes every marked occurrence. Space-constrained UI may use
``$$Japanese term ID|short label$$``; the term ID is still validated, while
the explicit display alias is written to the game.
"""

import csv
import io
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GLOSSARY = os.path.join(ROOT, "script", "glossary.tsv")
TOKEN_RE = re.compile(r"\$\$([^$|\r\n]+)(?:\|([^$\r\n]+))?\$\$")


def load_glossary(path=GLOSSARY):
    entries = {}
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        lines = (line for line in f if not line.startswith("#"))
        for row in csv.DictReader(lines, delimiter="\t"):
            term_id = row["japanese"].strip()
            preferred = row["preferred_english"].strip()
            if not term_id or not preferred:
                raise ValueError("glossary rows need japanese and preferred_english")
            if term_id in entries:
                raise ValueError("duplicate glossary term ID: %s" % term_id)
            entries[term_id] = row
    return entries


def _capitalize_at_sentence_start(text, pos, replacement):
    prefix = text[:pos].rstrip()
    if (prefix and prefix[-1] not in ".!?") or not replacement:
        return replacement
    return replacement[0].upper() + replacement[1:]


def expand_text(text, entries=None):
    """Resolve all glossary controls, failing on malformed or unknown IDs."""
    entries = entries or load_glossary()

    def replace(match):
        term_id, display_alias = match.group(1), match.group(2)
        if term_id not in entries:
            raise ValueError("unknown glossary term ID: $$%s$$" % term_id)
        value = (display_alias or entries[term_id]["preferred_english"]).strip()
        if not value:
            raise ValueError("empty glossary display value: $$%s$$" % term_id)
        return _capitalize_at_sentence_start(text, match.start(), value)

    expanded = TOKEN_RE.sub(replace, text)
    if "$$" in expanded:
        raise ValueError("malformed glossary control in: %s" % text)
    return expanded


def source_term_counts(japanese, entries=None):
    """Count longest non-overlapping glossary IDs in a Japanese source line."""
    entries = entries or load_glossary()
    # SCENARIO.DAT uses the unmapped gaiji word 0x81AF for 贄. The decoder
    # renders it as "?", but the repeated compound 生贄 is unambiguous in the
    # Babel sacrifice scenes. Restore it before matching glossary IDs.
    japanese = japanese.replace("生?", "生贄")
    ids = sorted(entries, key=len, reverse=True)

    def japanese_word_char(ch):
        code = ord(ch)
        return (0x3040 <= code <= 0x30FF or
                0x3400 <= code <= 0x4DBF or
                0x4E00 <= code <= 0x9FFF)

    def valid_at(term_id, pos):
        # この世 is a complete expression ("this world"), but it is also a
        # prefix of この世界.  In the latter spelling the canonical source
        # term is 世界, so leave the leading この unmarked and allow 世界 to
        # be found when the scanner advances.
        if term_id == "この世" and japanese.startswith("この世界", pos):
            return False

        # Hiragana proper-name variants such as かいん must not match inside
        # unrelated words such as 暖かいんだ. A preceding Japanese word
        # character proves this is a suffix/substring rather than the name.
        row = entries[term_id]
        if (row.get("category", "").strip() == "name" and
                all(0x3040 <= ord(ch) <= 0x309F for ch in term_id) and
                pos > 0 and japanese_word_char(japanese[pos - 1])):
            return False
        return True

    found = Counter()
    pos = 0
    while pos < len(japanese):
        match = next((term_id for term_id in ids
                      if japanese.startswith(term_id, pos) and
                      valid_at(term_id, pos)), None)
        if match is None:
            pos += 1
        else:
            found[match] += 1
            pos += len(match)
    return found


def token_counts(text):
    return Counter(match.group(1) for match in TOKEN_RE.finditer(text))
