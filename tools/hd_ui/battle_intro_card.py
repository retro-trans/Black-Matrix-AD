"""Translate one RGB565 SCL battle card, preserving its four text-area bounds.

MAP.DAT, not EVENT or a movie. Native and HD text use the same deterministic
caption rendering. Original game-derived art remains only in ignored build/.
"""
import hashlib
import struct

import xxhash
from PIL import Image, ImageDraw, ImageFont
import cooking
import pvr_atlas
import seed_noto_pack

ROOT = cooking.ROOT
UI = ROOT/'script/ui/battle_intro.tsv'
SCL, END = 0x1E9C840, 0x1EFD240
SOURCE_HASH = 'ec57b3a7734cd1730fbaa14b142e1548eb53a3fa5da8efdc335ac7b24dc7a515'
CAPTURES = ('e569a8d7.png','de576a17.png','e0712e45.png')
# Same bold serif face used by the existing chapter-card renderer.
FONT = 'C:/Windows/Fonts/georgiab.ttf'
SCALE = 4
PANELS = (((28,22,330,64),'chapter',38),
          ((160,68,474,124),'title',64),
          ((20,122,275,167),'condition',25),
          ((176,172,618,226),'objective',38))


def authenticate(original):
    if hashlib.sha256(original[SCL:END]).hexdigest()!=SOURCE_HASH:
        raise ValueError('unknown Chapter 2-1 source card')
    cols,rows,_,pages=pvr_atlas.scl_layout(original,SCL)
    if (cols,rows,len(pages))!=(40,15,3) or pages[-1]+16+131072!=END:
        raise ValueError('battle-card allocation changed')
    return pages


def render(original):
    authenticate(original)
    source=pvr_atlas.decode_scl(original,SCL)
    high=source.resize((640*SCALE,240*SCALE),Image.Resampling.NEAREST).convert('RGBA')
    # This lower-left patch is plain paper, below the original lettering.
    paper=source.crop((0,168,160,240))
    draw=ImageDraw.Draw(high);text=cooking.strings(UI)
    for rect,key,size in PANELS:
        x,y,xx,yy=(v*SCALE for v in rect)
        backing=paper.resize((rect[2]-rect[0],rect[3]-rect[1]),Image.Resampling.BICUBIC)
        high.paste(backing.resize((xx-x,yy-y),Image.Resampling.NEAREST),(x,y))
        draw.rectangle((x,y,xx-1,yy-1),outline='#414141',width=SCALE)
        face=ImageFont.truetype(FONT,size*SCALE)
        box=face.getbbox(text[key]);width=box[2]-box[0]+8;height=box[3]-box[1]+8
        layer=Image.new('RGBA',(width,height))
        ImageDraw.Draw(layer).text((4-box[0],4-box[1]),text[key],font=face,fill='#151515')
        # The game displays native 640x240 as 640x480: halve only native Y.
        fit=min(1,(xx-x-24*SCALE)/width)
        layer=layer.resize((round(width*fit),max(1,round(height*fit/2))),Image.Resampling.LANCZOS)
        if layer.width>xx-x-8*SCALE or layer.height>yy-y-8*SCALE:
            raise ValueError('battle-card caption does not fit')
        high.alpha_composite(layer,(x+(xx-x-layer.width)//2,y+(yy-y-layer.height)//2))
    # Preserve all source pixels outside the caption rectangles exactly.
    low=source.copy()
    for rect,_,_ in PANELS:
        crop=high.crop(tuple(v*SCALE for v in rect)).convert('RGB')
        low.paste(crop.resize((rect[2]-rect[0],rect[3]-rect[1]),Image.Resampling.LANCZOS),rect[:2])
    return low,high


def patch(data,original):
    pages=authenticate(original);low,high=render(original)
    expected=bytearray(original)
    tiles=pvr_atlas.encode_scl(expected,SCL,low)
    if data[SCL:END] not in (original[SCL:END],expected[SCL:END]):
        raise ValueError('unknown existing battle-card bytes')
    data[SCL:END]=expected[SCL:END]
    return dict(card='Chapter 2-1: Escape',labels=cooking.strings(UI),scl=SCL,
                tiles=tiles,capacity=len(pages)*256,
                scope='one SCL tilemap and its three atlas payloads; other maps unchanged')


def indices(image):
    return bytes(v for r,g,b in image.convert('RGB').getdata() for v in (r>>3,g>>2,b>>3))


def prepare_pack(original,patched,dumps):
    pages=authenticate(original);salts=set()
    for o,name in zip(pages,CAPTURES):
        with Image.open(dumps/name) as image:
            actual=image.convert('RGBA')
            decoded=pvr_atlas.decode(original,o).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if actual.size!=(256,256) or actual.getchannel('A').getextrema()!=(255,255) or indices(actual)!=indices(decoded):
                raise ValueError('battle-card capture pixels do not match original')
        salts.add(int(name[:-4],16)^xxhash.xxh32(original[o+16:o+16+131072],seed=7).intdigest())
    if salts!={0x08000000}:
        raise ValueError('RGB565 battle-card hash format disagrees across captures')
    expected=bytearray(original);patch(expected,original)
    if expected[SCL:END]!=patched[SCL:END]:raise ValueError('unexpected patched battle-card layout')
    _,high=render(original)
    cols,rows,descriptors,target_pages=pvr_atlas.scl_layout(patched,SCL)
    sheets=[Image.new('RGBA',(1024,1024),(0,0,0,255)) for _ in target_pages]
    seen={}
    for i,descriptor in enumerate(descriptors):
        x,y,page=descriptor>>8&255,descriptor&255,descriptor>>16
        sx,sy=(i%cols)*64,(i//cols)*64
        tile=high.crop((sx,sy,sx+64,sy+64))
        if descriptor in seen and seen[descriptor]!=tile.tobytes():
            raise ValueError('native tile deduplication merged different HD artwork')
        seen[descriptor]=tile.tobytes();sheets[page].paste(tile,(x*SCALE,y*SCALE))
    return [(im.transpose(Image.Transpose.FLIP_TOP_BOTTOM),dict(texture='%x.png'%(
                xxhash.xxh32(patched[o+16:o+16+131072],seed=7).intdigest()^0x08000000)))
            for im,o in zip(sheets,target_pages)]


def install_pack(original,patched):
    profile=ROOT/'build/stock-atlas-run/data'
    dumps=profile/'texdump/T20101M'
    missing=[name for name in CAPTURES if not (dumps/name).exists()]
    if missing:return dict(status='pending verified battle-card captures',missing=missing)
    pending=prepare_pack(original,patched,dumps)
    seed_noto_pack.write_pack(profile/'textures/T20101M',pending)
    low,high=render(original)
    output=ROOT/'build/hd-ui';output.mkdir(exist_ok=True)
    low.resize((640,480),Image.Resampling.NEAREST).save(output/'escape-card-native.png')
    high.resize((1280,960),Image.Resampling.LANCZOS).save(output/'escape-card-hd.png')
    return dict(textures=[meta['texture'] for _,meta in pending],scale=SCALE,
                source_captures=list(CAPTURES),format_salt=0x08000000,
                verification='three source captures pixel/hash verified; in-game restart check pending')
