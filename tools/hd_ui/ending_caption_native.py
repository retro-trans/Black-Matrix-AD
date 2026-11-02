"""Isolated post-credit instant captions; no changes without explicit build.

The formerly null PSI statement13 consumes a normal text record and invokes
the native instant-text helper8C08ADBC. Only the ending's post-STAFF block
uses it. Native16/17/19 own window creation, clearing, and destruction;
original1A/22/1B retain voice loading, start, and completion polling.
"""
from contextlib import contextmanager
import struct

import psi2
import scriptpack
import patchline
import sh4asm

BASE=0x8c010000
CODE=0x8c0f4680
END=0x8c0f46e0  # Existing font UV trampoline starts here; never touch it.
DISPATCH=0x8c09a26c+0x13*4
STREAM=0x8c263ab4
WINDOW=0x8c263b04
INSTANT=0x8c08adbc
OPCODE=0x13
GROUP=558
FIRST=0x54be
FINAL=0x5732


def helper():
    a=sh4asm.Asm(CODE)
    for key,value in dict(stream=STREAM,window=WINDOW,instant=INSTANT).items():a.long_(key,value)
    a.mov_l_dec(8,15);a.mov_l_dec(9,15);a.sts_l_pr(15)
    a.mov_l_pc('stream',8);a.mov_l_at(8,9)
    # Interpreter already consumed opcode. Advance over count+u16 units even
    # when the caller's text starts at address2(mod4); no aligned operands.
    a.mov_w_at(9,0);a.extu_w(0,0);a.shll(0);a.add_i(2,0);a.add(9,0);a.mov_l_store(0,8)
    a.mov_l_pc('window',4);a.mov_l_at(4,4);a.mov(9,5)
    a.mov_l_pc('instant',3);a.jsr(3);a.nop()
    a.lds_l_pr(15);a.mov_l_inc(15,9);a.mov_l_inc(15,8);a.rts();a.mov_i(0,0)
    blob=a.assemble()
    if CODE+len(blob)>END:raise ValueError('Caption helper overlaps existing UV trampoline')
    return blob


@contextmanager
def grammar():
    if OPCODE in psi2.ST_SIGS:raise ValueError('Caption opcode no longer unused')
    psi2.ST_SIGS[OPCODE]='t'
    try:yield
    finally:del psi2.ST_SIGS[OPCODE]


def patch_exe(before,original):
    lo,hi=CODE-BASE,END-BASE;ptr=DISPATCH-BASE
    if any(before[lo:hi]) or any(original[lo:hi]):raise ValueError('Caption helper reservation occupied')
    if before[ptr:ptr+4]!=bytes(4) or original[ptr:ptr+4]!=bytes(4):raise ValueError('Reserved statement13 not null')
    after=bytearray(before);blob=helper();after[lo:lo+len(blob)]=blob
    struct.pack_into('<I',after,ptr,CODE)
    allowed=set(range(lo,lo+len(blob)))|set(range(ptr,ptr+4))
    delta=[i for i,(a,c) in enumerate(zip(before,after)) if a!=c]
    if len(before)!=len(after) or not set(delta)<=allowed:raise ValueError('Out-of-caption executable edit')
    return bytes(after),delta


def caption_record(text):
    # Source dialogue wraps using existing33-cell layout and approved Latin
    # slots. Do not shrink letters to fit; two native caption rows available.
    wrapped,encoded=scriptpack.encode_text(text,cols=33)
    if len(encoded)//2>66:raise ValueError('Caption needs pagination; split into timed cues, not truncation')
    cursor=0
    for char in wrapped:
        cursor=(cursor//33+1)*33 if char=='\n' else cursor+1
    if cursor>66:raise ValueError('Caption exceeds two visible rows')
    # Keep all existing PSI instructions at the same modulo4 alignment.
    # A null-handler0 is NOT safe executable padding: dispatch retains R4.
    # An invisible trailing space remains inside the consumed text record.
    if len(encoded)%4:encoded+=struct.pack('<H',patchline.SPACE)
    record=struct.pack('<HH',OPCODE,len(encoded)//2)+encoded
    return record,wrapped


def patch_program(program,captions):
    w=psi2.walk(program);bounds=sorted(w.boundaries)+[w.end]
    cue_offsets={}
    for start,end in zip(bounds,bounds[1:]):
        if not FIRST<=start<FINAL or struct.unpack_from('<H',program,start)[0]!=0x1a:continue
        field=(start+4+3)&~3;voice=struct.unpack_from('<I',program,field)[0]
        cue_offsets[start]=voice
    if set(cue_offsets.values())!=set(range(0xa09,0xa1b)) or set(captions)!=set(cue_offsets.values()):
        raise ValueError('Caption inventory must exactly match18 post-credit voices')
    # Open the existing transparent narration window before the first load.
    # No text18/button-wait statement is introduced.
    inserts={FIRST:struct.pack('<6H',0x16,1,0,0,0,0)}
    report=[]
    for start,voice in cue_offsets.items():
        end=bounds[bounds.index(start)+1]
        # Every original cue must be immediately followed by start and wait.
        if program[end:end+4]!=struct.pack('<2H',0x22,0x1b):raise ValueError('Voice cue pattern changed')
        record,wrapped=caption_record(captions[voice])
        inserts[end]=record
        # Maintain modulo4 with a harmless extra voice-end poll: original1B
        # just returned0 (not playing), so this poll also returns0 immediately.
        # The final cue clears+closes instead, before the image is destroyed.
        inserts[end+4]=struct.pack('<2H',0x17,0x19 if end+4==FINAL else 0x1b)
        report.append(dict(voice=voice,original_offset=start,text=wrapped))
    # Inserts at branch destinations must execute BEFORE their old target.
    # Target mapping therefore counts inserts strictly before an old address.
    def mapped(pos):return pos+sum(len(blob) for off,blob in inserts.items() if off<pos)
    rebuilt=bytearray();previous=0
    for off,blob in sorted(inserts.items()):
        rebuilt+=program[previous:off];rebuilt+=blob;previous=off
    rebuilt+=program[previous:w.end]
    # Mapping for operand storage counts an insertion at that same address;
    # only branch-destination semantics differ from storage positions.
    def stored(pos):return pos+sum(len(blob) for off,blob in inserts.items() if off<=pos)
    for field,value in w.targets:struct.pack_into('<I',rebuilt,stored(field),mapped(value+16)-16)
    struct.pack_into('<I',rebuilt,12,len(rebuilt)-16)
    with grammar():checked=psi2.walk(bytes(rebuilt))
    if len(checked.targets)!=len(w.targets):raise ValueError('Branch count changed')
    # Reconstruct every original instruction byte-for-byte, ignoring only
    # relocated branch fields and the PSI length header.
    restored=bytearray();previous=0
    for off,blob in sorted(inserts.items()):
        begin=stored(previous) if previous in inserts else mapped(previous)
        finish=mapped(off)
        restored+=rebuilt[begin:finish];previous=off
    restored+=rebuilt[stored(previous):]
    struct.pack_into('<I',restored,12,w.end-16)
    for field,value in w.targets:struct.pack_into('<I',restored,field,value)
    if restored!=program[:w.end]:raise ValueError('Original ending instructions changed')
    result=bytes(rebuilt)+bytes(scriptpack.align_sector(len(rebuilt))-len(rebuilt))
    return result,report


def patch_archive(before,captions):
    groups=scriptpack.split_groups(before);old=groups[GROUP]
    groups[GROUP],report=patch_program(old,captions)
    result=bytearray(b''.join(groups));running=0
    for i,g in enumerate(groups):
        count=len(g)//2048;running+=count;struct.pack_into('<II',result,12+i*8,count,running)
    if len(result)>len(before):raise ValueError('Scenario needs verified ISO relocation; do not overwrite next file')
    result+=bytes(len(before)-len(result))
    checked=scriptpack.split_groups(result)
    if any(a!=c for i,(a,c) in enumerate(zip(scriptpack.split_groups(before),checked)) if i not in (0,GROUP)):
        raise ValueError('Unrelated scenario group changed')
    with grammar():
        for i,start,p in psi2.groups(result):psi2.walk(p)
    return bytes(result),report
