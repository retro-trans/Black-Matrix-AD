"""Initially highlight native Domina/index0; keep the real Zero unlock enabled.

The only extra difference from zero_unlocked is MOV #5,R2 -> MOV #0,R2 at
8c05c296. Do not reorder character/name/route tables or auto-confirm a choice.
"""
import argparse
import struct

import zero_unlocked as zero

ROOT = zero.ROOT
OUT = ROOT/'output/patched-discs-domina-first-2026-11-02'
STATUS = 'private-domina-first-zero-unlocked-runtime-pending'
FIRST = 0x8c05c296
EDITS = zero.EDITS + ((FIRST, 0xe205, 0xe200),)


def patch(exe):
    unlocked, prior_delta = zero.patch(exe)
    off = FIRST-zero.BASE
    if unlocked[off:off+6] != bytes.fromhex('05e217a0222e'):
        raise ValueError('Native first-choice instruction/branch differs')
    result = bytearray(unlocked)
    struct.pack_into('<H', result, off, 0xe200)
    delta = [i for i, (a, b) in enumerate(zip(exe, result)) if a != b]
    if set(delta) != set(prior_delta) | {off}:
        raise ValueError('Unexpected first-choice delta')
    return bytes(result), delta


def build():
    zero.build(out=OUT, patcher=patch, status=STATUS, edits=EDITS,
               first_choice='Domina', launcher='Domina First')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--launch', type=int, choices=(1, 2))
    args = parser.parse_args()
    if args.build:
        build()
    if args.launch:
        zero.launch(args.launch, build=OUT, status=STATUS)
