"""PSI2 statement-stream walker: the real grammar, from the interpreter.

Everything here was read out of 1ST_READ.BIN, not guessed from data:

  * The interpreter keeps its stream pointer at 0x8C263AB4.  A group is
    loaded whole at 0x8C700000 and execution starts at 0x8C700010, i.e. at
    file offset 0x10, just past the 16-byte PSI22.00 header.
  * The main loop (0x8C08BF60) reads a u16 statement word and dispatches it
    through the pointer table at 0x8C09A26C (statement N -> entry N).  The
    words 8, 9, 10, 11 instead switch dispatch mode (0x8C08C04E): the next
    u16 is a sub-opcode in the table at 0x8C09A32C, 0x8C09A408, 0x8C09A4D0
    or 0x8C09A5E4 respectively.  0x8C09A32C is the mode-1 table plus 0xC0,
    so mode-2 sub-op N is statement 0x30+N.  After the sub-op the stream
    returns to plain statements.
  * Operands are consumed by three readers:
      0x8C08BC3C  u16, advance 2                                  -> "u16"
      0x8C08BC4A  align the pointer to 4, u32, advance 4          -> "u32"
      0x8C08BC96  expression: a sequence of typed pushes and
                  operators terminated by a 0x0000 word           -> "expr"
    Expression tags: 1 = aligned-u32 immediate, 2/3/4 = u16 index into a
    variable bank; any word >= 0x80 is a stack operator; 0 ends the
    expression.  Alignment is against the runtime address, and the load
    base 0x8C700000 is 4-aligned, so file offsets align identically.
  * Text statements 0x14/0x15 (0x8C08C464 / 0x8C08C50C) read a u16 count
    and then count u16 characters                                 -> "text"
  * Statement 0x1D (0x8C08C8E6) reads a text record and then one aligned
    u32: the branch target for that menu choice                   -> "text", "tgt"
  * Control flow that embeds stream offsets, all relative to base + 0x10:
      st 0x02 (0x8C08BF06)  aligned u32 target, then an expression;
                            jumps when the expression is 0        -> "tgt", "expr"
      st 0x03 (0x8C08BF2A)  aligned u32 target, unconditional     -> "tgt"
      st 0x1D               choice target, taken via 0x8C08CC40 /
                            0x8C08CE74 when the player picks it
    Nothing else stores a stream offset: st 0x10/0x11 change *group* by
    number (load into 0x8C700000, restart at +0x10) and the call stack at
    0x8C263AB8 holds runtime pointers only.
  * There are no labels.  The six-byte pattern FF 00 80 00 00 00 that an
    earlier repacker treated as a label marker is the tail of an ordinary
    expression: tag 2, index 0xFF, operator 0x80, end.

Signatures below come from mechanically exploring every handler for reader
calls, then correcting against the data: walk() must consume every real
group of SCENARIO.DAT from 0x10 to its used end, land every branch target
on a statement boundary, and find a text statement at every offset that
bmtext.strings() reports.  scriptpack.py relies on that validation before
trusting the reference list.

    python tools/psi2.py check            # walk and validate every group
    python tools/psi2.py dump 50          # statement listing of one group
"""

import io
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
ENTRY = 0x10          # execution starts at file offset 0x10
TARGET_BIAS = 0x10    # stored targets are file offsets minus 0x10

# Operand signatures.  e=expr, w=u16, t=text record, T=aligned-u32 branch
# target (needs relocation), U=aligned-u32 value (no relocation).
ST_SIGS = {
    0x00: "",  # null handler; appears as padding after a final return
    0x01: "wwe", 0x02: "Te", 0x03: "T", 0x06: "e", 0x07: "",
    0x0C: "", 0x0D: "e", 0x0E: "", 0x0F: "e",
    0x10: "e", 0x11: "e", 0x12: "",
    0x14: "t", 0x15: "t", 0x16: "e", 0x17: "", 0x18: "", 0x19: "",
    0x1A: "e", 0x1B: "", 0x1C: "eee", 0x1D: "tT", 0x1E: "",
    0x20: "t", 0x21: "ee", 0x22: "", 0x25: "e",
    0x27: "ee", 0x28: "e", 0x29: "eee", 0x2A: "", 0x2B: "ee",
    0x2C: "eee", 0x31: "", 0x32: "", 0x34: "e", 0x35: "",
    0x36: "ee", 0x37: "ee", 0x38: "",
    0x3B: "e", 0x3C: "e", 0x3D: "", 0x3E: "e", 0x3F: "",
    0x40: "eee", 0x41: "e", 0x42: "eee", 0x43: "e", 0x44: "eeee",
    0x45: "et", 0x46: "e", 0x47: "", 0x48: "", 0x49: "e", 0x4A: "",
    0x4B: "", 0x4C: "ee", 0x4D: "", 0x4E: "e",
    0x50: "e", 0x51: "ee", 0x53: "e", 0x54: "", 0x55: "", 0x56: "",
    0x57: "e", 0x58: "e", 0x59: "", 0x5A: "e", 0x5B: "", 0x5C: "",
    0x60: "", 0x61: "ee", 0x62: "", 0x63: "", 0x65: "",
}
T1_SIGS = {
    0x01: "", 0x02: "", 0x03: "", 0x04: "e", 0x05: "e", 0x06: "",
    0x07: "", 0x08: "eee", 0x09: "ee", 0x0A: "", 0x0B: "", 0x0C: "",
    0x0D: "ee", 0x0E: "eeeee", 0x0F: "eeeee", 0x10: "eee",
    0x11: "ee", 0x12: "eee", 0x13: "e", 0x14: "ee", 0x15: "e",
    0x16: "", 0x17: "", 0x18: "e", 0x19: "", 0x1A: "e", 0x1B: "",
    0x1C: "ee", 0x1D: "ee", 0x1E: "eee", 0x20: "e", 0x21: "ee",
    0x22: "ee", 0x23: "ee", 0x24: "", 0x25: "", 0x26: "", 0x27: "e",
    0x28: "", 0x29: "", 0x2A: "", 0x2B: "", 0x2C: "ee", 0x2D: "e",
    0x2E: "ee", 0x2F: "", 0x30: "", 0x31: "",
}
T2_SIGS = {
    0x01: "e", 0x02: "e", 0x03: "e", 0x04: "ee", 0x05: "ee",
    0x06: "e", 0x07: "ee", 0x08: "", 0x0A: "e", 0x0B: "e",
    0x0C: "eeee", 0x0D: "e", 0x0E: "ee", 0x0F: "e", 0x10: "e",
    0x11: "e", 0x12: "", 0x13: "", 0x14: "e", 0x15: "", 0x16: "",
    0x17: "", 0x18: "eee", 0x19: "eee", 0x1A: "ee", 0x1B: "",
    0x1C: "", 0x1D: "", 0x1E: "", 0x20: "", 0x21: "", 0x22: "",
    0x23: "", 0x24: "ee", 0x25: "e", 0x26: "e", 0x27: "eeee",
    0x28: "e", 0x29: "e", 0x2A: "eee", 0x2B: "ee", 0x2C: "ee",
    0x2D: "e", 0x2E: "e", 0x2F: "ee", 0x30: "e", 0x31: "",
    0x32: "", 0x34: "e", 0x35: "", 0x36: "ee", 0x37: "e",
    0x38: "ee", 0x39: "ee", 0x3A: "ee", 0x3E: "e", 0x3F: "ee",
    0x40: "", 0x41: "", 0x42: "", 0x43: "",
}
T3_SIGS = {
    0x01: "", 0x02: "ee", 0x03: "", 0x04: "", 0x05: "", 0x06: "",
    0x07: "", 0x08: "", 0x09: "e", 0x0A: "eeee", 0x0B: "eee",
    0x0C: "eee", 0x0D: "eee", 0x0E: "ee", 0x10: "e", 0x11: "e",
    0x12: "eee", 0x13: "eee", 0x14: "eee", 0x15: "ee", 0x16: "ee",
    0x17: "ee",
}
MODE_TABLES = {8: None, 9: T1_SIGS, 10: T2_SIGS, 11: T3_SIGS}


class WalkError(ValueError):
    def __init__(self, message, pos):
        super(WalkError, self).__init__("%s at offset 0x%X" % (message, pos))
        self.pos = pos


class Walk(object):
    """The decoded statement stream of one PSI2 program."""

    def __init__(self, boundaries, texts, targets, end):
        self.boundaries = boundaries  # file offset of every statement word
        self.texts = texts            # text-statement offsets (of the st word)
        self.targets = targets        # (u32 field offset, stored value)
        self.end = end


def _word(program, pos):
    return program[pos] | (program[pos + 1] << 8)


def _parse_expr(program, pos, limit):
    while True:
        if pos + 2 > limit:
            raise WalkError("expression runs past the program end", pos)
        tag = _word(program, pos)
        pos += 2
        if tag == 0:
            return pos
        if tag == 1:
            pos = (pos + 3) & ~3
            if pos + 4 > limit:
                raise WalkError("immediate runs past the program end", pos)
            pos += 4
        elif tag in (2, 3, 4):
            if pos + 2 > limit:
                raise WalkError("variable index runs past the program end", pos)
            pos += 2
        elif tag >= 0x80:
            pass  # stack operator, no payload
        else:
            raise WalkError("invalid expression tag 0x%X" % tag, pos - 2)


def _parse_sig(program, pos, limit, sig, targets):
    for atom in sig:
        if atom == "e":
            pos = _parse_expr(program, pos, limit)
        elif atom == "w":
            if pos + 2 > limit:
                raise WalkError("u16 operand runs past the program end", pos)
            pos += 2
        elif atom in ("T", "U"):
            pos = (pos + 3) & ~3
            if pos + 4 > limit:
                raise WalkError("u32 operand runs past the program end", pos)
            if atom == "T":
                targets.append((pos, struct.unpack_from("<I", program, pos)[0]))
            pos += 4
        elif atom == "t":
            if pos + 2 > limit:
                raise WalkError("text length runs past the program end", pos)
            count = _word(program, pos)
            pos += 2
            if pos + 2 * count > limit:
                raise WalkError("text record runs past the program end", pos)
            pos += 2 * count
        else:
            raise AssertionError("unknown atom %r" % atom)
    return pos


def walk(program):
    """Decode one PSI22.00 program; raise WalkError if the grammar breaks."""
    if program[:8] != PSI_MAGIC:
        raise ValueError("not a PSI22.00 program")
    used_end = struct.unpack_from("<I", program, 12)[0] + 16
    if not ENTRY <= used_end <= len(program):
        raise ValueError("invalid PSI2 used length")

    boundaries = set()
    trace = []
    texts = []
    targets = []
    pos = ENTRY
    while pos < used_end:
        if pos + 2 > used_end:
            raise WalkError("statement word runs past the program end", pos)
        boundaries.add(pos)
        st_pos = pos
        st = _word(program, pos)
        trace.append(st_pos)
        pos += 2
        if st in MODE_TABLES:
            if pos + 2 > used_end:
                raise WalkError("sub-opcode runs past the program end", pos)
            sub = _word(program, pos)
            pos += 2
            table = MODE_TABLES[st]
            if table is None:  # mode 2 aliases the statement table at +0x30
                sig = ST_SIGS.get(0x30 + sub)
                if sig is None:
                    raise WalkError("mode-2 sub-op 0x%X has no handler" % sub, st_pos)
            else:
                sig = table.get(sub)
                if sig is None:
                    raise WalkError("sub-op 0x%X has no handler in mode %d"
                                    % (sub, st - 6), st_pos)
        else:
            sig = ST_SIGS.get(st)
            if sig is None:
                err = WalkError("statement 0x%X has no handler" % st, st_pos)
                err.trace = trace
                raise err
            if st in (0x14, 0x15, 0x1D, 0x20):
                texts.append(st_pos)
        try:
            pos = _parse_sig(program, pos, used_end, sig, targets)
        except WalkError as err:
            err.trace = trace
            raise

    for field_pos, value in targets:
        if value + TARGET_BIAS not in boundaries:
            raise WalkError("branch target 0x%X (file 0x%X) is not a "
                            "statement boundary"
                            % (value, value + TARGET_BIAS), field_pos)
    return Walk(boundaries, texts, targets, pos)


def groups(data):
    """Yield (index, start, program bytes) for each real PSI2 group."""
    if data[:4] != b"CMP2":
        raise ValueError("not a CMP2 container")
    count = struct.unpack_from("<I", data, 8)[0]
    previous_end = 0
    for i in range(count):
        n, end = struct.unpack_from("<II", data, 12 + i * 8)
        if end != previous_end + n:
            raise ValueError("CMP2 group %d is non-contiguous" % i)
        start = previous_end * SECTOR
        block = data[start:end * SECTOR]
        if block[:8] == PSI_MAGIC:
            yield i, start, block
        previous_end = end


def check(data):
    """Walk every group; return (walks by index, list of failure strings)."""
    walks = {}
    failures = []
    for i, start, program in groups(data):
        try:
            w = walk(program)
        except WalkError as e:
            context = ""
            trace = getattr(e, "trace", None)
            if trace:
                context = "; last statements " + " ".join(
                    "0x%X:%04X.%04X" % (p, _word(program, p),
                                        _word(program, p + 2))
                    for p in trace[-6:])
            failures.append("group %d (start 0x%X): %s%s" % (i, start, e, context))
            continue
        except ValueError as e:
            failures.append("group %d (start 0x%X): %s" % (i, start, e))
            continue
        # every heuristically found text record must be a walked statement
        found = {off for off, kind, voice, text in bmtext.strings(program)}
        walked = set(w.texts)
        missing = sorted(found - walked)
        if missing:
            failures.append("group %d: %d scanner text records not on "
                            "statement boundaries: %s"
                            % (i, len(missing),
                               " ".join("0x%X" % m for m in missing[:8])))
        walks[i] = w
    return walks, failures


def main(argv):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    data = open(SCENARIO, "rb").read()
    if len(argv) > 1 and argv[1] == "check":
        walks, failures = check(data)
        total_targets = sum(len(w.targets) for w in walks.values())
        print("walked %d PSI2 groups; %d branch targets"
              % (len(walks), total_targets))
        for f in failures:
            print("FAIL " + f)
        return 1 if failures else 0
    if len(argv) > 2 and argv[1] == "dump":
        wanted = int(argv[2], 0)
        for i, start, program in groups(data):
            if i != wanted:
                continue
            w = walk(program)
            print("group %d: %d statements, %d texts, %d targets"
                  % (i, len(w.boundaries), len(w.texts), len(w.targets)))
            for pos, value in w.targets:
                print("  target field 0x%04X -> 0x%04X (file 0x%04X)"
                      % (pos, value, value + TARGET_BIAS))
            return 0
        print("group %d is not a PSI2 group" % wanted)
        return 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
