"""Render the AP warning as ordinary Latin, not an unadmitted compound record.

The original warning window already has14 columns, but its11-character record
uses two native compound glyphs for the counter. Keep its geometry and logic;
replace that record with14 ordinary Latin characters and update the existing
two SJIS digit stores. This enables the unchanged canonical font admission path.
"""
import argparse
import struct

import disc_swap_english as prior
import patchline
import skies_vga_item_alignment as choices

ROOT = prior.ROOT
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-ap-font-2026-11-02'
STATUS = 'private-ap-warning-font-runtime-pending'
BASE = 0x8c010000
EXE_SHA = prior.EXE_SHA
RECORD = 0x8c0f48e0
END = 0x8c0f4900
ENTRY = 0x8c04e4ce
CONTEXT = 0x8c1d41b4
STATE = 0x8c1d342c+36
CAPTURE = ROOT/'build/choice-selector-inspection-2026-11-02/ram-8136-1793586927658869000.bin'
CAPTURE_SHA = '27bfbbfb94ea9119b7cbc5b491bc4cfafdb4f4a53ba5ba3708c98888cf922706'
CHOICE_CAPTURE = ROOT/'build/choice-selector-inspection-2026-11-02/ram-4000-1793587415680059300.bin'
CHOICE_CAPTURE_SHA = '917950a9f2d4fc073332cc168c1612c64ff9ba574fba868440c001b690e6fd3a'
TRACK_HASHES = {1: 'e5985c35d9de38bf84cd1dbc0de5558acef64391e95c3f1d57ba6c26370bbaef',
                2: 'ae611e0e7bc6113dc5c843db431ae3c8ec0a3f1836ef76a97ae1dbdd31b974c6'}
WORDS = ((0x8c04e506, 0x81da, 0x81db),    # current digit -> record+22
         (0x8c04e50e, 0x816b, 0x816d),    # required digit -> record+26
         (0x8c04e524, 0xe30b, 0xe30e))    # text length11 ->14, grid already14
LONGS = ((0x8c04e684, 0x8c098c80, RECORD),
         (0x8c04e68c, 0x000083a7, 0x0000824f),  # compound base -> fullwidth0
         (0x8c04e690, 0x000083ab, 0x0000824f))


def record():
    text = 'AP: LOW! (0/1)'
    if len(text) != 14:
        raise ValueError('Unexpected AP warning length')
    return struct.pack('<15H', len(text), *(patchline.to_sjis(c) for c in text))


def patch(exe):
    if prior.sha(exe) != EXE_SHA:
        raise ValueError('Unknown current English disc-swap executable')
    original = (ROOT/'extracted/1ST_READ.BIN').read_bytes()
    ram = CAPTURE.read_bytes()
    if prior.sha(ram) != CAPTURE_SHA or ram[0x10000:0x10080] != exe[:128]:
        raise ValueError('Unauthenticated read-only RAM guard')
    lo, hi = RECORD-BASE, END-BASE
    if any(exe[lo:hi]) or any(original[lo:hi]) or any(ram[RECORD-0x8c000000:END-0x8c000000]):
        raise ValueError('AP record reservation occupied')
    # Preserve the original width14/height1 and all state/input/action paths.
    if exe[0x8c04e51a-BASE:0x8c04e524-BASE] != bytes.fromhex('0ee002e5428101e04381'):
        raise ValueError('Native14-column warning window differs')
    after = bytearray(exe)
    allowed = set(range(lo, hi))
    for fmt, entries in (('<H', WORDS), ('<I', LONGS)):
        size = struct.calcsize(fmt)
        for address, before, new in entries:
            off = address-BASE
            if struct.unpack_from(fmt, exe, off)[0] != before:
                raise ValueError('Unknown AP writer instruction/data')
            struct.pack_into(fmt, after, off, new)
            allowed.update(range(off, off+size))
    after[lo:lo+len(record())] = record()
    # Extend the existing Items placement wrapper, not the shared UV sampler.
    # Old defaults remain byte-identical for historical build/test guards.
    start, end = choices.HELPER-BASE, choices.HELPER_END-BASE
    old, new = choices.item_helper(), choices.item_helper(choice_rows=True)
    live = CHOICE_CAPTURE.read_bytes()
    if prior.sha(live) != CHOICE_CAPTURE_SHA or live[0x10000:0x10080] != exe[:128]:
        raise ValueError('Choice selector capture is not authenticated')
    if exe[start:end] != old+bytes(end-start-len(old)) or any(original[start:end]):
        raise ValueError('Unknown choice placement wrapper/reservation')
    if live[choices.HELPER-0x8c000000:choices.HELPER_END-0x8c000000] != exe[start:end]:
        raise ValueError('Live helper reservation differs')
    after[start:end] = new+bytes(end-start-len(new))
    allowed.update(range(start, end))
    delta = [i for i, (a, b) in enumerate(zip(exe, after)) if a != b]
    if not delta or not set(delta).issubset(allowed):
        raise ValueError('Unexpected AP warning patch scope')
    return bytes(after), delta


def build():
    prior.domina.zero.build(out=OUT, patcher=patch, status=STATUS, edits=WORDS+LONGS,
        first_choice='Domina', launcher='AP Font Fix', source=SOURCE,
        source_status=prior.STATUS, source_track_hashes=TRACK_HASHES,
        readme_notes=('AP WARNING FONT + COOKING CHOICE ALIGNMENT\n'
            'AP: LOW! now uses the regular Latin font, including its current/required counter.\n'
            'AP costs, counter values and warning window size are unchanged.\n'
            'Yes / No / Explain labels move down 2 native pixels inside their existing selector.\n'
            'Their font size, selector, arrow, controls and other menu layouts are unchanged.\n'
            'The English disc-swap artwork and all previous movie/font fixes are retained.\n'
            'The launchers retain the established 1440 rendering settings and original VMUs.\n'
            'No save or emulator configuration was rewritten. Fresh in-game appearance pending.\n\n'),
        extra_report=dict(ap_warning=dict(text='AP: LOW! (current/required)',
            ordinary_latin_record_characters=14, original_window_columns=14,
            original_record_characters=11, mutable_record=hex(RECORD),
            current_ap_values=list(range(5)), required_ap_values=list(range(1, 6)),
            original_action_cost_logic_and_window_geometry_unchanged=True,
            canonical_font_pixels_tables_and_uv_samplers_unchanged=True,
            existing_allocator_and_forecast_limits_unchanged=True,
            note='Ordinary native capacity14 uses7 units vs6 for11; existing admission budget remains authoritative.'),
            choice_alignment=dict(context=hex(choices.CONTEXT), grid=[7,3], native_y_inset=2,
                selector_box_and_arrow_unchanged=True, glyph_size_and_uv_unchanged=True,
                existing_items_8x9_alignment_preserved=True, capture_sha256=CHOICE_CAPTURE_SHA),
            english_disc_swap_artwork_and_1440_launcher_retained=True))


def launch(disc):
    prior.domina.zero.launch(disc, build=OUT, status=STATUS, settings=prior.renderer_settings())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--launch', type=int, choices=(1, 2))
    args = parser.parse_args()
    if args.build:
        build()
    if args.launch:
        launch(args.launch)
