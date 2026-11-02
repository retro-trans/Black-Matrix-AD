"""Replace only SYSTEM sprite 6 (the translated vertical-attack V badge).

The checked-in SVG is the artwork source. Its tiny polygon-only subset is
rasterized at native/HD sizes with no platform font or external renderer.
Never replace the Latin V glyph, weapon icons, stance icons or descriptors.
"""
import hashlib
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))

from PIL import Image, ImageDraw
import config_load_ui
import pvr_atlas

ART = ROOT/'assets/ui/vertical-attack.svg'
PVX, TEXTURE, SPRITE = 0x21000, 0x21890, 6
RECT = (0,16,16,32)
HD_SIZE = 10  # Native-source pixels: 20x20 on the 640x480 display.
HD_Y = 1  # Match the adjacent compact weapon badge; keep clear of the next row.


def artwork(scale=4, art=None):
    if scale not in (1,4):
        raise ValueError('unsupported vertical icon scale')
    root = ET.fromstring((ART if art is None else art).read_text(encoding='utf-8'))
    if root.attrib != dict(width='16',height='16',viewBox='0 0 16 16'):
        raise ValueError('unexpected sword SVG viewport')
    # Supersample only edges; the native and HD versions share one outline.
    factor=scale*4
    image=Image.new('RGBA',(16*factor,16*factor))
    draw=ImageDraw.Draw(image)
    for element in root:
        kind=element.tag.rsplit('}',1)[-1]
        if kind=='title':continue
        if kind!='polygon' or set(element.attrib)!={'fill','points'}:
            raise ValueError('unsupported sword SVG element')
        points=[tuple(map(float,p.split(','))) for p in element.attrib['points'].split()]
        if any(len(p)!=2 or any(v<0 or v>16 for v in p) for p in points):
            raise ValueError('sword SVG exceeds original icon bounds')
        draw.polygon([(x*factor,y*factor) for x,y in points],fill=element.attrib['fill'])
    return image.resize((16*scale,16*scale),Image.Resampling.LANCZOS)


def sites():
    return [TEXTURE+16+2*pvr_atlas.pixel_index(x,y)
            for y in range(RECT[1],RECT[3]) for x in range(RECT[0],RECT[2])]


def hd_artwork():
    """Compact sword with a one-source-pixel downward inset in the shared slot.

    Do not change artwork()/native_badge(): their full-height native icon and
    resulting texture hash must remain stable. Uniform scaling preserves the
    sword's proportions. Horizontal centering and the original UV slot remain.
    """
    image=Image.new('RGBA',(64,64))
    size=HD_SIZE*4
    image.paste(artwork().resize((size,size),Image.Resampling.LANCZOS),
                ((64-size)//2,HD_Y*4))
    return image


def legacy_badge():
    data=bytearray((ROOT/'extracted/SYSTEM.DAT').read_bytes())
    config_load_ui.paint(data,TEXTURE,RECT,'V',config_load_ui.GOLD,condense=True)
    return b''.join(data[o:o+2] for o in sites())


def native_badge():
    low=artwork(4).resize((16,16),Image.Resampling.LANCZOS)
    words=[]
    for r,g,b,a in low.getdata():
        # Match the rest of the native ARGB1555 UI's alpha threshold.
        r,g,b=(c*a//255 for c in (r,g,b))
        word=0x8000|(r*31//255)<<10|(g*31//255)<<5|(b*31//255) if a>=64 else 0
        words.append(struct.pack('<H',word))
    return b''.join(words)


def validate_geometry(data):
    original=(ROOT/'extracted/SYSTEM.DAT').read_bytes()
    descriptor=PVX+48+SPRITE*16
    if (data[PVX:PVX+48]!=original[PVX:PVX+48] or
            data[TEXTURE:TEXTURE+16]!=original[TEXTURE:TEXTURE+16] or
            struct.unpack_from('<8H',data,descriptor)!=(16,16,*RECT,0,0)):
        raise ValueError('vertical-attack sprite geometry changed')


def patch_system(data):
    validate_geometry(data)
    original=(ROOT/'extracted/SYSTEM.DAT').read_bytes()
    current=b''.join(data[o:o+2] for o in sites())
    target=native_badge()
    if current not in (b''.join(original[o:o+2] for o in sites()),legacy_badge(),target):
        raise ValueError('unknown vertical-attack badge pixels')
    for i,o in enumerate(sites()):data[o:o+2]=target[2*i:2*i+2]
    return dict(sprite=SPRITE,uv=RECT,meaning='vertical attack',icon='upright gold sword',
                artwork=str(ART.relative_to(ROOT)),
                artwork_sha256=hashlib.sha256(ART.read_bytes()).hexdigest(),
                scope='one icon rectangle only; stats, weapon and stance unchanged')


def restore_legacy(data):
    """Reconstruct the authenticated old capture, not a downgrade installer."""
    validate_geometry(data)
    if b''.join(data[o:o+2] for o in sites())!=native_badge():
        raise ValueError('expected installed sword badge')
    previous=legacy_badge()
    for i,o in enumerate(sites()):data[o:o+2]=previous[2*i:2*i+2]


if __name__=='__main__':
    path=ROOT/'build/SYSTEM.vwf.dat'
    data=bytearray(path.read_bytes());patch_system(data);path.write_bytes(data)
    print('Replaced the vertical-attack V badge with an upright sword.')
