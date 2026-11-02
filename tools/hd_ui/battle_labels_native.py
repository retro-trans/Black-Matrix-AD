"""Bake missing Normal/Latent/Attack sprites into both native disc copies."""
import argparse

import numpy as np
from PIL import Image,ImageDraw

import disc2_prompt_imagegen as previous
import disc_swap_english as builder
import attack_mode_labels as legacy
import attack_mode_split_labels as split
import skies_vga_optical_baseline as optical
import skies_vga_font_metrics as font
import skies_rayblade_match as header
import skies_full_texture as full
import pvr_atlas

ROOT = previous.ROOT
SOURCE = previous.OUT
OUT = ROOT/'output/patched-discs-battle-labels-2026-11-02'
STATUS = 'private-native-battle-labels-runtime-pending'
VERSION = '0.1.0'  # First private battle-label artwork revision, not a release tag.
EXE_SHA = previous.EXE_SHA
CHAR_SHA = '96b7377621b07f7a8bf6a6a8ddbd40947fff66fac572632fb4876960c0ae57cd'
TRACK_HASHES = {1:'ddae3aa39f62c70489957726da2dbb3a8b57bb4464aac7aabd148a9f661f1975',
                2:'d2d43109176ba01774e3491e73126dd98f63338ac882f8b7a024dde056d757d5'}
TEXTURE = 0x1350
RECTS = {i:r for i,(_,r) in legacy.LABELS.items()}|split.RECTS|{161:(192,224,224,240)}
LABELS = {93:'Normal',94:'Latent',163:'Normal',164:'Latent',161:'Attack'}
TRACKING = -1  # One common logical-pixel tracking adjustment; no glyph stretching.


def font_inputs(texts=None):
    exe = (SOURCE/'1ST_READ.BIN').read_bytes()
    if builder.sha(exe) != EXE_SHA:raise ValueError('Unknown current executable')
    system = builder.READER.read_file(builder.track(SOURCE,2),'SYSTEM.DAT')[0]
    if builder.sha(system) != previous.SYSTEM_HASHES[2]:raise ValueError('Unknown font archive')
    glyphs = optical.corrected_glyphs()[1]
    forward = exe[full.prior.atlas.FORWARD-full.prior.atlas.BASE:full.prior.atlas.FORWARD-full.prior.atlas.BASE+256]
    pages = [full.decode_vq(system[full.prior.FONT_OFFSET+16+b*128:full.prior.FONT_OFFSET+16+b*128+8192]) for b in full.BANKS]
    for ch in set(''.join(LABELS.values() if texts is None else texts)) - {' '}:
        slot = forward[full.prior.latin.charmap()[ch]]
        x,y = slot%8*16,slot%32//8*32
        if pages[slot//32].crop((x,y,x+16,y+32)).tobytes() != header.glyph(ch,glyphs).tobytes():
            raise ValueError('Approved font differs from actual current glyph '+ch)
    return exe,glyphs


def word_mask(text,exe,glyphs,native_width=32):
    # Same approved24-source-row masks and baseline for every character.
    line = Image.new('L',(192,24))
    pen = 0
    for ch in text:
        glyph = glyphs[ch]
        left = glyph.getbbox()[0]
        for y in range(24):
            for x in range(12):
                a = glyph.getpixel((x,y))
                px = pen+2+x-left
                if a:line.putpixel((px,y),max(a,line.getpixel((px,y))))
        pen += exe[font.ritual.size.SMALL_ADV-full.prior.atlas.BASE+full.prior.latin.charmap()[ch]]+TRACKING
    box = line.getbbox()
    if not box or box[2]-box[0] > native_width*2-2:raise ValueError('Word exceeds original badge')
    width = native_width*4
    mask = Image.new('L',(width,64))
    # Source half-scale on both axes compensates existing spriteX2/scanoutY2.
    x = (width-(box[2]-box[0])*2)//2-box[0]*2
    mask.paste(line.resize((384,48),Image.Resampling.NEAREST),(x,2))
    b = mask.getbbox()
    if not b or b[0] < 1 or b[2] > width-1 or b[3] > 50:raise ValueError('Badge ink clips')
    return mask


def artwork(before):
    exe,glyphs = font_inputs()
    page = pvr_atlas.decode(before,TEXTURE)
    masks = {t:word_mask(t,exe,glyphs) for t in set(LABELS.values())}
    result = {}
    for index,text in LABELS.items():
        # Preserve the actual existing native peak shade (bright213/dim115),
        # rather than copying legacy HD-only dark49 assumptions.
        peak = max(px[0] for px in page.crop(RECTS[index]).getdata() if px[3])
        level = round(peak*31/255)
        colour = (level*255+30)//31  # Inverse of existing native.encode floor.
        # Downsample alpha alone: resampling RGBA can overshoot constant gray,
        # making active/inactive lettering brighter than its native source.
        art = Image.new('RGBA',(32,16),(colour,colour,colour,0))
        alpha = masks[text].resize((32,16),Image.Resampling.LANCZOS)
        maximum = alpha.getextrema()[1]
        alpha = alpha.point(lambda a:round(a*255/maximum))
        art.putalpha(alpha)
        result[index] = art
    for whole,(left,right) in split.PAIRS.items():
        result[left] = result[whole].crop((0,0,16,16))
        result[right] = result[whole].crop((16,0,32,16))
    return result


def preview(after):
    page = pvr_atlas.decode(after,TEXTURE)
    out = Image.new('RGB',(640,480),'#111715')
    draw = ImageDraw.Draw(out)
    draw.text((16,10),'Native battle label preview - not an in-game screenshot',fill='white')
    for row,(index,text) in enumerate(LABELS.items()):
        # Uniform enlargement keeps the native32x16 sprite's aspect ratio.
        tile = page.crop(RECTS[index]).resize((192,96),Image.Resampling.NEAREST)
        x,y = 20+(row%2)*310,42+(row//2)*125
        out.paste(tile,(x,y),tile)
        draw.text((x,y+100),text+(' (dim)' if index in (163,164) else ''),fill='#dddddd')
    return out


def patch(before,disc):
    if disc not in (1,2) or builder.sha(before) != CHAR_SHA:
        raise ValueError('Unknown per-disc native CHAR source')
    rows = legacy.pack.descriptors(before,TEXTURE)
    if any(rows[i] != r for i,r in RECTS.items()):raise ValueError('Badge descriptors changed')
    original = legacy.ui.japanese_audit.archive(disc,'CHAR.DAT')
    source_page,original_page = pvr_atlas.decode(before,TEXTURE),pvr_atlas.decode(original,TEXTURE)
    for rect in RECTS.values():
        if source_page.crop(rect).tobytes() != original_page.crop(rect).tobytes():
            raise ValueError('Label is no longer the known original Japanese')
    after = bytearray(before)
    allowed = set()
    for index,art in artwork(before).items():
        for offset,value in legacy.native.encode(before,TEXTURE,RECTS[index],art):
            after[offset:offset+2] = value
            allowed.update((offset,offset+1))
    delta = np.flatnonzero(np.frombuffer(before,'u1') != np.frombuffer(after,'u1')).tolist()
    if not delta or not set(delta).issubset(allowed):raise ValueError('Out-of-label changes')
    report = dict(disc=disc,char_sha256=builder.sha(after),changed_char_bytes=len(delta),
        labels=LABELS,split_pairs=split.PAIRS,rectangles=RECTS,
        font='Exact currently approved Skies masks',uniform_tracking=TRACKING,
        native_scale=[.5,.5],bright_and_inactive_contrast_preserved=True,
        code_bp_fields_costs_and_actions_unchanged=True,
        all_headers_descriptors_and_other_pixels_unchanged=True)
    return bytes(after),delta,report,preview(after)


def build():
    builder.build(out=OUT,source=SOURCE,status=STATUS,source_status=previous.STATUS,
        exe_sha=EXE_SHA,track_hashes=TRACK_HASHES,patcher=patch,archive='CHAR.DAT',version=VERSION,
        preview_name='battle-labels-preview.png',texts=('Normal','Latent','Attack'),launcher='Battle Labels',
        readme=('PRIVATE battle-label build0.1.0: cumulative English discs.\n'
            'Normal / Latent: bright, dim and separately drawn inactive halves; Attack badge.\n'
            'Uses approved current font shapes and one common tighter spacing; original sizes retained.\n'
            'Only9 sprite pixel regions in CHAR.DAT change, on both discs.\n'
            'Code, BP names/costs, combat, fonts, SYSTEM artwork and movies unchanged.\n'
            'All latest alignment, footer, AP, ImageGen artwork, movie/VGA and Domina/Zero fixes retained.\n'
            'Use Play - Disc 2 - Battle Labels.cmd (or Disc1) in the project folder.\n'
            'Close Flycast first. SAME original-save profile, Port A Slot2 for latest old saves.\n'
            'Do not open CUE with a different Flycast installation: its cards may differ.\n'
            'No save/config writes or automatic emulator restart. In-game appearance pending.\n'
            'Originals/previous builds preserved; keep complete binaries local/private on E:.\n'))


def launch(disc):
    builder.domina.zero.launch(disc,build=OUT,status=STATUS,settings=builder.renderer_settings())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--launch',type=int,choices=(1,2))
    args = parser.parse_args()
    if args.build:build()
    if args.launch:launch(args.launch)
