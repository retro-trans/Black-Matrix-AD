"""Improve Normal/Latent native sprite contrast without runtime changes."""
import argparse

import numpy as np
from PIL import Image,ImageDraw,ImageFilter

import thinking_label_native as prior
import pvr_atlas

ROOT = prior.ROOT
b = prior.b
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-mode-readability-2026-11-02'
STATUS = 'private-mode-label-readability-runtime-pending'
VERSION = '0.1.6'
EXE_SHA = prior.EXE_SHA
TRACK_HASHES = {1:'aa2058fa781be9821ef3ca0d79d8da9a90eb53fa14aa654d507702d4661d8b4d',
                2:'2c78e46e484cf5e009a5c8959e155d6c833ae38b93e157285fbaec31d44aad1c'}
CHAR_SHA = 'f549376ba93c178e4e7e3878836debbc3d372c632794a37315fa0f20ae94483f'
TEXTURE = 0x1350
font = prior.prior.lettering
LABELS = {93:'Normal',94:'Latent',163:'Normal',164:'Latent'}
RECTS = {i:font.RECTS[i] for i in LABELS}|font.split.RECTS
LEVELS = {93:255,94:255,163:180,164:180}
COVERAGE = 96  # One common threshold; no word/state-specific weight or fit.


def core_mask(text):
    exe,glyphs=prior.prior.font_inputs('NormalLatent',SOURCE)
    # Same existing font/size/position. Native ARGB1555 has only binary alpha;
    # store solid foreground pixels instead of gray preblended thin strokes.
    alpha=font.word_mask(text,exe,glyphs).resize((32,16),Image.Resampling.LANCZOS)
    return alpha.point(lambda a:255 if a>=COVERAGE else 0)


def artwork():
    result={}
    for index,text in LABELS.items():
        core=core_mask(text);border=core.filter(ImageFilter.MaxFilter(3))
        box=border.getbbox()
        if not box or box[0]<0 or box[1]<0 or box[2]>32 or box[3]>16:
            raise ValueError('Mode outline clips original badge')
        # Glyph pixels use the chosen solid shade; an opaque BLACK one-pixel
        # contour prevents scenery showing through the letter edges. There is
        # no rectangular backing plate or glow, and outside remains transparent.
        art=Image.new('RGBA',(32,16),(0,0,0,0));art.putalpha(border)
        level=LEVELS[index];inv=(round(level*31/255)*255+30)//31
        ink=Image.new('RGBA',(32,16),(inv,inv,inv,0));ink.putalpha(core)
        art=Image.alpha_composite(art,ink)
        result[index]=art
    # Outline BEFORE splitting, so seams match the whole-label variant.
    for whole,(left,right) in font.split.PAIRS.items():
        result[left]=result[whole].crop((0,0,16,16))
        result[right]=result[whole].crop((16,0,32,16))
    return result


def preview(before,after):
    sheet=Image.new('RGB',(640,480),'#10110f');draw=ImageDraw.Draw(sheet)
    draw.text((12,8),'Actual packed sprite comparison on test backgrounds - not in-game',fill='white')
    # Deliberately busy deterministic test swatches, not an edited screenshot.
    colours=('#0b0b0b','#7a7974','#7c2315','#c3b697')
    for row,index in enumerate((93,94,163,164)):
        y=38+row*108
        draw.text((12,y),LABELS[index]+(' (selected)' if index<160 else ' (inactive)'),fill='white')
        for col,data in enumerate((before,after)):
            tile=pvr_atlas.decode(data,TEXTURE).crop(RECTS[index]).resize((192,96),Image.Resampling.NEAREST)
            x=200+col*224
            for j,colour in enumerate(colours):draw.rectangle((x+j*48,y,x+j*48+47,y+95),fill=colour)
            sheet.paste(tile,(x,y),tile)
    draw.text((202,24),'Before',fill='white');draw.text((426,24),'After',fill='white')
    return sheet


def patch(before,disc):
    if disc not in (1,2) or b.sha(before)!=CHAR_SHA:raise ValueError('Unknown cumulative CHAR source')
    rows=font.legacy.pack.descriptors(before,TEXTURE)
    if any(rows[i]!=rect for i,rect in RECTS.items()):raise ValueError('Mode descriptors differ')
    page=pvr_atlas.decode(before,TEXTURE)
    for whole,(left,right) in font.split.PAIRS.items():
        joined=Image.new('RGBA',(32,16))
        joined.paste(page.crop(RECTS[left]),(0,0));joined.paste(page.crop(RECTS[right]),(16,0))
        if joined.tobytes()!=page.crop(RECTS[whole]).tobytes():raise ValueError('Unknown inactive split seam')
    result=bytearray(before);allowed=set()
    for index,art in artwork().items():
        for offset,value in font.legacy.native.encode(before,TEXTURE,RECTS[index],art):
            result[offset:offset+2]=value;allowed.update((offset,offset+1))
    delta=np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(result,'u1')).tolist()
    if not delta or not set(delta)<=allowed or len(before)!=len(result):raise ValueError('Out-of-mode artwork edit')
    report=dict(disc=disc,labels=LABELS,rectangles=RECTS,split_pairs=font.split.PAIRS,
        char_sha256=b.sha(result),source_char_sha256=CHAR_SHA,changed_char_bytes=len(delta),
        active_gray=255,inactive_gray=180,opaque_black_outline_native_pixels=1,
        font_masks_size_baseline_spacing_and_descriptors_unchanged=True,
        foreground_coverage_threshold=COVERAGE,no_background_box=True,
        imagegen_role='Contrast concept reference only; no generated pixels packed',
        all_other_pixels_headers_code_and_gameplay_unchanged=True)
    return bytes(result),delta,report,preview(before,result)


def plan():
    for disc in (1,2):
        source=b.READER.read_file(b.track(SOURCE,disc),'CHAR.DAT')[0]
        print(patch(source,disc)[2],flush=True)


def build():
    b.build(out=OUT,source=SOURCE,status=STATUS,source_status=prior.STATUS,
        exe_sha=EXE_SHA,track_hashes=TRACK_HASHES,patcher=patch,archive='CHAR.DAT',
        preview_name='mode-readability-preview.png',texts=('Normal','Latent'),launcher='Mode Readability',version=VERSION,
        readme=('PRIVATE cumulative0.1.6: stronger Normal/Latent contrast on busy battle scenes.\n'
            'Same approved font/size/baseline/spacing/positions; solid native strokes and1px black outline.\n'
            'Selected white255; inactive gray180 remains distinct but more legible. No background box/glow.\n'
            'All4 whole sprites and4 separately drawn inactive halves updated, seams preserved.\n'
            'Only8 CHAR rectangles change. Move/Attack/Thinking, all other art/code and gameplay unchanged.\n'
            'ImageGen concept reference only; no generated pixels packed.\n'
            'All previous font/VGA/movie/subtitle/Whip/Remove/English fixes retained.\n'
            'Use Play - Disc 2 - Mode Readability.cmd or Disc1 after closing Flycast.\n'
            'Same original E: VMUs/frozen1440 launch-only settings; no save/card/config writes.\n'
            'Offline packed test-background preview/full binary checks; fresh in-game display/hardware pending.\n'
            'No actual emulator restart/launch/input during preparation.\n'
            'Separate oversized Equip and topic-list reports remain pending.\n'
            'Originals/earlier outputs preserved. Complete game binaries stay private/local on E:.\n'))


def launch(disc):b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.build:build()
    elif a.launch:launch(a.launch)
    else:plan()
