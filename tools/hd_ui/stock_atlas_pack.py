"""Generate a standard Flycast PNG replacement from a verified fixed-atlas dump.

No custom emulator, injected host DLL, OCR or runtime font matcher. Matching
happens OFFLINE only to identify the stock dump's hash and palette safely.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageFont
import generate
import font_style
import reusable_atlas as atlas
import bizin_font


def cell(slot):
    offset = (slot * 256 - 128 * (slot & 1)) * 2
    return (sum(((offset >> (2*b+1)) & 1) << b for b in range(8)),
            sum(((offset >> (2*b)) & 1) << b for b in range(8)))


def sheets(source, ttf, renderer=None):
    if ttf.resolve() == font_style.DEFAULT_TTF.resolve():
        font_style.default_font()
    data = source.read_bytes()
    font = ImageFont.truetype(str(ttf), 128)
    if renderer is None and ttf.resolve() == font_style.DEFAULT_TTF.resolve():
        renderer=bizin_font
    natural = renderer is not None
    if natural:font=renderer.outline(ttf)
    forward, _, chars = atlas.tables()
    low = Image.new('L', (256,256)); high = Image.new('L',(1024,1024))
    seen = set()
    for character, glyph in chars.items():
        if glyph in seen: continue
        seen.add(glyph)
        if natural:
            result=generate.native_glyph(data,character)
            if result is None:continue
            _,lo=result
            hi=renderer.glyph(character,font)
        else:
            result=generate.make_glyph(data,character,font,ink_scale=generate.COMPACT_INK_SCALE)
            if result is None:continue
            _,lo,hi=result
        x,y=cell(forward[glyph]);low.paste(lo,(x,y));high.paste(hi,(x*4,y*4))
    return low, high


def replacement(dump, low, high):
    """Fail closed unless EVERY pixel matches the canonical native sheet."""
    if dump.size != low.size: return None
    native=dump.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    values=list(native.getdata());mask=list(low.getdata())
    backgrounds={p for p,m in zip(values,mask) if not m}
    foregrounds={p for p,m in zip(values,mask) if m}
    if len(backgrounds)!=1 or len(foregrounds)!=1:return None
    bg=next(iter(backgrounds));fg=next(iter(foregrounds))
    if bg==fg:return None
    # Interpolate RGBA directly to preserve the dump's exact two-color palette.
    # Transparent backgrounds retain foreground RGB to avoid dark filter halos.
    if bg[3]==0:bg=fg[:3]+(0,)
    out=Image.new('RGBA',high.size,bg)
    solid=Image.new('RGBA',high.size,fg);out.paste(solid,(0,0),high)
    return out.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def segments(low, high):
    """Stock count=128 splits into FOUR 32-slot 128px sheets, not one 256px.

    Its threshold uses >128, not >=128. These quadrants preserve the global
    Morton slot order. Blank padding cannot identify a font and needs no HD.
    """
    for index, (x,y) in enumerate(((0,0),(128,0),(0,128),(128,128))):
        lo=low.crop((x,y,x+128,y+128))
        if lo.getbbox() is None:continue
        hi=high.crop((x*4,y*4,(x+128)*4,(y+128)*4))
        yield index,lo,hi


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font',type=Path,default=bizin_font.NATIVE)
    p.add_argument('--ttf',type=Path,default=font_style.DEFAULT_TTF)
    p.add_argument('--dumps',type=Path,default=atlas.ROOT/'build/stock-atlas-run/data/texdump/T20101M')
    p.add_argument('--output',type=Path,default=atlas.ROOT/'build/stock-atlas-run/data/textures/T20101M')
    p.add_argument('--preview-only',action='store_true')
    p.add_argument('--noto-regular',action='store_true',
                   help='use the pinned Noto native font and direct Regular outlines')
    args=p.parse_args()
    renderer=bizin_font if args.ttf.resolve()==font_style.DEFAULT_TTF.resolve() else None
    style=font_style
    if args.noto_regular:
        import noto_font
        renderer=style=noto_font
        args.font=noto_font.NATIVE;args.ttf=noto_font.default_font()
    low,high=sheets(args.font,args.ttf,renderer=renderer)
    preview=(renderer.OUTPUT if args.noto_regular else atlas.ROOT/'build/reusable-atlas')
    preview.mkdir(parents=True,exist_ok=True)
    low.save(preview/'native-sheet-mask.png');high.save(preview/'hd-sheet-mask.png')
    if args.preview_only:return
    matches=[]
    parts=list(segments(low,high))
    for path in sorted(args.dumps.glob('*.png')):
        # Stock texture names must be hash-only, never arbitrary paths.
        if not 1<=len(path.stem)<=8 or any(c not in '0123456789abcdef' for c in path.stem.lower()):continue
        with Image.open(path) as dump:
            for index,lo,hi in parts:
                result=replacement(dump,lo,hi)
                if result is None:continue
                args.output.mkdir(parents=True,exist_ok=True)
                result.save(args.output/path.name)
                matches.append(dict(texture=path.name,segment=index,native_size=list(lo.size),hd_size=list(hi.size)))
    if not matches:
        raise SystemExit('No canonical atlas found. Cold-boot the test disc, open battle help, then retry. No replacements installed.')
    (preview/'stock-pack.json').write_text(json.dumps(dict(
        textures=matches, output=str(args.output),
        font_size=renderer.SIZE if renderer else None, layout_metrics_unchanged=False,
        outline_font=str(args.ttf),
        outline_font_sha256=hashlib.sha256(args.ttf.read_bytes()).hexdigest()),
        indent=2),encoding='utf-8')
    if renderer is not None:
        style.copy_license(args.output)
    print('Installed verified standard PNG textures: '+', '.join(m['texture'] for m in matches))
    print('Fully close and restart the STOCK test emulator to load the pack.')


if __name__=='__main__':main()
