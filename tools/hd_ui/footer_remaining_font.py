"""Match four remaining footer captions to the existing live canonical font.

Use only guarded padding in the existing footer code/table reservations.
No SYSTEM/font image edits, new texture allocations, or emulator/save writes.
"""
import argparse
import struct

import ap_warning_font as prior
import native_translation_parity as native
import skies_vga_sharp_footer as footer

ROOT = prior.ROOT
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-footer-font-2026-11-02'
STATUS = 'private-remaining-footer-font-runtime-pending'
BASE = prior.BASE
EXE_SHA = '41e06b8ed54d5643e0c5144cad2510d5b0034c8d1f90bb49c7f0b34b582cbffa'
TRACK_HASHES = {1:'2a47cca7ca66d945e98b9d982d125d6c7ccf133dc6747ce2bfcfced981ee8b7e',
                2:'e6bb569eec5e809c98a1c2253ca00b11cdd20f5fdd7ce8f4ef0c2c7b9fab6205'}
LABELS = {65:'Exit',54:'Manual',56:'Max',69:'Reset'}
RECTS = {54:(0,160,56,176),56:(64,96,104,112),
         65:(0,224,32,240),69:(64,224,120,240)}
EXTRA = footer.DRAW+len(footer.draw())
CAPTURE = prior.CAPTURE
CAPTURE_SHA = prior.CAPTURE_SHA


def row(index):
    ids = bytes(footer.prior.latin.charmap()[c] for c in LABELS[index])
    if not 0 < len(ids) <= 7 or any(i == 0 for i in ids):
        raise ValueError('Unknown caption glyph/length')
    return bytes([index])+ids+bytes(7-len(ids))+struct.pack('<4H',*RECTS[index])


def patch(exe):
    if prior.prior.sha(exe) != EXE_SHA:
        raise ValueError('Expected authenticated AP/choice-fixed executable')
    original = (ROOT/'extracted/1ST_READ.BIN').read_bytes()
    capture = CAPTURE.read_bytes()
    if prior.prior.sha(capture) != CAPTURE_SHA:
        raise ValueError('Unknown read-only padding guard capture')
    old, new = footer.main(), footer.main(extra_table=EXTRA)
    table = footer.label_table()
    blocks = ((footer.MAIN,footer.MAIN_END,old,new),
              (footer.TABLE,footer.TABLE_END,table,table+row(65)),
              (EXTRA,footer.DRAW_END,b'',b''.join(row(i) for i in (54,56,69))))
    result = bytearray(exe)
    allowed = set()
    for address,end,before,after in blocks:
        lo,hi = address-BASE,end-BASE
        if len(after) > hi-lo or exe[lo:hi] != before+bytes(hi-lo-len(before)):
            raise ValueError('Unknown footer code/table or occupied padding')
        if any(original[lo:hi]):
            raise ValueError('Original reservation is occupied')
        if capture[address-0x8c000000:end-0x8c000000] != exe[lo:hi]:
            raise ValueError('Live footer reservation differs')
        result[lo:hi] = after+bytes(hi-lo-len(after))
        allowed.update(range(lo,hi))
    delta = [i for i,(a,b) in enumerate(zip(exe,result)) if a != b]
    if not delta or not set(delta).issubset(allowed) or len(result) != len(exe):
        raise ValueError('Unexpected footer patch scope')
    return bytes(result),delta


def build():
    # Guard both discs' existing sprite UVs before constructing the table.
    for disc in (1,2):
        data = prior.prior.READER.read_file(prior.prior.track(SOURCE,disc),'SYSTEM.DAT')[0]
        rows = native.pack.descriptors(data,0x21890)
        if any(rows[index] != rect for index,rect in RECTS.items()):
            raise ValueError('Disc-specific caption UVs differ')
    prior.prior.domina.zero.build(out=OUT,patcher=patch,status=STATUS,edits=(),
        first_choice='Domina',launcher='Footer Font Fix',source=SOURCE,
        source_status=prior.STATUS,source_track_hashes=TRACK_HASHES,
        readme_notes=('REMAINING FOOTER FONT FIX\n'
            'Exit, Manual, Max and Reset now use the same live font as Equip/Magic.\n'
            'Identical glyph size, advances, baseline and sampling; no bitmap rescaling.\n'
            'Icons, actions, disabled/fade fallback and all existing nine captions retained.\n'
            'AP warning and cooking-choice fixes, English artwork and movies retained.\n'
            'Same original VMUs and 1440 launch-only rendering settings; no save/config writes.\n'
            'Topic-list alignment is not included: its live measurement is still pending.\n\n'),
        extra_report=dict(footer_labels=LABELS,footer_caption_uvs=RECTS,
            expanded_primary_table_rows=10,secondary_table_rows=3,
            secondary_table=hex(EXTRA),footer_helper_bytes=len(footer.main(extra_table=EXTRA)),
            existing_geometry_uv_and_texture_handles_unchanged=True,
            fallback_and_lifetime_guards_retained=True,
            extra_nodes_textures_or_allocator_units=0,
            ap_warning_choice_alignment_and_1440_launcher_retained=True,
            topic_list_alignment_pending=True))


def launch(disc):
    prior.prior.domina.zero.launch(disc,build=OUT,status=STATUS,
                                 settings=prior.prior.renderer_settings())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--launch',type=int,choices=(1,2))
    args = parser.parse_args()
    if args.build:build()
    if args.launch:launch(args.launch)
