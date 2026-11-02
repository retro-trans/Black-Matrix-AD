"""Repair captured No-magic text and inset dedicated HD Range/Area labels."""
import json
import sys
import struct
import shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
import hd_silver_fallback as hd
import magic_label_size as labels
import magic_hd_followup as helper
import magic_menu
import awaken_confirm as archive

ROOT=hd.ROOT
OUT=ROOT/'build/magic-spacing-fix-v1'
BUILD=ROOT/'build/magic-panel-fix-v1'
VARIANTS={
    'hd':('reusable-atlas-noto-ui-r35-hd-awaken-prompt-v1','reusable-atlas-noto-ui-r35-hd-magic-panel-v1'),
    'native':('reusable-atlas-noto-ui-r35-native-silver-awaken-prompt-v1','reusable-atlas-noto-ui-r35-native-silver-magic-panel-v1'),
}


def patch(data):
    if data[magic_menu.INSET:magic_menu.INSET+4]!=struct.pack('<f',6):raise ValueError('Unknown label inset')
    # Descriptor +20 for the 5-column/3-row Range/Area label window. The
    # separate numbers window uses another literal; do not touch its position.
    if data[0x6CF90:0x6CF98]!=bytes.fromhex('2bc708f314e037f4'):raise ValueError('Label-window descriptor changed')
    record=magic_menu.encoded('No magic')
    if data[magic_menu.UNAVAILABLE:magic_menu.UNAVAILABLE+len(record)]!=record:raise ValueError('No-magic source text differs')
    result=bytearray(data);result[magic_menu.INSET:magic_menu.INSET+4]=struct.pack('<f',10)
    return bytes(result)


def build():
    archive.build(patcher=patch,out=BUILD,variants=VARIANTS,status='verified-magic-panel-fix',
        details=dict(label_inset_before=6,label_inset_after=10,numbers_and_borders_unchanged=True,wording_unchanged=True))


def render(text,capacity,font):
    size=int((capacity*512)**.5);low=Image.new('L',(size,size));high=Image.new('L',(size*4,size*4))
    chars={' ':0,**hd.native.latin.charmap()};face=hd.native.noto_font.outline()
    for i,ch in enumerate(text):
        x,y=hd.records.pack.cell(i);low.paste(hd.records.indexed_cell(font,chars[ch]),(x,y))
        high.paste(hd.native.noto_font.glyph(ch,face),(x*4,y*4))
    return low,high


def install_hd():
    fonts=hd.fonts();salt,color,_=hd.records.verified_palette(hd.DUMPS)
    # Known eight-letter text, normal two-cell pieces, full-sheet variants,
    # and padded suffix allocations. Never guess unrelated allocator residue.
    parts={('No magic',8),('No magic',32)}
    parts|={(text,2) for text in ('No',' m','ag','ic')}
    parts|={('No magic'[start:],cap) for start in (2,4,6) for cap in (8,32)}
    pending={};coverage=[]
    for font_name,font in zip(('noto','silver'),fonts):
        for text,capacity in sorted(parts):
            low,high=render(text,capacity,font);name=hd.key(low,salt)
            art=Image.new('RGBA',high.size,color[:3]+(0,));art.putalpha(high);art=art.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if name in pending and pending[name].tobytes()!=art.tobytes():raise ValueError('HD key collision')
            if (hd.TARGET/name).exists():
                with Image.open(hd.TARGET/name) as im:
                    if im.convert('RGBA').tobytes()!=art.tobytes():raise ValueError('Unexpected existing No-magic artwork')
            pending[name]=art;coverage.append(dict(font=font_name,text=text,capacity=capacity,texture=name))
    pack=BUILD/'pack';pack.mkdir();added=[]
    for name,art in pending.items():
        art.save(pack/name)
        if not (hd.TARGET/name).exists():shutil.copy2(pack/name,hd.TARGET/name);added.append(name)
        with Image.open(hd.TARGET/name) as im:
            if im.convert('RGBA').tobytes()!=art.tobytes():raise ValueError('HD readback differs')
    previous=json.loads((BUILD/'build-verification.json').read_text())['original_hd_hashes']
    if any(hd.native.base.digest(hd.TARGET/n)!=sha for n,sha in previous.items()):raise ValueError('Previous HD art changed')
    report=dict(status='installed-magic-panel-fix',added=added,coverage=coverage,
                existing_hd_preserved=len(previous),live_game_verified=False,
                diagnosis='Known two-cell pieces existed; full-label and padded suffix variants were missing. Exact live allocation is not captured.')
    (BUILD/'installation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(added=len(added),variants=len(coverage))))


def scan():
    fonts=hd.fonts();dictionaries=[]
    for font in fonts:
        chars={bytes(512):' '}
        for ch in hd.native.latin.charmap():
            glyph=hd.native.decode(font,ch);chars.setdefault(glyph.tobytes(),ch)
        dictionaries.append(chars)
    found=[]
    for path in hd.DUMPS.glob('*.png'):
        with Image.open(path) as im:
            for font,chars in zip(('noto','silver'),dictionaries):
                text=helper.decode(im,chars)
                if text and ('magic' in text or 'Range' in text or 'Area' in text):
                    found.append(dict(texture=path.name,font=font,text=text,installed=(hd.TARGET/path.name).exists()))
    OUT.mkdir(exist_ok=True)
    (OUT/'captures.json').write_text(json.dumps(found,indent=2),encoding='utf-8')
    print(json.dumps(found,indent=2))


if __name__=='__main__':
    if '--scan' in sys.argv:scan()
    else:build();install_hd()
