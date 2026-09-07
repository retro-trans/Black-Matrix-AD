"""Localize load/config sprites, confirmations, and the Free Action banner.

Sprite bounds come from the original PVX descriptors. Only the selected atlas
pixels are replaced; controller art, UVs, geometry, and save data are unchanged.
"""
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import cooking
import field_battle_ui
import pvr_atlas

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'script/ui/config_load.tsv'
FONT = r'C:\Windows\Fonts\verdanab.ttf'
EXE_RECORDS = {
    0x89EBC: ('empty_equipment', 7),
    0x88E4A: ('pick_vmu', 8), 0x88E5C: ('pick_port', 11),
    0x88E96: ('pick_slot', 12), 0x88086: ('finish_setup', 16),
    0x888CA: ('show_again', 16), 0x8842C: ('show_help', 18),
    0x88452: ('hide_help', 19), 0x8847A: ('manual_help', 19),
    0x884A2: ('default_help', 28), 0x884DC: ('exit_help', 28),
}
START_HELP = 0x7A0D6
GOLD = (255, 160, 16)
SYSTEM_SPRITES = [
    (0x21000, 0x21890, 63, 'back', GOLD),
    (0x21000, 0x21890, 64, 'confirm', GOLD),
    (0x629040, 0x6294D0, 17, 'show', (255, 255, 255)),
    (0x629040, 0x6294D0, 18, 'hide', (255, 255, 255)),
    (0x629040, 0x6294D0, 19, 'manual', (255, 255, 255)),
    (0x629040, 0x6294D0, 20, 'defaults', (255, 255, 255)),
] + [(0x608620, 0x608810, i, 'chapter_%d' % (i+1), GOLD) for i in range(11)] + [
    (0x608620, 0x608810, 11, 'chapter_final', GOLD),
    (0x608620, 0x608810, 12, 'port', GOLD),
    (0x608620, 0x608810, 13, 'slot', GOLD),
]
BANNER_PVX = 0xBC4000
BANNER_TEXTURE = 0xBC4090
MOVE_PVX = 0x629040
MOVE_TEXTURE = 0x6494F0
MOVE_SPRITE = 56
STATUS_SPRITES = [(51, 'status_heading'), (59, 'equip_button'),
                  (57, 'magic_button'), (6, 'vertical_attack')]


def sprite_rect(data, pvx, index, expected_page=0):
    if data[pvx:pvx+4] != b'PVX ':
        raise ValueError('missing PVX header')
    count = struct.unpack_from('<I', data, pvx+32)[0]
    if not 0 <= index < count:
        raise ValueError('invalid sprite index')
    w, h, x0, y0, x1, y1, page, flags = struct.unpack_from('<8H', data, pvx+48+index*16)
    if page != expected_page or flags != 0 or (x1-x0, y1-y0) != (w, h):
        raise ValueError('unexpected sprite layout')
    return x0, y0, x1, y1


def paint(data, texture, rect, text, color, size=14, center=False, condense=False):
    """Write a label into an existing ARGB1555 atlas rectangle only."""
    if data[texture:texture+4] != b'PVRT' or data[texture+8:texture+10] != b'\x00\x01':
        raise ValueError('expected ARGB1555 square-twiddled texture')
    if struct.unpack_from('<HH', data, texture+12) != (256, 256):
        raise ValueError('expected 256x256 atlas')
    x0, y0, x1, y1 = rect
    w, h = x1-x0, y1-y0
    if not (0 <= x0 < x1 <= 256 and 0 <= y0 < y1 <= 256):
        raise ValueError('label outside atlas')
    for font_size in range(size, 6, -1):
        font = ImageFont.truetype(FONT, font_size)
        box = font.getbbox(text)
        tw, th = box[2]-box[0], box[3]-box[1]
        if (tw <= w-2 or condense) and th <= h-2:
            break
    else:
        raise ValueError('label does not fit sprite: ' + text)
    mask_width = max(w, tw+2) if condense else w
    mask = Image.new('L', (mask_width, h))
    x = (mask_width-tw)//2 if center else 1
    y = (h-th)//2
    ImageDraw.Draw(mask).text((x-box[0], y-box[1]), text, font=font, fill=255)
    if mask_width != w:
        mask = mask.resize((w, h), Image.Resampling.LANCZOS)
    for y in range(h):
        for x in range(w):
            level = mask.getpixel((x, y))
            if level >= 64:
                r, g, b = (c * level // 255 for c in color)
                word = 0x8000 | (r*31//255)<<10 | (g*31//255)<<5 | (b*31//255)
            else:
                word = 0
            struct.pack_into('<H', data, texture+16+2*pvr_atlas.pixel_index(x+x0, y+y0), word)


def patch_system(data, preview_dir=None):
    text = cooking.strings(UI)
    for pvx, texture, index, key, color in SYSTEM_SPRITES:
        paint(data, texture, sprite_rect(data, pvx, index), text[key], color)
    move_rect = sprite_rect(data, MOVE_PVX, MOVE_SPRITE, expected_page=1)
    paint(data, MOVE_TEXTURE, move_rect, text['move_heading'], (255,255,255))
    for index, key in STATUS_SPRITES:
        paint(data, 0x21890, sprite_rect(data, 0x21000, index),
              text[key], GOLD, condense=True)
    if preview_dir is not None:
        # Draw only patched labels over a neutral background for visual QA.
        out = Image.new('RGB', (480, 32*((len(SYSTEM_SPRITES)+2)//3)), '#252525')
        for i, (pvx, texture, index, key, _) in enumerate(SYSTEM_SPRITES):
            crop = pvr_atlas.decode(data, texture).crop(sprite_rect(data, pvx, index))
            out.paste(crop, ((i%3)*160, (i//3)*32), crop)
        out.save(Path(preview_dir) / 'load-config-labels-english.png')
        move = pvr_atlas.decode(data, MOVE_TEXTURE).crop(move_rect)
        bg = Image.new('RGBA', move.size, 'black')
        bg.alpha_composite(move)
        bg.resize((move.width*2, move.height*2), Image.Resampling.NEAREST).save(
            Path(preview_dir) / 'move-heading-english.png')
        status = Image.new('RGBA', (128, len(STATUS_SPRITES)*32), 'black')
        atlas = pvr_atlas.decode(data, 0x21890)
        for row, (index, _) in enumerate(STATUS_SPRITES):
            crop = atlas.crop(sprite_rect(data, 0x21000, index))
            crop = crop.resize((crop.width*2,crop.height*2), Image.Resampling.NEAREST)
            status.alpha_composite(crop, (0, row*32))
        status.save(Path(preview_dir) / 'status-labels-english.png')


def patch_event(data, preview_dir=None):
    text = cooking.strings(UI)
    rect = sprite_rect(data, BANNER_PVX, 0)
    paint(data, BANNER_TEXTURE, rect, text['free_action'], (255,255,255), size=24, center=True)
    if preview_dir is not None:
        im = pvr_atlas.decode(data, BANNER_TEXTURE).crop(rect)
        bg = Image.new('RGBA', im.size, 'black')
        bg.alpha_composite(im)
        bg.resize((im.width*2, im.height*2)).save(Path(preview_dir) / 'free-action-english.png')


def patch_executable(data):
    text = cooking.strings(UI)
    for offset, (key, width) in EXE_RECORDS.items():
        field_battle_ui.record(data, offset, [text[key]], width)
    field_battle_ui.record(data, 0x88E74, ['Pt.'+p for p in 'ABCD'], 4)
    field_battle_ui.record(data, 0x88EB0, ['Slot1', 'Slot2'], 5)


def patch_parameters(data):
    text = cooking.strings(UI)
    field_battle_ui.record(data, START_HELP, text['start_help'].split('\\n'), 19)


def install():
    for file, fn in [('1ST_READ.vwf.bin', patch_executable),
                     ('PARAMETA.vwf.dat', patch_parameters),
                     ('SYSTEM.vwf.dat', patch_system)]:
        path = ROOT / 'build' / file
        data = bytearray(path.read_bytes())
        if file == 'SYSTEM.vwf.dat':
            fn(data, ROOT / 'build')
        else:
            fn(data)
        path.write_bytes(data)
    print('localized VMU/load labels, help settings, and deployment confirmations')


if __name__ == '__main__':
    install()
