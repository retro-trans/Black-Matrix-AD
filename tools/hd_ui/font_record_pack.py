"""Seed known English record textures from pixel-verified stock captures.

Verify six original Japanese 32px sheets AND three canonical 128px sheets
agree on the indexed-texture hash salt before deriving new record hashes.
This covers the seeded Magic/battle labels when canonical admission is declined.
"""
import hashlib
import json
from pathlib import Path
import math

import xxhash
from PIL import Image
import noto_font
import fallback_font_pack
import stock_atlas_pack as pack
import seed_noto_pack
import bizin_font
import font_style
import magic_menu
import battle_system_ui
import equipment_menu
import equipment_confirm
import status_heading
import config_help
import inventory_menu
import config_load_ui
import party_names
import field_battle_ui
import formation_menu
import battle_loot
import remaining_parameters
import remaining_messages
import pickup_messages

ROOT = noto_font.ROOT
PROFILE = ROOT/'build/stock-atlas-run/data'
CAPTURES = {'b4c95735.png':'魔法', '77749bcb.png':'は使', 'be295743.png':'えま',
            'c18b56d0.png':'せん', '556f2b23.png':'射程', '2ea49f41.png':'範囲'}


def capacities(count):
    if not 1 <= count <= 192:
        raise ValueError('record count outside native allocator range')
    levels = (128,32,8,2,0); parts = []; index = 0
    while count:
        size = levels[index]
        if count > size:
            parts.append(size); count -= size
        elif count > levels[index+1]*(4-len(parts)):
            parts.append(size); break
        else:
            index += 1
    return parts


def indexed_cell(data, index):
    result = Image.new('L',(32,16))
    result.putdata([noto_font.fontdump.pixel(data,0,index,x,y)
                    for y in range(16) for x in range(32)])
    return result


def twiddled(indexed):
    w,h = indexed.size
    if w != h or w not in (32,64,128,256):
        raise ValueError('unexpected native font texture size')
    raw = bytearray(w*h//2)
    for y in range(h):
        for x in range(w):
            value = indexed.getpixel((x,y))
            if not 0 <= value <= 3:
                raise ValueError('expected original 2bpp glyph indices')
            offset = sum(((y>>b)&1)<<(2*b)|((x>>b)&1)<<(2*b+1) for b in range(w.bit_length()-1))
            raw[offset//2] |= value << (4*(offset%2))
    return bytes(raw)


def capture_palette(dump, indexed):
    if dump.size != indexed.size:
        raise ValueError('font capture dimensions changed')
    pixels = dump.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    palette = {}
    for y in range(indexed.height):
        for x in range(indexed.width):
            index = indexed.getpixel((x,y)); color = pixels.getpixel((x,y))
            if index in palette and palette[index] != color:
                raise ValueError('font capture has unknown pixels')
            palette[index] = color
    if len(palette) != 4 or palette[0][3] != 0 or palette[1][3] != 255:
        raise ValueError('unexpected original font palette')
    return palette


def verified_palette(dumps):
    native = noto_font.NATIVE.read_bytes(); salts = set(); palettes = set(); sources = []
    for name, text in CAPTURES.items():
        low = Image.new('L',(32,32))
        for i,ch in enumerate(text):
            index = noto_font.latin.sjis_to_index(int.from_bytes(ch.encode('cp932'),'big'))
            low.paste(indexed_cell(native,index),(0,i*16))
        with Image.open(dumps/name) as image:
            palette = capture_palette(image,low)
            sources.append(dict(texture=name,rgba_sha256=hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest()))
        palettes.add(tuple(palette[i] for i in range(4)))
        salts.add(int(Path(name).stem,16)^xxhash.xxh32(twiddled(low),seed=7).intdigest())
    old = pack.sheets(bizin_font.NATIVE,font_style.default_font())
    new = pack.sheets(noto_font.NATIVE,noto_font.default_font(),renderer=noto_font)
    parts = lambda sheets: {i:(lo,hi) for i,lo,hi in pack.segments(*sheets)}
    canonical = seed_noto_pack.prepare(dumps,parts(old),parts(new))
    salts.update(meta['palette_format_salt'] for _,meta in canonical)
    if len(salts) != 1 or len(palettes) != 1:
        raise ValueError('32px and 128px font captures disagree on palette/hash layout')
    palette = next(iter(palettes))
    # New Noto cells use palette entry one, exactly like canonical English.
    color = canonical[0][0].getpixel((0,0))[:3]
    if palette[1][:3] != color:
        raise ValueError('canonical and native text colors disagree')
    return next(iter(salts)),palette[1],sources


def record_parts(text):
    native = noto_font.NATIVE.read_bytes(); start = 0
    chars = {' ':0,**noto_font.latin.charmap()}; face = noto_font.outline()
    for capacity in capacities(len(text)):
        size = math.isqrt(capacity*512)
        low = Image.new('L',(size,size)); high = Image.new('L',(size*4,size*4))
        for i,ch in enumerate(text[start:start+capacity]):
            if ch not in chars:
                raise ValueError('record seed requires mapped English only')
            x,y = pack.cell(i)
            low.paste(indexed_cell(native,chars[ch]),(x,y))
            high.paste(noto_font.glyph(ch,face),(x*4,y*4))
        start += capacity
        if high.getbbox() is not None:
            yield low,high


def install():
    dumps = PROFILE/'texdump/T20101M'
    required = set(CAPTURES)|set(seed_noto_pack.CAPTURES.values())
    missing = sorted(name for name in required if not (dumps/name).exists())
    if missing:
        return dict(status='pending verified source captures',missing=missing)
    fallback_font_pack.dictionary()  # Fail before writes if native metrics are stale.
    salt,color,sources = verified_palette(dumps)
    text = magic_menu.strings()
    records = [text['heading'],text['unavailable'],
               text['range'].ljust(5)+' '*5+text['area'].ljust(5)]
    records += battle_system_ui.records()
    records += [equipment_menu.strings()['heading']]
    records += equipment_confirm.records()
    records += [status_heading.text()]
    records += config_help.records()
    records += inventory_menu.records()
    records += inventory_menu.help_records()
    records += party_names.records()
    records += field_battle_ui.item_records()
    records += formation_menu.records()
    records += battle_loot.records()
    records += remaining_parameters.records()
    records += remaining_messages.records()
    records += pickup_messages.records()
    records += [config_load_ui.cooking.strings(config_load_ui.UI)['show_again'].ljust(16)]
    pending = {}; metadata = []
    for text in records:
        for low,high in record_parts(text):
            name = '%x.png' % (xxhash.xxh32(twiddled(low),seed=7).intdigest()^salt)
            image = Image.new('RGBA',high.size,color[:3]+(0,)); image.putalpha(high)
            image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if name in pending and pending[name].tobytes() != image.tobytes():
                raise ValueError('seeded native texture hash collision')
            pending[name] = image
            metadata.append(dict(record=text,texture=name,native_size=list(low.size),hd_size=list(high.size)))
    target = PROFILE/'textures/T20101M'
    seed_noto_pack.write_pack(target,[(im,dict(texture=name)) for name,im in pending.items()])
    noto_font.copy_license(target)
    result = dict(font_sha256=noto_font.FONT_SHA256,size=noto_font.SIZE,palette_format_salt=salt,
                  source_captures=sources,textures=metadata,
                  verification='six 32px and three canonical 128px captures agree; new in-game check pending')
    (noto_font.OUTPUT/'record-pack.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__ == '__main__':
    print(json.dumps(install(),indent=2))
