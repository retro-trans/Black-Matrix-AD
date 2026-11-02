"""Inset admitted battle-command text two native pixels; preserve prior menus."""
import argparse
import struct

import footer_remaining_font as prior
import skies_vga_item_alignment as placement

ROOT = prior.ROOT
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-battle-alignment-2026-11-02'
STATUS = 'private-battle-command-alignment-runtime-pending'
BASE = prior.BASE
EXE_SHA = 'f071cc38c82fb337031782b4d44a29db6a8339cd73c7358108cf3bc476bfc441'
TRACK_HASHES = {1:'c88af549c93203423c22edc2dc1a6432f6a1ae49ae5977cef7bdefe4d0d54cb5',
                2:'74543b5f2745a681cc96acc5f21380d0ed33bb6b37ca1420f90ed84a97cc153b'}
CAPTURE = ROOT/'build/choice-selector-inspection-2026-11-02/ram-4000-1793589261118806200.bin'
CAPTURE_SHA = '674ebceca0c4cf6f5ccfae16dfe811c6a47b8b794ccd8cf5082807d6e45bd3ae'
CONTEXT = placement.CONTEXT


def patch(exe):
    if prior.prior.prior.sha(exe) != EXE_SHA:
        raise ValueError('Expected current footer/AP/choice-fixed executable')
    ram = CAPTURE.read_bytes()
    if prior.prior.prior.sha(ram) != CAPTURE_SHA:
        raise ValueError('Unknown authenticated battle menu capture')
    lo,hi = placement.HELPER-BASE,placement.HELPER_END-BASE
    old = placement.item_helper(choice_rows=True)
    new = placement.item_helper(choice_rows=True,battle_rows=True)
    if exe[lo:hi] != old+bytes(hi-lo-len(old)):
        raise ValueError('Unknown previous scoped placement wrapper')
    if any((ROOT/'extracted/1ST_READ.BIN').read_bytes()[lo:hi]):
        raise ValueError('Original reservation occupied')
    # Live game was the older English Disc Swap build. Validate its exact
    # known wrapper and unchanged sampler, not just a common EXE prefix.
    live_old = placement.item_helper()
    if ram[placement.HELPER-0x8c000000:placement.HELPER_END-0x8c000000] != live_old+bytes(hi-lo-len(live_old)):
        raise ValueError('Captured live wrapper differs')
    uv = placement.geometry.full.UV
    if ram[uv-0x8c000000:placement.geometry.full.END-0x8c000000] != exe[uv-BASE:placement.geometry.full.END-BASE]:
        raise ValueError('Captured canonical sampling differs')
    c = CONTEXT-0x8c000000
    if tuple(struct.unpack_from('<H',ram,c+o)[0] for o in (8,10,14)) != (9,8,2):
        raise ValueError('Not the measured battle-command grid')
    if struct.unpack_from('<H',exe,0x1d436)[0] != 0xe409:
        raise ValueError('Native nine-column battle constructor changed')
    if len(new) != hi-lo:
        raise ValueError('New helper must fit exact existing108-byte reservation')
    after = exe[:lo]+new+exe[hi:]
    delta = [i for i,(a,b) in enumerate(zip(exe,after)) if a != b]
    if not delta or any(not lo <= i < hi for i in delta):
        raise ValueError('Out-of-placement edit')
    return after,delta


def build():
    prior.prior.prior.domina.zero.build(out=OUT,patcher=patch,status=STATUS,edits=(),
        first_choice='Domina',launcher='Battle Alignment',source=SOURCE,
        source_status=prior.STATUS,source_track_hashes=TRACK_HASHES,
        readme_notes=('BATTLE COMMAND TEXT ALIGNMENT\n'
            'All eight battle-command rows move down 2 native pixels inside the existing selector.\n'
            'Font size, horizontal position, selector/arrow, disabled states and actions unchanged.\n'
            'Existing Items and Yes/No/Explain alignment is retained exactly.\n'
            'Clear Exit/Manual/Max/Reset font, AP warning and all previous movie/art fixes retained.\n'
            'Same original VMUs and 1440 launch settings; no save/config writes.\n'
            'Separate dialogue topic-list alignment still awaits its live measurement.\n\n'),
        extra_report=dict(battle_alignment=dict(context=hex(CONTEXT),grid=[9,8],native_y_inset=2,
            capture_sha256=CAPTURE_SHA,helper_bytes=108,
            selector_arrow_font_size_uv_and_input_unchanged=True,
            existing_items_and_cook_geometry_preserved=True,
            fallback_and_star_unchanged=True),
            footer_ap_movie_artwork_and_1440_launcher_retained=True,
            topic_list_alignment_pending=True))


def launch(disc):
    prior.prior.prior.domina.zero.launch(disc,build=OUT,status=STATUS,
        settings=prior.prior.prior.renderer_settings())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--launch',type=int,choices=(1,2))
    args = parser.parse_args()
    if args.build:build()
    if args.launch:launch(args.launch)
