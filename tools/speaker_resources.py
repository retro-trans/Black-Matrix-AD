"""Audit nearby PSI resource selectors against confirmed script speakers.

The common character/resource command is encoded as::

    000A 0011 0001 <u32 resource_id> ...

This utility reports the closest such command before each TALK/NARR record.
It is evidence assistance only: a resource can be reused by generic map NPCs,
so the output must still be checked against scene structure and dialogue.

    python tools/speaker_resources.py [START [END]]
"""

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bmtext
import build_script


SIGNATURE = b"\x0a\x00\x11\x00\x01\x00"


def selector_before(data, offset, window=128):
    pos = data.rfind(SIGNATURE, max(0, offset - window), offset)
    if pos < 0:
        return None, None
    resource = struct.unpack_from("<I", data, pos + len(SIGNATURE))[0]
    # Two observed encodings differ by an inserted zero word. Normalize the
    # shifted form so 00 00 52 00 reports the established resource 0x52.
    if resource > 0xFFFF and not resource & 0xFFFF:
        resource >>= 16
    return resource, offset - pos


def main(argv):
    lo = int(argv[1], 0) if len(argv) > 1 else 0
    hi = int(argv[2], 0) if len(argv) > 2 else 1 << 62
    with open(build_script.SCENARIO, "rb") as f:
        data = f.read()
    ranges = build_script.load_speakers()

    for off, kind, voice, japanese in bmtext.strings(data):
        if kind not in ("TALK", "NARR") or not lo <= off <= hi:
            continue
        resource, distance = selector_before(data, off)
        try:
            speaker = build_script.speaker_for(off, kind, ranges)
        except ValueError as exc:
            speaker = "ERROR: %s" % exc
        print("%08X %-4s resource=%s distance=%s speaker=%s | %s" % (
            off, kind,
            "----" if resource is None else "%04X" % resource,
            "---" if distance is None else "%3d" % distance,
            speaker or "UNRESOLVED", japanese.replace("\n", " / ")))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv))
