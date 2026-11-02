"""Guarded HD repair for the two captured, six-column Units name sheets.

Legacy save names remain Japanese in transient multi-name records. Translate
their *display* into existing quads, including padding cells, without changing
the record, executable, save, geometry, or canonical font. This deliberately
matches exact captures, not arbitrary Japanese glyphs or other unit orders.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
import interface_redraw as pack
import interface_art
import noto_font as font
import font_record_pack as records
import stock_atlas_pack as atlas
import ui_upscale
import vwf

ROOT = pack.ROOT
DEFAULT_OUT = ROOT/'build/ui-redraw-units-v2'
CAPTURES = {
    'e684e6a6.png': 'f7419c15084561d23c690630dd744dcf019119170dae8b86391da6aea86eb398',
    '133707ea.png': '3e3a895f41dcc4d8992e93383aea3b99213187d11f059f62e32fcb165b913648',
}
COMMON_SHA = 'ff691c2cd4f81a5d10ff19014c6ba75461971b870c1967fefd560a76f55fcc7f'
EXE_SHA = 'fe6f4c774d7080fb77d496e222f17abb0661f4e585797a9b200a1f848023bfe2'
NATIVE_ROWS = ['Abel  ', 'レブロブス ', 'ガイウス  ', 'ピリポ   ', 'Warden'] + ['Guard ']*5
ALIASES = {1:'Leb', 2:'Gaius', 3:'Piripo'}


def index(ch):
    if ch == ' ': return 0
    if ch in font.latin.charmap(): return font.latin.charmap()[ch]
    return font.latin.sjis_to_index(int.from_bytes(ch.encode('cp932'),'big'))


def layout(text, exe):
    """Mirror r35's bearing/advance and English-only 2:1 quad compensation."""
    ids = [index(ch) for ch in text]
    advances = exe[vwf.ADV_TAB-vwf.LOAD_BASE:vwf.ADV_TAB-vwf.LOAD_BASE+vwf.NGLYPH]
    bearings = exe[vwf.BEAR_TAB-vwf.LOAD_BASE:vwf.BEAR_TAB-vwf.LOAD_BASE+vwf.NGLYPH]
    forward = __import__('reusable_atlas').tables()[0]
    pen = 0
    result = []
    for glyph in ids:
        factor = 2 if glyph < 256 and forward[glyph] != 255 else 1
        result.append((pen+bearings[ids[0]]-bearings[glyph], factor))
        pen += advances[glyph]
    return result


def word_mask(word):
    """Exactly the installed font's glyphs and advances, in game-X coordinates."""
    canvas = Image.new('L',(512,64)); pen = 0
    for ch in word:
        glyph = font.glyph(ch).resize((256,64),Image.Resampling.LANCZOS)
        layer = Image.new('L',canvas.size); layer.paste(glyph,(pen*4,0))
        canvas = Image.fromarray(np.maximum(np.array(canvas),np.array(layer)))
        pen += font.game_advances()[ch]
    return canvas


def alias_cells(native, word, exe):
    """Use overlap to place tile boundaries in whitespace where possible.

    A two-outline-pixel inset lets Piripo's final letter fit wholly into one
    padding quad. Never split ink across different quad scale factors.
    """
    positions = layout(native,exe)
    canvas = Image.new('L',(544,64)); canvas.paste(word_mask(word),(16,0))
    pixels = np.array(canvas); end = canvas.getbbox()[2]; start = 0; result = []
    for i,(origin,factor) in enumerate(positions):
        right = (origin+28*factor)*4
        if start >= end:
            stop = start
        elif end <= right:
            stop = end
        elif i+1 < len(positions):
            next_origin,next_factor = positions[i+1]
            candidates = range(max(start,next_origin*4),right+1)
            # Wider blank margin wins; keep any interpolation away from ink.
            stop = min(candidates,key=lambda x:int(pixels[:,max(0,x-4):x+4].sum()))
            if factor != next_factor and pixels[:,stop-2:stop+2].max() > 12:
                raise ValueError('scaled alias tile would cut a letter')
        else:
            raise ValueError('alias exceeds existing quad coverage')
        cell = Image.new('L',(128*factor,64))
        if stop > start: cell.paste(canvas.crop((start,0,stop,64)),(start-origin*4,0))
        result.append(cell.resize((128,64),Image.Resampling.LANCZOS))
        start = stop
    return result


def colored(mask, color):
    result = Image.new('RGBA',mask.size,color[:3]+(0,)); result.putalpha(mask)
    return result


def prepare(out=DEFAULT_OUT):
    out = Path(out).resolve()
    if not out.is_relative_to((ROOT/'build').resolve()) or out == (ROOT/'build').resolve():
        raise ValueError('use dedicated build subdirectory')
    if (out/'manifest.json').exists(): raise ValueError('pack exists')
    exe = (ui_upscale.DEFAULT_BUILD/'1ST_READ.BIN').read_bytes()
    if pack.sha(exe) != EXE_SHA: raise ValueError('unknown game text metrics')
    native_font = font.NATIVE.read_bytes()
    _, color, _ = records.verified_palette(ui_upscale.DUMPS)
    low = []; high = []
    for name,digest in CAPTURES.items():
        path = ui_upscale.DUMPS/name
        if pack.sha(path.read_bytes()) != digest: raise ValueError('unknown Units capture: '+name)
        with Image.open(path) as im:
            image = im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        low.append(image); high.append(image.resize((512,512),Image.Resampling.NEAREST))
        if (ui_upscale.TARGET/name).exists(): raise ValueError('existing name artwork must be reviewed')
    palettes = {}
    for row,text in enumerate(NATIVE_ROWS):
        masks = alias_cells(text,ALIASES[row],exe) if row in ALIASES else [font.glyph(c) for c in text]
        for col,(ch,mask) in enumerate(zip(text,masks)):
            slot = row*6+col; sheet,local = divmod(slot,32); x,y = atlas.cell(local)
            captured = low[sheet].crop((x,y,x+32,y+16))
            indices = records.indexed_cell(native_font,index(ch))
            for value,pixel in zip(indices.getdata(),captured.getdata()):
                if value in palettes and palettes[value] != pixel:
                    raise ValueError('native glyph/capture mismatch')
                palettes[value] = pixel
            high[sheet].paste(colored(mask,color),(x*4,y*4))
    if palettes.get(1) != color or palettes[0][3] != 0:
        raise ValueError('unexpected captured font palette')
    # Last four cells are unrelated allocator residue. Never rewrite them.
    for slot in range(28,32):
        x,y = atlas.cell(slot); rect = (x*4,y*4,(x+32)*4,(y+16)*4)
        expected = low[1].resize((512,512),Image.Resampling.NEAREST).crop(rect)
        if high[1].crop(rect).tobytes() != expected.tobytes(): raise ValueError('unused cell changed')
    common_path = ui_upscale.TARGET/'fc87d908.png'; common_bytes = common_path.read_bytes()
    if pack.sha(common_bytes) != COMMON_SHA: raise ValueError('unknown installed common UI')
    with Image.open(common_path) as im:
        before = im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    # Replace only the arrow's ink footprint in its two known copies.
    arrow = interface_art.selector().crop((12,12,48,56))
    updates = [(rect,arrow,'smooth selector arrow') for rect in ((3,83,12,94),(99,19,108,30))]
    common,changed = pack.compose(before,updates)
    pending = [(name,None,image) for name,image in zip(CAPTURES,high)]
    pending.append(('fc87d908.png',common_bytes,common))
    for folder in ('textures','originals','upright'): (out/folder).mkdir(parents=True,exist_ok=True)
    entries = []
    for name,previous,image in pending:
        if previous is not None: (out/'originals'/name).write_bytes(previous)
        image.save(out/'upright'/name)
        image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(out/'textures'/name)
        entries.append(dict(texture=name,original_file_sha256=pack.sha(previous) if previous else None,
                            output_file_sha256=pack.sha((out/'textures'/name).read_bytes())))
    preview = Image.new('RGBA',(640,10*96),(12,12,12,255))
    for row,text in enumerate(NATIVE_ROWS):
        positions = layout(text,exe)
        for col,(origin,factor) in enumerate(positions):
            sheet,local = divmod(row*6+col,32); x,y = atlas.cell(local)
            cell = high[sheet].crop((x*4,y*4,(x+28)*4,(y+16)*4))
            cell = cell.resize((112*factor,64),Image.Resampling.BILINEAR)
            preview.alpha_composite(cell,(16+origin*4,row*96+8))
    # Preview applies the game's 2:1 vertical display aspect.
    preview.resize((640,1920),Image.Resampling.BILINEAR).save(out/'names-preview.png')
    interface_art.selector().resize((768,256),Image.Resampling.LANCZOS).save(out/'selector-preview.png')
    report = dict(version=1,scope='captured Units list: Leb/Gaius/Piripo aliases, all ten names in Noto, smooth shared selector arrow',
                  textures=entries,changed_arrow_pixels=changed,unused_cells_preserved=True,
                  limitations=['Exact captured unit order only; other list textures need separate coverage.',
                               'Texture-only legacy alias uses existing padding quads; needs live visual verification.',
                               'Saves, executable, geometry, stats, portraits and buttons unchanged.'])
    (out/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','install','restore'))
    parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    args = parser.parse_args()
    report = prepare(args.out) if args.command == 'prepare' else pack.apply(args.out,args.command=='restore')
    print(json.dumps(report,indent=2))
