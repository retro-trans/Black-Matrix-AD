"""Inspect/edit raw square-twiddled 16-bit PVR atlases, preserving headers.

    python tools/pvr_atlas.py sheet extracted/GRAPHIC.DAT build/graphic-atlas.png
"""
import struct
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw


def textures(data):
    pos = 0
    while True:
        pos = data.find(b'PVRT', pos)
        if pos < 0:
            return
        if pos + 16 <= len(data):
            size, px, fmt, _, w, h = struct.unpack_from('<IBBHHH', data, pos + 4)
            if (px in (0, 1, 2) and fmt == 1 and w == h
                    and w in (32, 64, 128, 256, 512)
                    and size == 8 + w * h * 2 and pos + 8 + size <= len(data)):
                yield pos, px, w
        pos += 4


@lru_cache(maxsize=262144)
def pixel_index(x, y):
    # Dreamcast Morton order: y in even bits, x in odd bits.
    return sum(((y >> b) & 1) << (2*b) | ((x >> b) & 1) << (2*b+1)
               for b in range(9))


def decode(data, offset):
    px, fmt = data[offset + 8:offset + 10]
    w, h = struct.unpack_from('<HH', data, offset + 12)
    if fmt != 1 or w != h or px not in (0, 1, 2):
        raise ValueError('requires a raw square-twiddled 16-bit PVR')
    pixels = []
    for y in range(h):
        for x in range(w):
            v = struct.unpack_from('<H', data, offset + 16 + pixel_index(x,y)*2)[0]
            if px == 0:
                rgba = ((v>>10&31)*255//31, (v>>5&31)*255//31, (v&31)*255//31,
                        255 if v&0x8000 else 0)
            elif px == 1:
                rgba = ((v>>11&31)*255//31, (v>>5&63)*255//63, (v&31)*255//31,255)
            else:
                rgba = ((v>>8&15)*17, (v>>4&15)*17, (v&15)*17, (v>>12&15)*17)
            pixels.append(rgba)
    im = Image.new('RGBA', (w,h))
    im.putdata(pixels)
    return im


def scl_layout(data, offset):
    if data[offset:offset+4] != b'SCL ' or data[offset+8] != 16:
        raise ValueError('requires a 16-pixel SCL tilemap')
    rows, cols = data[offset+10:offset+12]
    descriptors = struct.unpack_from('<%dI' % (rows*cols), data, offset+32)
    count = max(d >> 16 for d in descriptors) + 1
    directory = offset + struct.unpack_from('<I', data, offset+20)[0] * 2
    if directory != offset + 32 + rows*cols*4:
        raise ValueError('unexpected SCL tile-directory position')
    atlases = []
    for i in range(count):
        base = offset + struct.unpack_from('<I', data, directory+i*4)[0]*2
        if data[base:base+4] != b'GBIX' or data[base+16:base+20] != b'PVRT':
            raise ValueError('unexpected SCL atlas header')
        if data[base+24:base+26] != b'\x01\x01':
            raise ValueError('SCL patch requires RGB565 square-twiddled textures')
        if struct.unpack_from('<HH', data, base+28) != (256,256):
            raise ValueError('SCL patch requires 256x256 atlases')
        atlases.append(base+16)
    return cols, rows, descriptors, atlases


def decode_scl(data, offset):
    cols, rows, descriptors, offsets = scl_layout(data, offset)
    atlases = [decode(data, off) for off in offsets]
    screen = Image.new('RGB', (cols*16, rows*16))
    for i,d in enumerate(descriptors):
        x,y,atlas = d>>8&255, d&255, d>>16
        if x%16 or y%16 or x>240 or y>240:
            raise ValueError('invalid SCL tile coordinate')
        screen.paste(atlases[atlas].crop((x,y,x+16,y+16)), ((i%cols)*16,(i//cols)*16))
    return screen


def encode_scl(data, offset, screen):
    """Re-tile RGB565 screen into its EXISTING atlases; never resize archives."""
    cols,rows,_,atlases = scl_layout(data,offset)
    if screen.size != (cols*16,rows*16):
        raise ValueError('replacement SCL dimensions changed')
    screen = screen.convert('RGB')
    unique = {}
    tiles = []
    mapping = []
    for y in range(rows):
        for x in range(cols):
            pixels = screen.crop((x*16,y*16,x*16+16,y*16+16)).getdata()
            words = tuple(((r*31+127)//255)<<11 | ((g*63+127)//255)<<5
                          | (b*31+127)//255 for r,g,b in pixels)
            if words not in unique:
                unique[words] = len(tiles)
                tiles.append(words)
            index = unique[words]
            atlas,local = divmod(index,256)
            tx,ty = (local//16)*16,(local%16)*16
            mapping.append(ty | tx<<8 | atlas<<16)
    if len(tiles)>len(atlases)*256:
        raise ValueError('translated SCL exceeds existing tile capacity')
    # Validation is complete before any output bytes are modified.
    struct.pack_into('<%dI'%len(mapping),data,offset+32,*mapping)
    for off in atlases:
        data[off+16:off+16+256*256*2] = bytes(256*256*2)
    for index,words in enumerate(tiles):
        atlas,local = divmod(index,256)
        tx,ty = (local//16)*16,(local%16)*16
        for y in range(16):
            for x in range(16):
                pos=atlases[atlas]+16+pixel_index(tx+x,ty+y)*2
                struct.pack_into('<H',data,pos,words[y*16+x])
    return len(tiles)


def sheet(source, output, start=0, count=None):
    data = Path(source).read_bytes()
    items = list(textures(data))[start:None if count is None else start+count]
    im = Image.new('RGB', (8*160, ((len(items)+7)//8)*180), '#252525')
    draw = ImageDraw.Draw(im)
    for i,(offset,px,w) in enumerate(items):
        tile = decode(data,offset).resize((152,152))
        x,y = (i%8)*160, (i//8)*180
        im.paste(tile,(x,y),tile)
        draw.text((x,y+154), '%d 0x%X'%(i+start,offset),fill='white')
    im.save(output)
    print('wrote %s (%d textures)'%(output,len(items)))


if __name__ == '__main__':
    if len(sys.argv) in (4,6) and sys.argv[1] == 'sheet':
        sheet(sys.argv[2],sys.argv[3],*[int(a) for a in sys.argv[4:]])
    else:
        raise SystemExit(__doc__)
