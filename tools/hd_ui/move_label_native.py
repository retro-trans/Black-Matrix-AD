"""Translate only the native battle Move badge; preserve cumulative0.1.3."""
import argparse
from functools import lru_cache

import numpy as np
from PIL import Image,ImageDraw

import whip_remove_font as prior
import battle_labels_native as lettering
import pvr_atlas
import japanese_audit

ROOT = prior.ROOT
b = prior.b
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-move-label-2026-11-02'
STATUS = 'private-native-move-label-runtime-pending'
VERSION = '0.1.4'
EXE_SHA = '387fd76fa34314d041ed426d46e272e1a1bbe411bb412e37ff5d73e4aa612fc3'
TRACK_HASHES = {1:'61af2a2d9a36393c56fc689028731fb6e9ec3eb89da8a96fd4de8d6bc56a4aca',
                2:'12d69e31de8916e7fad43f2c07a7d16afa5fe180f74c686139dcee55c2268102'}
CHAR_SHA = '14def48c0dbbb824ca1d0d2218008fbb2a42842bb0828051e15e4169cad9307d'
TEXTURE = 0x1350
INDEX = 160
RECT = (192,208,224,224)
REFERENCE = ROOT/'assets/ui/battle-labels/move-imagegen-reference-v1.png'


@lru_cache(maxsize=4)
def font_inputs(text='Move',source=None):
    source=SOURCE if source is None else source
    exe=(source/'1ST_READ.BIN').read_bytes()
    if b.sha(exe)!=EXE_SHA:raise ValueError('Unknown current executable')
    glyphs=lettering.optical.corrected_glyphs()[1]
    full=lettering.full
    for disc in (1,2):
        system=b.READER.read_file(b.track(source,disc),'SYSTEM.DAT')[0]
        if b.sha(system)!={1:'0c5c57bde9743cf813ea49673a4a8a4193f09a1ad874963484fcc622cb9b2ac5',
                          2:'08d139446320bf4f9368cf36f25f40e167a3a04df4fe391f65cc880038c4dc17'}[disc]:
            raise ValueError('Current font archive changed')
        forward=exe[full.prior.atlas.FORWARD-full.prior.atlas.BASE:full.prior.atlas.FORWARD-full.prior.atlas.BASE+256]
        pages=[full.decode_vq(system[full.prior.FONT_OFFSET+16+bank*128:full.prior.FONT_OFFSET+16+bank*128+8192]) for bank in full.BANKS]
        for ch in set(text):
            slot=forward[full.prior.latin.charmap()[ch]];x,y=slot%8*16,slot%32//8*32
            if pages[slot//32].crop((x,y,x+16,y+32)).tobytes()!=lettering.header.glyph(ch,glyphs).tobytes():
                raise ValueError('Current approved glyph differs: '+ch)
    return exe,glyphs


def artwork(before):
    exe,glyphs=font_inputs()
    mask=lettering.word_mask('Move',exe,glyphs)
    page=pvr_atlas.decode(before,TEXTURE)
    pixels=np.asarray(page.crop(RECT))
    peak=int(pixels[:,:,0][pixels[:,:,3]>0].max())
    level=round(peak*31/255);colour=(level*255+30)//31
    alpha=mask.resize((32,16),Image.Resampling.LANCZOS)
    maximum=alpha.getextrema()[1]
    if not maximum:raise ValueError('Blank Move caption')
    alpha=alpha.point(lambda a:round(a*255/maximum))
    art=Image.new('RGBA',(32,16),(colour,colour,colour,0));art.putalpha(alpha)
    return art


def preview(before,after):
    sheet=Image.new('RGB',(640,480),'#111715');d=ImageDraw.Draw(sheet)
    d.text((14,10),'Actual native packed labels - offline preview, not an in-game capture',fill='white')
    for row,(data,rect,title) in enumerate(((before,RECT,'Before'),(after,RECT,'Move'),
                                          (after,(192,224,224,240),'Attack (unchanged font reference)'))):
        tile=pvr_atlas.decode(data,TEXTURE).crop(rect).resize((192,96),Image.Resampling.NEAREST)
        sheet.paste(tile,(24,42+row*140),tile);d.text((240,80+row*140),title,fill='white')
    return sheet


def patch(before,disc):
    if disc not in (1,2) or b.sha(before)!=CHAR_SHA:raise ValueError('Unknown native CHAR source')
    rows=lettering.legacy.pack.descriptors(before,TEXTURE)
    if rows[INDEX]!=RECT:raise ValueError('Move sprite geometry differs')
    original=japanese_audit.archive(disc,'CHAR.DAT')
    if pvr_atlas.decode(before,TEXTURE).crop(RECT).tobytes()!=pvr_atlas.decode(original,TEXTURE).crop(RECT).tobytes():
        raise ValueError('Move is no longer the original Japanese badge')
    result=bytearray(before);allowed=set()
    for offset,value in lettering.legacy.native.encode(before,TEXTURE,RECT,artwork(before)):
        result[offset:offset+2]=value;allowed.update((offset,offset+1))
    delta=np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(result,'u1')).tolist()
    if not delta or not set(delta)<=allowed or len(before)!=len(result):raise ValueError('Out-of-badge edits')
    report=dict(disc=disc,label='Move',sprite=INDEX,texture=hex(TEXTURE),rectangle=RECT,
        source_char_sha256=CHAR_SHA,char_sha256=b.sha(result),changed_char_bytes=len(delta),
        font='Exact current approved Skies masks, same battle-label metrics as Attack',
        uniform_tracking=lettering.TRACKING,imagegen_role='Lettering review reference only; no generated pixels packed',
        all_headers_descriptors_and_other_pixels_unchanged=True)
    return bytes(result),delta,report,preview(before,result)


def plan():
    for disc in (1,2):
        before=b.READER.read_file(b.track(SOURCE,disc),'CHAR.DAT')[0]
        _,_,report,_=patch(before,disc)
        print(report,flush=True)


def build():
    b.build(out=OUT,source=SOURCE,status=STATUS,source_status=prior.STATUS,
        exe_sha=EXE_SHA,track_hashes=TRACK_HASHES,patcher=patch,archive='CHAR.DAT',
        preview_name='move-label-preview.png',texts=('Move',),launcher='Move Label',version=VERSION,
        readme=('PRIVATE cumulative0.1.4: pictured battle badge translated to Move.\n'
            'One32x16 sprite160 at CHAR texture1350; exact current approved font/Attack metrics.\n'
            'ImageGen supplied a lettering review reference only, not game pixels.\n'
            'Movement logic/range/AP, other labels, descriptors, code and font pixels unchanged.\n'
            'All0.1.3 Whip/Remove, movies, subtitles, English artwork and gameplay fixes retained.\n'
            'Use Play - Disc 2 - Move Label.cmd or Disc1 after closing Flycast.\n'
            'Same original E: VMUs; no save/card/config writes or emulator restart during preparation.\n'
            'Offline packed preview/full disc checks; fresh in-game appearance/hardware pending.\n'
            'Separate oversized Equip list and topic-list reports remain pending.\n'
            'Originals/earlier builds preserved; complete game binaries stay private/local on E:.\n'))


def launch(disc):b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.build:build()
    elif a.launch:launch(a.launch)
    else:plan()
