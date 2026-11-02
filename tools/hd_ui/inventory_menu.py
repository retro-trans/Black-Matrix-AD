"""Items/Abilities headings and full-width inventory category captions.

The HD battle menu must already be relocated before its retired text can hold
Abilities. Category sprites reuse unreferenced, transparent atlas space; their
IDs, colors, positions and inventory counts are preserved.
"""
import struct

from PIL import Image, ImageDraw, ImageFont
import battle_menu
import cooking
import field_battle_ui
import magic_menu
import noto_font
import pvr_atlas

ROOT = noto_font.ROOT
UI = ROOT/'script/ui/inventory_menu.tsv'
ITEMS, ITEMS_POINTER = 0x898C8, 0x5E8F4
ABILITIES, ABILITIES_POINTER = 0x8A09E, 0x7A5FC
STORAGE, END = 0x87FA6, 0x87FBA  # 20 bytes, preserving the old count word.
PVX, TEXTURE = 0x21000, 0x21890
SCALE, SIZE, BASELINE = 4, 12, 11.75
COLOR = (231, 140, 74)
HELP = {0x793B0:'help_overview', 0x79424:'help_discard', 0x79498:'help_battle_only'}
# Sprite ID, original rectangle, new transparent rectangle, translation key.
CATEGORIES = (
    (66, (64,176,96,192), (0,240,64,256), 'weapons'),
    (128, (144,112,160,128), (64,240,112,256), 'armor'),
    (129, (160,112,216,128), (112,240,192,256), 'accessories'),
    (130, (112,208,152,224), (176,208,256,224), 'consumables'),
)


def strings():
    text = cooking.strings(UI)
    if len(text['items']) > 6 or len(text['abilities']) != 9:
        raise ValueError('inventory heading exceeds its record capacity')
    return text


def records():
    text = strings()
    return [text['items'].ljust(6), text['abilities']]


def help_records():
    text = strings()
    records = []
    for key in HELP.values():
        rows = text[key].split('\\n')
        if len(rows)!=3 or any(len(row)>19 for row in rows):
            raise ValueError('inventory help must fit three 19-cell rows')
        records.append(''.join(row.ljust(19) for row in rows))
    return records


def patch_parameters(data):
    original = (ROOT/'extracted/PARAMETA.DAT').read_bytes()
    pending = []
    for (offset,key),text in zip(HELP.items(),help_records()):
        source = original[offset:offset+116]
        if len(source)!=116 or struct.unpack_from('<H',source)[0]!=57:
            raise ValueError('inventory help source record changed')
        target = magic_menu.encoded(text)
        if data[offset:offset+116] not in (source,target):
            raise ValueError('unknown inventory help at %X' % offset)
        pending.append((offset,target))
    for offset,target in pending:
        data[offset:offset+116] = target
    return dict(pages=list(HELP.values()),columns=19,rows=3,
                scope='three help text records only; counts and item behavior unchanged')


def patch_executable(data, battle):
    # Reconstruct and reapply the exact expanded battle menu on a copy. This
    # authenticates both its relocated record and pointer before storage reuse.
    candidate = bytearray(data)
    struct.pack_into('<I', candidate, battle_menu.POINTER,
                     magic_menu.BASE+battle_menu.ORIGINAL)
    struct.pack_into('<H', candidate, battle_menu.WIDTH, 0xE403)
    offset = battle['storage']-magic_menu.BASE
    candidate[offset:offset+battle['bytes']] = bytes(battle['bytes'])
    verified = battle_menu.patch(candidate)
    if candidate != data or verified != battle:
        raise ValueError('install verified expanded battle menu before inventory headings')
    original = (ROOT/'extracted/1ST_READ.BIN').read_bytes()
    previous = bytearray(original)
    field_battle_ui.patch_executable(previous)
    items, abilities = map(magic_menu.encoded, records())
    if len(abilities) != END-STORAGE:
        raise ValueError('Abilities storage bounds changed')
    checks = (
        (ITEMS, [original[ITEMS:ITEMS+14], items]),
        (ITEMS_POINTER, [struct.pack('<I', magic_menu.BASE+ITEMS)]),
        (ABILITIES, [original[ABILITIES:ABILITIES+10]]),
        (STORAGE, [original[STORAGE:END], previous[STORAGE:END], abilities]),
        (ABILITIES_POINTER, [struct.pack('<I', magic_menu.BASE+o)
                             for o in (ABILITIES, STORAGE)]),
    )
    for o, accepted in checks:
        if data[o:o+len(accepted[0])] not in accepted:
            raise ValueError('unknown inventory heading site at %X' % o)
    data[ITEMS:ITEMS+len(items)] = items
    data[STORAGE:END] = abilities
    struct.pack_into('<I', data, ABILITIES_POINTER, magic_menu.BASE+STORAGE)
    return dict(headings={k:strings()[k] for k in ('items','abilities')},
                storage=STORAGE, bytes=len(abilities),
                scope='two headings only; shared title grid and list logic unchanged')


def descriptor(rect):
    x,y,xx,yy = rect
    return struct.pack('<8H', xx-x, yy-y, x,y,xx,yy,0,0)


def labels():
    face = ImageFont.truetype(str(noto_font.default_font()), round(SIZE*SCALE))
    text = strings()
    result = []
    for index, _, rect, key in CATEGORIES:
        width = rect[2]-rect[0]
        probe = Image.new('L', (512,128))
        ImageDraw.Draw(probe).text((SCALE, BASELINE*SCALE), text[key],
                                  font=face, fill=255, anchor='ls')
        box = probe.getbbox()
        if not box or box[0]<SCALE or box[2]>(width-1)*SCALE or box[3]>=16*SCALE:
            raise ValueError('inventory caption exceeds reserved sprite rectangle')
        result.append((index,rect,probe.crop((0,0,width*SCALE,16*SCALE))))
    return result


def pixel_sites(rect):
    x,y,xx,yy = rect
    return [TEXTURE+16+2*pvr_atlas.pixel_index(col,row)
            for row in range(y,yy) for col in range(x,xx)]


def patch_system(data):
    original = (ROOT/'extracted/SYSTEM.DAT').read_bytes()
    if (data[PVX:PVX+48] != original[PVX:PVX+48] or
            data[TEXTURE:TEXTURE+16] != original[TEXTURE:TEXTURE+16]):
        raise ValueError('unknown inventory sprite atlas header')
    pending = []
    for (index,old,rect,key), (_,_,mask) in zip(CATEGORIES,labels()):
        d = PVX+48+index*16
        if data[d:d+16] not in (descriptor(old),descriptor(rect)):
            raise ValueError('unknown inventory category sprite descriptor')
        # No other sprite may refer to this newly allocated area.
        count = struct.unpack_from('<I', original, PVX+32)[0]
        for i in range(count):
            _,_,x,y,xx,yy,page,_ = struct.unpack_from('<8H', original, PVX+48+i*16)
            if page==0 and max(x,rect[0])<min(xx,rect[2]) and max(y,rect[1])<min(yy,rect[3]):
                raise ValueError('inventory caption overlaps existing sprite')
        sites = pixel_sites(rect)
        source = b''.join(original[o:o+2] for o in sites)
        if any(source):
            raise ValueError('inventory caption destination is not transparent unused space')
        low = mask.resize((rect[2]-rect[0],16),Image.Resampling.LANCZOS)
        values = []
        for alpha in low.getdata():
            rgb = [c*alpha//255 for c in COLOR]
            value = (0x8000 | (rgb[0]*31//255)<<10 | (rgb[1]*31//255)<<5 |
                     rgb[2]*31//255) if alpha>=64 else 0
            values.append(struct.pack('<H',value))
        target = b''.join(values)
        current = b''.join(data[o:o+2] for o in sites)
        if current not in (source,target):
            raise ValueError('unknown inventory caption pixels')
        pending.extend(zip(sites,values))
        pending.append((d,descriptor(rect)))
    for o,value in pending:
        data[o:o+len(value)] = value
    return dict(labels={k:strings()[k] for *_,k in CATEGORIES},size=SIZE,
                sprites=[i for i,*_ in CATEGORIES],
                scope='four sprite descriptors and unused atlas rectangles; counts unchanged')


def restore_system(data):
    """Authenticate the installed captions, then restore only their changes."""
    check = bytearray(data)
    patch_system(check)
    if check != data:
        raise ValueError('expected installed inventory captions')
    original = (ROOT/'extracted/SYSTEM.DAT').read_bytes()
    for index,old,rect,_ in CATEGORIES:
        d = PVX+48+index*16
        data[d:d+16] = descriptor(old)
        for o in pixel_sites(rect):
            data[o:o+2] = original[o:o+2]


def compose(high):
    """Compose direct 4x outlines into an upright, verified equipment page."""
    if high.size != (1024,1024):
        raise ValueError('unexpected HD inventory atlas size')
    for _,rect,mask in labels():
        tile = Image.new('RGBA',mask.size,COLOR+(0,))
        tile.putalpha(mask)
        high.paste(tile,(rect[0]*SCALE,rect[1]*SCALE))
    return high
