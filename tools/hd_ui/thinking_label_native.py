"""Native Thinking status indicator; cumulative0.1.5, no AI/turn changes."""
import argparse

import numpy as np
from PIL import Image,ImageDraw,ImageFilter

import move_label_native as prior
import pvr_atlas
import japanese_audit

ROOT = prior.ROOT
b = prior.b
SOURCE = prior.OUT
OUT = ROOT/'output/patched-discs-thinking-label-2026-11-02'
STATUS = 'private-native-thinking-label-runtime-pending'
VERSION = '0.1.5'
EXE_SHA = prior.EXE_SHA
TRACK_HASHES = {1:'f4b75ea6e4c76db810599b8665ada82cc953c2c46355ec852712f5d4863fc935',
                2:'749f691646aab432f3d3f809d663936efddc016d2b6ff3995c57c4239f5f93ac'}
CHAR_SHA = '269ea6a1630744c6420a1d131802a8beb88a133b5c762135110aafa45ac8b4f7'
TEXTURE = 0x1350
INDEX = 99
RECT = (144,80,184,96)
COLOUR = (180,49,16)
OUTLINE = (16,0,0)


def artwork():
    exe,glyphs=prior.font_inputs('Thinking',SOURCE)
    mask=prior.lettering.word_mask('Thinking',exe,glyphs,native_width=40)
    # Same font/size/baseline/tracking as Move/Attack; only the original badge
    # width differs. Native one-pixel dark outline retains the stock red cue.
    alpha=mask.resize((40,16),Image.Resampling.LANCZOS)
    maximum=alpha.getextrema()[1]
    if not maximum:raise ValueError('Blank Thinking indicator')
    alpha=alpha.point(lambda a:round(a*255/maximum))
    border=alpha.filter(ImageFilter.MaxFilter(3))
    inv=lambda c:(round(c*31/255)*255+30)//31
    art=Image.new('RGBA',(40,16),tuple(inv(c) for c in OUTLINE)+(0,));art.putalpha(border)
    ink=Image.new('RGBA',(40,16),tuple(inv(c) for c in COLOUR)+(0,));ink.putalpha(alpha)
    art=Image.alpha_composite(art,ink)
    # The native ARGB1555 encoder discards alpha<64; test the pixels that
    # are actually packed, not invisible Lanczos support outside the outline.
    box=art.getchannel('A').point(lambda a:255 if a>=64 else 0).getbbox()
    if not box or box[0]<1 or box[2]>39 or box[1]<0 or box[3]>15:
        raise ValueError('Thinking outline clips original badge')
    return art


def preview(before,after):
    sheet=Image.new('RGB',(640,480),'#111715');d=ImageDraw.Draw(sheet)
    d.text((14,10),'Actual native packed labels - offline preview, not an in-game capture',fill='white')
    for row,(data,rect,title) in enumerate(((before,RECT,'Before'),(after,RECT,'Thinking'),
                                          (after,prior.RECT,'Move (unchanged)'))):
        tile=pvr_atlas.decode(data,TEXTURE).crop(rect)
        tile=tile.resize((tile.width*6,96),Image.Resampling.NEAREST)
        sheet.paste(tile,(24,42+row*140),tile);d.text((290,80+row*140),title,fill='white')
    return sheet


def patch(before,disc):
    if disc not in (1,2) or b.sha(before)!=CHAR_SHA:raise ValueError('Unknown current CHAR source')
    rows=prior.lettering.legacy.pack.descriptors(before,TEXTURE)
    if rows[INDEX]!=RECT:raise ValueError('Thinking sprite geometry differs')
    old=pvr_atlas.decode(japanese_audit.archive(disc,'CHAR.DAT'),TEXTURE).crop(RECT)
    page=pvr_atlas.decode(before,TEXTURE)
    if page.crop(RECT).tobytes()!=old.tobytes():raise ValueError('Thinking is not the original Japanese sprite')
    original_colours={tuple(p) for p in np.asarray(old).reshape(-1,4) if p[3]}
    if COLOUR+(255,) not in original_colours or OUTLINE+(255,) not in original_colours:
        raise ValueError('Original red/outline palette changed')
    result=bytearray(before);allowed=set()
    for offset,value in prior.lettering.legacy.native.encode(before,TEXTURE,RECT,artwork()):
        result[offset:offset+2]=value;allowed.update((offset,offset+1))
    delta=np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(result,'u1')).tolist()
    if not delta or not set(delta)<=allowed or len(before)!=len(result):raise ValueError('Out-of-indicator edit')
    report=dict(disc=disc,label='Thinking',sprite=INDEX,texture=hex(TEXTURE),rectangle=RECT,
        source_char_sha256=CHAR_SHA,char_sha256=b.sha(result),changed_char_bytes=len(delta),
        font='Exact current approved Skies masks, same Move/Attack metrics and baseline',
        colour=COLOUR,outline=OUTLINE,uniform_tracking=prior.lettering.TRACKING,
        imagegen_role='Lettering review reference only; no generated pixels packed',
        all_headers_descriptors_and_other_pixels_unchanged=True,ai_and_turn_logic_unchanged=True)
    return bytes(result),delta,report,preview(before,result)


def plan():
    for disc in (1,2):
        source=b.READER.read_file(b.track(SOURCE,disc),'CHAR.DAT')[0]
        print(patch(source,disc)[2],flush=True)


def build():
    b.build(out=OUT,source=SOURCE,status=STATUS,source_status=prior.STATUS,
        exe_sha=EXE_SHA,track_hashes=TRACK_HASHES,patcher=patch,archive='CHAR.DAT',
        preview_name='thinking-label-preview.png',texts=('Thinking',),launcher='Thinking Label',version=VERSION,
        readme=('PRIVATE cumulative0.1.5: enemy-turn indicator translated to Thinking.\n'
            'One40x16 sprite99 at CHAR texture1350; exact Move/Attack font masks and baseline.\n'
            'Original red-orange peak colour and dark outline retained.\n'
            'ImageGen lettering reference only; no generated pixels imported into game.\n'
            'AI/turn/movement/AP/range/combat logic, other labels, descriptors and code unchanged.\n'
            'All0.1.4 Move, Whip/Remove, movies, subtitles and English artwork/fixes retained.\n'
            'Use Play - Disc 2 - Thinking Label.cmd or Disc1 after closing Flycast.\n'
            'Same original E: VMUs, frozen1440 launch-only settings; no save/card/config writes.\n'
            'No real emulator launch, restart or input during preparation.\n'
            'Offline packed preview/full disc checks; fresh display/hardware pending.\n'
            'Separate oversized Equip and topic-list reports remain pending.\n'
            'Originals/earlier builds preserved; complete binaries stay private/local on E:.\n'))


def launch(disc):b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.build:build()
    elif a.launch:launch(a.launch)
    else:plan()
