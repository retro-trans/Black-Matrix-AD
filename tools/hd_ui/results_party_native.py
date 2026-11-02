"""Cumulative native results/party image labels; no code or reward edits."""
import argparse
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image,ImageDraw,ImageFont

import battle_labels_native as prior

ROOT = prior.ROOT
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-results-party-2026-11-02'
STATUS = 'private-results-party-labels-runtime-pending'
VERSION = '0.1.1'  # Private cumulative artwork revision; no public release.
EXE_SHA = prior.EXE_SHA
TRACK_HASHES = {1:'d7ec13d4b90bec6e93a5ca8988029401897ba3eb95c3e6909cc9674aa33d3f0d',
                2:'d98e4c1f1d7ccfb6a89dae1a8fe635b00134f0a135bc6af05cac6a0c8d2d0733'}
PARAMETA_SHA = '678d0d53e37fdef5bcef3277e74cc2421c726968a517d592a092c7dd1cab82dd'
SYSTEM_HASHES = {1:'5bd23b182fafb6f91e884509d0c6ffe0bfa0436764a1301d511685825d7ab8a6',
                 2:'8ee6db2a8f5044ed87b15f62dd8abd1cabb5ac709410cbba6340bcdfcb5edad2'}
RESULT_TEXTURE = 0x1bfdd0
FOOTER_TEXTURE = 0x21890
RESULTS = {7:('Carryover:',(0,112,120,128)),
           10:('Command Time:',(0,160,160,176)),
           11:('Turns:',(0,176,112,192))}
FOOTERS = {50:('Level Up',(0,96,56,112)),
           67:('Join',(64,192,96,208)),
           68:('Remove',(64,208,112,224))}
SERIF = Path('C:/Windows/Fonts/georgiab.ttf')
SERIF_SHA = '72a6cd94fab6c179392075d3fb361e269cdddfad41bb7ab385fa22a37e49a900'
RESULT_EM = 15
RESULT_BASELINE = 47  # Shared 4x-native baseline, including Carryover's y tail.
GOLD = (255,184,40)


@lru_cache(maxsize=1)
def current_font():
    # Validate against THIS cumulative pair, not merely the older loose sources.
    exe,glyphs = prior.font_inputs([t for t,_ in FOOTERS.values()])
    for disc in (1,2):
        if prior.builder.READER.read_file(prior.builder.track(SOURCE,disc),'1ST_READ.BIN')[0] != exe:
            raise ValueError('Current font executable differs across revisions')
    return exe,glyphs


def result_art(text,width):
    if prior.builder.sha(SERIF.read_bytes()) != SERIF_SHA:
        raise ValueError('Results face changed')
    face = ImageFont.truetype(str(SERIF),RESULT_EM*4)
    mask = Image.new('L',(width*4,64))
    ImageDraw.Draw(mask).text((6,RESULT_BASELINE),text,font=face,anchor='ls',fill=255,
                             stroke_width=1,stroke_fill=255)
    box = mask.getbbox()
    if not box or box[0]<4 or box[2]>width*4-4 or box[3]>61 or box[1]<1:
        raise ValueError('Fixed result font does not fit '+text)
    # Native UI is doubled vertically by the scanout, as are adjacent stock
    # result labels. Keep one common face/em/baseline; never fit word-by-word.
    alpha = mask.resize((width,16),Image.Resampling.LANCZOS)
    art = Image.new('RGBA',(width,16),GOLD+(0,));art.putalpha(alpha)
    return art


def footer_art(text,width):
    exe,glyphs = current_font()
    art,_ = prior.font.caption(text,width,glyphs,exe)
    # Resample alpha alone, keeping constant gold out of RGBA ringing.
    alpha = art.getchannel('A').resize((width,16),Image.Resampling.LANCZOS)
    peak = alpha.getextrema()[1]
    if not peak:raise ValueError('Blank footer')
    alpha = alpha.point(lambda a:round(a*255/peak))
    result = Image.new('RGBA',(width,16),GOLD+(0,));result.putalpha(alpha)
    return result


def patch_archive(before,disc,name,texture,labels,expected,render):
    if disc not in (1,2) or prior.builder.sha(before) != expected:
        raise ValueError('Unknown per-disc '+name+' source')
    rows = prior.legacy.pack.descriptors(before,texture)
    original = prior.legacy.ui.japanese_audit.archive(disc,name)
    oldpage = prior.pvr_atlas.decode(original,texture)
    page = prior.pvr_atlas.decode(before,texture)
    result = bytearray(before);allowed = set()
    for index,(text,rect) in labels.items():
        if rows[index] != rect or page.crop(rect).tobytes() != oldpage.crop(rect).tobytes():
            raise ValueError('Expected original Japanese sprite '+str(index))
        art = render(text,rect[2]-rect[0])
        for offset,word in prior.legacy.native.encode(before,texture,rect,art):
            result[offset:offset+2] = word;allowed.update((offset,offset+1))
    delta = np.flatnonzero(np.frombuffer(before,'u1') != np.frombuffer(result,'u1')).tolist()
    if not delta or not set(delta)<=allowed or len(before)!=len(result):
        raise ValueError('Out-of-sprite changes')
    report = dict(disc=disc,archive=name,texture=hex(texture),labels={i:t for i,(t,_) in labels.items()},
        rectangles={i:r for i,(_,r) in labels.items()},changed_bytes=len(delta),
        source_sha256=prior.builder.sha(before),sha256=prior.builder.sha(result),
        headers_geometry_font_cells_and_other_pixels_unchanged=True)
    return bytes(result),delta,report


def patch_system(before,disc):
    if disc not in SYSTEM_HASHES:raise ValueError('Unknown disc')
    after,delta,report = patch_archive(before,disc,'SYSTEM.DAT',FOOTER_TEXTURE,FOOTERS,
                                     SYSTEM_HASHES[disc],footer_art)
    return after,delta,report,None


def preview(parameta,system):
    sheet = Image.new('RGB',(640,480),'#11100b');draw = ImageDraw.Draw(sheet)
    draw.text((12,8),'Packed native labels - preview, not an in-game screenshot',fill='white')
    for row,(index,(text,rect)) in enumerate(RESULTS.items()):
        crop = prior.pvr_atlas.decode(parameta,RESULT_TEXTURE).crop(rect)
        # 2x X / 4x Y reproduces existing result sprite's scanout proportions.
        crop = crop.resize((crop.width*2,64),Image.Resampling.NEAREST)
        sheet.paste(crop,(16,30+row*80),crop)
    page = prior.pvr_atlas.decode(system,FOOTER_TEXTURE)
    for row,(index,(text,rect)) in enumerate(FOOTERS.items()):
        crop = page.crop(rect).resize(((rect[2]-rect[0])*4,64),Image.Resampling.NEAREST)
        sheet.paste(crop,(16,290+row*60),crop)
    return sheet


def patch_parameta(before,disc):
    after,delta,report = patch_archive(before,disc,'PARAMETA.DAT',RESULT_TEXTURE,RESULTS,
                                     PARAMETA_SHA,result_art)
    system = prior.builder.READER.read_file(prior.builder.track(SOURCE,disc),'SYSTEM.DAT')[0]
    system = patch_system(system,disc)[0]
    return after,delta,report,preview(after,system)


def build():
    prior.builder.build(out=OUT,source=SOURCE,status=STATUS,source_status=prior.STATUS,
        exe_sha=EXE_SHA,track_hashes=TRACK_HASHES,
        patches={'PARAMETA.DAT':patch_parameta,'SYSTEM.DAT':patch_system},
        preview_name='results-party-preview.png',
        texts=tuple(t for t,_ in [*RESULTS.values(),*FOOTERS.values()]),
        launcher='Results and Party',version=VERSION,
        readme=('PRIVATE cumulative artwork build0.1.1: results and party labels.\n'
            'Carryover: / Command Time: / Turns: / Level Up / Join / Remove.\n'
            'Only6 native sprite rectangles change, in PARAMETA and SYSTEM, on both discs.\n'
            'Fixed gold serif results typography; exact current approved footer font masks.\n'
            'No code, rewards, counters, item names, stats, ranks, combat or input changes.\n'
            'Normal/Latent/Attack and all previous cumulative fixes retained.\n'
            'Native preview is actual packed readback, not an in-game screenshot.\n'
            'ImageGen supplied a lettering reference only; no generated scene pixels imported.\n'
            'Use project Play - Disc 2 - Results and Party.cmd (or Disc1) after closing Flycast.\n'
            'Uses SAME original E: save profile; latest old saves on Port A Slot2.\n'
            'No save/config writes or automatic restart. In-game display and hardware pending.\n'
            'Originals/previous builds unchanged; complete binaries stay local/private on E:.\n'))


def launch(disc):
    prior.builder.domina.zero.launch(disc,build=OUT,status=STATUS,settings=prior.builder.renderer_settings())


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--launch',type=int,choices=(1,2))
    args = parser.parse_args()
    if args.build:build()
    if args.launch:launch(args.launch)
