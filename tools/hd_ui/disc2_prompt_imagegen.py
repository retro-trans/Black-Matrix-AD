"""Replace the pictured blue Insert Disc2 prompt, preserving latest code fixes."""
import argparse
import struct

import numpy as np
from PIL import Image

import battle_selector_alignment as previous
import disc_swap_english as builder
import pvr_atlas

ROOT = previous.ROOT
SOURCE = previous.OUT
OUT = ROOT/'output/patched-discs-disc2-prompt-imagegen-2026-11-02'
STATUS = 'private-disc2-prompt-imagegen-runtime-pending'
ASSET = ROOT/'assets/ui/disc-swap/insert-disc-2-imagegen-v1.png'
ASSET_SHA = '5c78f028d9bc912b543387ffe3b0ed7341bce35da96f883aca1f85a1b203f58c'
EXE_SHA = '9ea7917f6dcae82e29d2cfa7e35606bc53f8f4a085fddf9f0fec0c780a5555d4'
TRACK_HASHES = {1:'c7d0253303e2f3e6756017b31b1a32367f2849db1fbcb0a4671ec3e0b448ccc1',
                2:'d2d43109176ba01774e3491e73126dd98f63338ac882f8b7a024dde056d757d5'}
SYSTEM_HASHES = {1:'9962a3c17e8c53d1689bc7425743b9f1dafea0b6c0107f5e4dfcd42269f49136',
                 2:'8ee6db2a8f5044ed87b15f62dd8abd1cabb5ac709410cbba6340bcdfcb5edad2'}
OFFSET,END = 0x505040,0x565a40
LEAF_SHA = 'af0495c47e7b2ad7937db26af7d458365b448267f9403fd21972b544ffbc7a28'
TEXTS = ('Please insert Disc 2.','Press OPEN to open the disc lid,','then replace the disc.')


def native_image():
    if builder.sha(ASSET.read_bytes()) != ASSET_SHA:
        raise ValueError('Generated artwork differs from reviewed output')
    with Image.open(ASSET) as image:
        if image.width*3 != image.height*4:raise ValueError('Expected full4:3 artwork')
        # Deterministic game-format conversion, not an alternative image edit.
        return image.convert('RGB').resize((640,240),Image.Resampling.LANCZOS)


def patch(system,disc):
    if disc not in SYSTEM_HASHES or builder.sha(system) != SYSTEM_HASHES[disc]:
        raise ValueError('Unknown per-disc SYSTEM source')
    if disc == 2:
        # The pictured insert-Disc2 artwork belongs to Disc1. Do not substitute
        # its SYSTEM offsets into Disc2 or touch the separate red Disc1 prompt.
        return system,[],dict(disc=2,system_sha256=SYSTEM_HASHES[2],
            changed_system_bytes=0,unchanged=True),None
    cols,rows,_,pages = pvr_atlas.scl_layout(system,OFFSET)
    if (cols,rows,len(pages)) != (40,15,3) or pages[-1]+16+131072 != END:
        raise ValueError('Unknown native blue prompt allocation')
    if builder.sha(system[OFFSET:END]) != LEAF_SHA:
        raise ValueError('Unknown boxed prompt')
    users,pos = [],0
    while (pos:=system.find(b'SCL ',pos)) >= 0:
        try:
            if set(pages).intersection(pvr_atlas.scl_layout(system,pos)[3]):users.append(pos)
        except (ValueError,IndexError,struct.error):pass
        pos += 4
    if users != [OFFSET]:raise ValueError('Prompt pages have other consumers')
    after = bytearray(system)
    image = native_image()
    tiles = pvr_atlas.encode_scl(after,OFFSET,image)
    allowed = np.zeros(len(system),dtype=bool)
    allowed[OFFSET+32:OFFSET+32+2400] = True
    for page in pages:allowed[page+16:page+16+131072] = True
    delta = np.flatnonzero(np.frombuffer(system,'u1') != np.frombuffer(after,'u1')).tolist()
    if not delta or np.any(~allowed[delta]):raise ValueError('Out-of-screen edit')
    decoded = pvr_atlas.decode_scl(after,OFFSET)
    if decoded.tobytes() != builder.quantized(image).tobytes():
        raise ValueError('Native artwork readback differs')
    report = dict(disc=1,offset=hex(OFFSET),end=hex(END),tiles=tiles,
        source_leaf_sha256=LEAF_SHA,system_sha256=builder.sha(after),
        changed_system_bytes=len(delta),asset=str(ASSET.relative_to(ROOT)),
        asset_sha256=ASSET_SHA,texts=TEXTS,source_background_pixel_exact=False,
        native_rgb_sha256=builder.sha(decoded.tobytes()),
        method='built-in ImageGen full artwork; reviewed then downsampled and RGB565 packed',
        all_headers_and_other_archive_bytes_unchanged=True)
    return bytes(after),delta,report,decoded


def build():
    builder.build(out=OUT,source=SOURCE,status=STATUS,source_status=previous.STATUS,
        exe_sha=EXE_SHA,track_hashes=TRACK_HASHES,patcher=patch,texts=TEXTS,
        preview_name='insert-disc-2-preview.png',launcher='Disc 2 Prompt Art',
        readme=('PRIVATE full English disc pair: ImageGen blue Insert Disc2 prompt.\n'
            'Pictured modern text boxes replaced with ivory lettering directly over dark teal artwork.\n'
            'Generated full background is not pixel-identical to the original.\n'
            'Only Disc1 blue normal Insert Disc2 SCL changes; Disc2 tracks are byte-identical to source.\n'
            'Wrong/missing-disc error artwork and the red Insert Disc1 prompt are unchanged.\n'
            'Battle/Cook/Items alignment, clear footer fonts, AP warning, repaired movies, Domina/Zero retained.\n'
            'Use Play - Disc 1 - Disc 2 Prompt Art.cmd or matching Disc2 launcher in project folder.\n'
            'Close Flycast first. Same original VMUs and full1440 launch-only rendering settings.\n'
            'No save/config writes; previous builds and originals preserved.\n'
            'Binary checks verified; fresh in-game artwork/disc swap and hardware unverified.\n'
            'Keep complete game images local/private; no upload or publication.\n'))


def launch(disc):
    builder.domina.zero.launch(disc,build=OUT,status=STATUS,settings=builder.renderer_settings())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--launch',type=int,choices=(1,2))
    args = parser.parse_args()
    if args.build:build()
    if args.launch:launch(args.launch)
