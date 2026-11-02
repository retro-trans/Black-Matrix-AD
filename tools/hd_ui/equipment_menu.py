"""Equipment heading/buttons and optional vertical-attack icon replacement.

The heading uses retired deployment-menu storage after mainmenu.ensure.
Sprite text is directly rasterized Noto, both on disc and at 4x in Flycast.
The optional sword is composed into the same authenticated HD page; unrelated
icons and game logic remain unchanged.
"""
import hashlib
import json
import struct

import xxhash
from PIL import Image, ImageDraw, ImageFont
import cooking
import mainmenu
import field_battle_ui
import patchline
import pvr_atlas
import noto_font
import seed_noto_pack
import vertical_attack_icon

ROOT = mainmenu.ROOT
UI = ROOT/'script/ui/equipment_menu.tsv'
TITLE = 0x89E82
POINTERS = (0x681B0, 0x68904)
STORAGE, STORAGE_END = 0x8981A, 0x89826  # Heading owns 12 bytes; prompts use the remaining 44.
PVX, TEXTURE = 0x21000, 0x21890
BUTTONS = ((61, (64,128,104,144), 'unequip'),
           (62, (64,144,104,160), 'discard'))
CAPTURE = 'c8cacd24.png'
SOURCE_SHA256 = '391539fbc880552edf7a2c7ec83f5dea4710dd8257d337e1371669931c848ae7'
SCALE, SIZE, BASELINE = 4, 9.5, 11.75
COLOR = (255,160,16)
# User-requested HD-only alignment upgrade of our exact r24 sword page.
# All other existing artwork still fails closed in write_pack().
PREVIOUS_SWORD_PACK = {'e578881f.png': {
    'da8bdaf1c98a30d67f0ca6fcf6a7da3eb69e465ab312619e146ba7d2b7349171'}}


def strings():
    text = cooking.strings(UI)
    # Five cells keep the current heading's visual center without touching the
    # shared heading window used by Status and Magic.
    if not 1 <= len(text['heading']) <= 5:
        raise ValueError('equipment heading exceeds its compact layout')
    return text


def patch_executable(data):
    for i, (_, pointer, _, _) in enumerate(mainmenu.MENUS):
        if struct.unpack_from('<I', data, pointer)[0] != mainmenu.STORAGE+i*mainmenu.RECORD_BYTES:
            raise ValueError('install expanded main menus before equipment heading')
    mainmenu.ensure(data)
    original = (ROOT/'extracted/1ST_READ.BIN').read_bytes()
    text = strings()['heading']
    payload = struct.pack('<%dH' % (len(text)+1), len(text),
                          *(patchline.to_sjis(ch) for ch in text))
    previous = bytearray(original); field_battle_ui.patch_executable(previous)
    accepted = [original[STORAGE:STORAGE_END],previous[STORAGE:STORAGE_END]]
    accepted += [payload+source[len(payload):] for source in accepted[:]]
    if data[STORAGE:STORAGE_END] not in accepted:
        raise ValueError('unknown retired deployment-menu storage')
    old = struct.pack('<I',mainmenu.vwf.LOAD_BASE+TITLE)
    new = struct.pack('<I',mainmenu.vwf.LOAD_BASE+STORAGE)
    for offset in POINTERS:
        if data[offset:offset+4] not in (old,new):
            raise ValueError('unknown equipment heading pointer')
    data[STORAGE:STORAGE+len(payload)] = payload
    for offset in POINTERS: data[offset:offset+4] = new
    return dict(heading=text, storage=STORAGE, pointers=list(POINTERS),
                scope='text only; shared heading position and command logic unchanged')


def labels():
    """Full words at a smaller em size, never horizontally squeezed."""
    face = ImageFont.truetype(str(noto_font.default_font()),round(SIZE*SCALE))
    text = strings(); result = []
    for index, rect, key in BUTTONS:
        probe = Image.new('L',(512,128))
        ImageDraw.Draw(probe).text((SCALE,BASELINE*SCALE),text[key],font=face,fill=255,anchor='ls')
        box = probe.getbbox()
        if not box or box[0]<SCALE or box[2]>39*SCALE or box[3]>=16*SCALE:
            raise ValueError('equipment caption exceeds original 40x16 sprite')
        result.append((index,rect,probe.crop((0,0,40*SCALE,16*SCALE))))
    return result


def patch_system(data):
    original = (ROOT/'extracted/SYSTEM.DAT').read_bytes()
    if (data[PVX:PVX+4]!=b'PVX ' or
            data[TEXTURE:TEXTURE+16]!=original[TEXTURE:TEXTURE+16]):
        raise ValueError('unknown equipment sprite atlas header')
    pending = []
    for index, rect, mask in labels():
        x,y,xx,yy = rect
        expected = (40,16,x,y,xx,yy,0,0)
        if struct.unpack_from('<8H',data,PVX+48+index*16)!=expected:
            raise ValueError('equipment sprite geometry changed')
        low = mask.resize((40,16),Image.Resampling.LANCZOS)
        sites = []
        for row in range(16):
            for col in range(40):
                level=low.getpixel((col,row))
                rgb=[c*level//255 for c in COLOR]
                value=(0x8000 | (rgb[0]*31//255)<<10 | (rgb[1]*31//255)<<5 | rgb[2]*31//255) if level>=64 else 0
                offset=TEXTURE+16+2*pvr_atlas.pixel_index(x+col,y+row)
                sites.append((offset,struct.pack('<H',value)))
        current=b''.join(data[o:o+2] for o,_ in sites)
        source=b''.join(original[o:o+2] for o,_ in sites)
        target=b''.join(v for _,v in sites)
        if current not in (source,target):
            raise ValueError('unknown equipment caption pixels')
        pending.extend(sites)
    for offset,value in pending:data[offset:offset+2]=value
    return dict(labels={k:strings()[k] for _,_,k in BUTTONS},size=SIZE,
                sprites=[i for i,_,_ in BUTTONS],scope='two caption rectangles only')


def decoded(data):
    """Match Flycast ARGB1555 channel expansion (bit replication)."""
    image=pvr_atlas.decode(data,TEXTURE)
    image.putdata([tuple(((v*31+127)//255<<3 | (v*31+127)//255>>2) for v in p[:3])+(p[3],)
                   for p in image.getdata()])
    return image


def raw_hash(data):
    raw=data[TEXTURE+16:TEXTURE+16+256*256*2]
    return '%x.png' % xxhash.xxh32(raw,seed=7).intdigest()


def prepare_pack(source, patched, capture):
    native=decoded(source)
    actual=capture.convert('RGBA')
    if (actual.size!=(256,256) or hashlib.sha256(actual.tobytes()).hexdigest()!=SOURCE_SHA256
            or actual.tobytes()!=native.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
            or raw_hash(source)!=CAPTURE):
        raise ValueError('equipment atlas capture does not match verified source')
    expected=bytearray(source);patch_system(expected)
    if expected!=patched:raise ValueError('unexpected equipment SYSTEM changes')
    high=native.resize((1024,1024),Image.Resampling.NEAREST)
    for _,rect,mask in labels():
        tile=Image.new('RGBA',mask.size,COLOR+(0,));tile.putalpha(mask)
        high.paste(tile,(rect[0]*SCALE,rect[1]*SCALE))
    return high.transpose(Image.Transpose.FLIP_TOP_BOTTOM),raw_hash(patched)


def install_pack(patched, sword_icon=False, inventory=False, attack_styles=False):
    profile=ROOT/'build/stock-atlas-run/data'
    path=profile/'texdump/T20101M'/CAPTURE
    if not path.exists():return dict(status='pending verified equipment atlas capture',missing=CAPTURE)
    # Restore only the two source rectangles to authenticate this build's atlas.
    source=bytearray(patched);original=(ROOT/'extracted/SYSTEM.DAT').read_bytes()
    buttons_only=bytearray(patched)
    if attack_styles:
        import attack_type_icons
        attack_type_icons.restore_system(source)
        attack_type_icons.restore_system(buttons_only)
    if inventory:
        import inventory_menu
        inventory_menu.restore_system(source)
        inventory_menu.restore_system(buttons_only)
    if sword_icon:
        vertical_attack_icon.restore_legacy(source)
        vertical_attack_icon.restore_legacy(buttons_only)
    for _,(x,y,xx,yy),_ in BUTTONS:
        for row in range(y,yy):
            for col in range(x,xx):
                o=TEXTURE+16+2*pvr_atlas.pixel_index(col,row)
                source[o:o+2]=original[o:o+2]
    with Image.open(path) as capture:high,name=prepare_pack(source,buttons_only,capture)
    if sword_icon or inventory or attack_styles:
        high=high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if sword_icon:
            high.paste(vertical_attack_icon.hd_artwork(),(0,16*SCALE))
        if inventory:
            inventory_menu.compose(high)
        if attack_styles:
            attack_type_icons.compose(high)
        high=high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        name=raw_hash(patched)
    target=profile/'textures/T20101M'
    seed_noto_pack.write_pack(target,[(high,dict(texture=name))],
                             previous_hashes=PREVIOUS_SWORD_PACK if sword_icon else None)
    noto_font.copy_license(target)
    preview=Image.new('RGBA',(160,128),'black')
    upright=high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    for row,(_,rect,_) in enumerate(BUTTONS):
        preview.alpha_composite(upright.crop(tuple(v*SCALE for v in rect)),(0,row*64))
    out=ROOT/'build/hd-ui';out.mkdir(exist_ok=True)
    preview.save(out/'equipment-buttons-english.png')
    meta=dict(texture=name,source=CAPTURE,source_rgba_sha256=SOURCE_SHA256,
              font_sha256=noto_font.FONT_SHA256,size=SIZE,scale=SCALE,
              labels={k:strings()[k] for _,_,k in BUTTONS},
              verification='source pixels and raw stock hash verified; new in-game capture pending')
    if sword_icon:
        meta['vertical_attack_icon']=vertical_attack_icon.patch_system(bytearray(patched))
        meta['vertical_attack_icon'].update(hd_revision=2,hd_size=vertical_attack_icon.HD_SIZE,
                                           hd_alignment='1px down, horizontally centered; native icon unchanged')
    if inventory:
        meta['inventory_categories']=inventory_menu.patch_system(bytearray(patched))
    if attack_styles:
        meta['attack_style_icons']=attack_type_icons.patch_system(bytearray(patched))
    (out/'equipment-buttons-pack.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta
