"""Source-bound in-game translations for the seven reported activity screens.

Native EVENT resources and HD atlases share one layout. Never modify game
logic, AP costs, item attributes, archive extents, or sprite descriptors.
"""
import hashlib
import struct
import sys
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/hd_ui'))
import all_title_cards as cards
import pvr_atlas
import patchline

SOURCES = {
    'fishing': (0x73C000, 0x77C9E0, '2235f220e290bc22370ed219c9d6e7bccb07a8f7afa8a2d31bab4d5729d29b51'),
    'next_day': (0x2BB0800, 0x2BD11C0, '026aa9aed4bf96a8bc3d0e0b70e7cd41f1818c5509a4025bc22b450080a8eafa'),
    'week_later': (0x2BD1800, 0x2BF21C0, '6876bb01b6d366f5c1c03e61d85562869bfdad9bac2d720af84e981b6475315e'),
}
NAMES = {
    0xE3210: ('おせんべい', 'Crackers'),
    0xE3230: ('おせんべい', 'Crackers'),
    0xE3250: ('おせんべい', 'Crackers'),
    0xE3510: ('毛虫', 'Caterplr'),
    0xE3850: ('まき', 'Firewood'),
    0xE3890: ('キャベツ', 'Cabbage'),
}
FISHING = [
    ('1. Wait for a fish to bite.', 150),
    ('2. When a fish bites, press A to stop the cursor.', 170),
    ('3. When the prompt appears, tap A rapidly to reel it in.', 190),
    ('Your catch depends on where you stop the cursor.', 212),
]
FISHING_RECTS = [(70,8,610,54),(359,63,635,140),(20,146,635,225)]


def digest(data):
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def original():
    path=ROOT/'extracted/EVENT.DAT'
    data=path.read_bytes() if path.exists() else cards.source(1,'EVENT')
    if digest(data)!='7f13b1db6ae11cec47745e39c6fb40ea674bcfc5fa34c0b068f88c00c3ef09af':
        raise ValueError('Unknown original Disc 1 EVENT archive')
    return data


def name_payload(text):
    if not text or len(text) > 8:
        raise ValueError('Activity item name must fit its eight reserved cells')
    words = [patchline.to_sjis(c) if ord(c)<128 else int.from_bytes(c.encode('cp932'),'big') for c in text.ljust(8)]
    return struct.pack('<9H', len(text), *words)


def text(high, word, xy, size, width, color='white', bold=False, center=False):
    face = ImageFont.truetype('C:/Windows/Fonts/verdanab.ttf' if bold else 'C:/Windows/Fonts/verdana.ttf', round(size*4))
    box = face.getbbox(word)
    layer = Image.new('RGBA', (box[2]-box[0]+8, box[3]-box[1]+8))
    ImageDraw.Draw(layer).text((4-box[0],4-box[1]), word, font=face, fill=color)
    layer = layer.resize((round(layer.width*1.8), layer.height), Image.Resampling.LANCZOS)
    if layer.width > width*4:
        raise ValueError('Activity caption too wide: '+word)
    x,y = (round(v*4) for v in xy)
    if center:
        x -= layer.width//2
    high.alpha_composite(layer, (x,y))


@lru_cache(maxsize=3)
def render(key):
    o,end,sha = SOURCES[key]
    source = original()
    if digest(source[o:end]) != sha:
        raise ValueError('Activity source changed: '+key)
    native = pvr_atlas.decode_scl(source,o)
    high = native.resize((2560,960),Image.Resampling.NEAREST).convert('RGBA')
    draw=ImageDraw.Draw(high)
    if key == 'fishing':
        # Preserve the entire controller, buttons and the green connector lines.
        for rect in FISHING_RECTS:
            x,y,xx,yy=(v*4 for v in rect)
            draw.rectangle((x,y,xx-1,yy-1),fill='black')
        text(high,'Fishing',(200,17),25,260,'#6595ff',True,True)
        text(high,'Controls',(432,24),17,200,bold=True,center=True)
        for word,y,color in [('Not used',68,'#ac3824'),('Not used',87,'#ac3824'),
                             ('Pull the rod',105,'white'),('Not used',124,'#ac3824')]:
            text(high,word,(367,y),12,260,color)
        for word,y in FISHING:
            text(high,word,(29,y),10.5,600)
    else:
        high = Image.new('RGBA',(2560,960),'black')
        word = 'The Next Day' if key=='next_day' else 'One Week Later'
        # Existing title-card caption rendering already compensates the game's
        # 640x240 -> 640x480 geometry, retaining natural serif letter shapes.
        cards.caption(high,word,(35,91,605,149),58,'#dedede',max_lines=1)
    low = high.convert('RGB').resize((640,240),Image.Resampling.LANCZOS)
    if key=='fishing':
        # Keep pixels outside text rectangles byte-exact (avoid resampling art).
        clean = native.copy()
        for rect in FISHING_RECTS:
            clean.paste(low.crop(rect),rect[:2])
        low=clean
    return low,high


def allowed_ranges():
    spans = [(o,o+18) for o in NAMES]
    for o,_,_ in SOURCES.values():
        cols,rows,_,pages=pvr_atlas.scl_layout(original(),o)
        spans += [(o+32,o+32+cols*rows*4)] + [(a+16,a+16+131072) for a in pages]
    return sorted(spans)


def verify_outside(before,after):
    if len(before)!=len(after):
        raise ValueError('Activity archive extent changed')
    last=0
    for lo,hi in allowed_ranges():
        if before[last:lo]!=after[last:lo]:
            raise ValueError('Change outside activity resource ranges')
        last=hi
    if before[last:]!=after[last:]:
        raise ValueError('Change after activity resource ranges')


def patch(data, previews=None):
    source=original()
    if len(data)!=len(source):
        raise ValueError('Expected the Disc 1 EVENT archive')
    before=bytes(data)
    pending=[];details=[]
    for o,(japanese,english) in NAMES.items():
        expected=name_payload(japanese)
        if source[o:o+18]!=expected:
            raise ValueError('Unexpected original activity item name')
        target=name_payload(english)
        if data[o:o+18] not in (expected,target):
            raise ValueError('Unknown translated item name')
        pending.append((o,o+18,target))
    for key,(o,end,_) in SOURCES.items():
        low,high=render(key)
        candidate=bytearray(source)
        count=cards.retile(candidate,{'offset':o},low,high)
        if data[o:end] not in (source[o:end],candidate[o:end]):
            raise ValueError('Unknown installed activity card: '+key)
        pending.append((o,end,candidate[o:end]))
        details.append(dict(key=key,offset=o,tiles=count,capacity=len(pvr_atlas.scl_layout(source,o)[3])*256))
    for lo,hi,payload in pending:
        data[lo:hi]=payload
    verify_outside(before,data)
    if previews:
        previews=Path(previews);previews.mkdir(parents=True,exist_ok=True)
        for key,(o,_,_) in SOURCES.items():
            pvr_atlas.decode_scl(data,o).resize((1280,960),Image.Resampling.NEAREST).save(previews/(key+'-native.png'))
            render(key)[1].resize((1280,960),Image.Resampling.LANCZOS).save(previews/(key+'-hd.png'))
    return dict(items={hex(o):name for o,(_,name) in NAMES.items()},cards=details)


def hd_pages(patched):
    import xxhash
    for key,(o,_,_) in SOURCES.items():
        _,high=render(key)
        cols,rows,descriptors,pages=pvr_atlas.scl_layout(patched,o)
        sheets=[Image.new('RGBA',(1024,1024),'black') for _ in pages]
        seen={}
        for i,d in enumerate(descriptors):
            tile=high.crop((i%cols*64,i//cols*64,(i%cols+1)*64,(i//cols+1)*64))
            if d in seen and seen[d]!=tile.tobytes():
                raise ValueError('HD activity tile collision')
            seen[d]=tile.tobytes()
            sheets[d>>16].paste(tile,((d>>8&255)*4,(d&255)*4))
        for a,image in zip(pages,sheets):
            name='%x.png'%(xxhash.xxh32(patched[a+16:a+16+131072],seed=7).intdigest()^cards.SALT)
            yield name,image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
