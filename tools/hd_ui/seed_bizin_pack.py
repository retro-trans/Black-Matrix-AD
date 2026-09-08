"""Seed stock replacement hashes for the new native font from verified dumps.

Stock Flycast's non-VQ paletted hash is XXH32(raw twiddled 4bpp, seed=7)
XOR palette hash XOR format bits (core/rend/TexCache.cpp::ComputeHash).
Require all three old captured sheets to agree on that palette/format salt.
No emulator source or running memory is modified.
"""
import hashlib
import json
from pathlib import Path
import xxhash
from PIL import Image
import stock_atlas_pack as pack
import bizin_font
import font_style

CAPTURES = ('559d7642.png','adce381a.png','fdb35a3c.png')
PROFILE = font_style.ROOT/'build/stock-atlas-run/data'


def twiddled(mask):
    if mask.size!=(128,128):raise ValueError('expected a 128px font segment')
    output=bytearray(8192)
    for y in range(128):
        for x in range(128):
            if not mask.getpixel((x,y)):continue
            index=sum(((y>>b)&1)<<(2*b)|((x>>b)&1)<<(2*b+1) for b in range(7))
            output[index//2] |= 1 << (4*(index%2))
    return bytes(output)


def install():
    # The old MFD is only a fingerprint of known captured textures. It does
    # not determine any Bizin outline, size, bearing, advance or baseline.
    old,_=pack.sheets(font_style.ROOT/'build/FONT.vwf.bin',font_style.DEFAULT_TTF)
    low,high=pack.sheets(bizin_font.NATIVE,font_style.DEFAULT_TTF)
    old_parts={i:lo for i,lo,_ in pack.segments(old,high)}
    new_parts={i:(lo,hi) for i,lo,hi in pack.segments(low,high)}
    checked=[]
    for name in CAPTURES:
        with Image.open(PROFILE/'texdump/T20101M'/name) as im:
            dump=im.convert('RGBA')
        matches=[]
        for i,old_mask in old_parts.items():
            lo,hi=new_parts[i]
            result=pack.replacement(dump,old_mask,hi)
            if result is not None:
                salt=int(Path(name).stem,16)^xxhash.xxh32(twiddled(old_mask),seed=7).intdigest()
                matches.append((i,lo,result,salt))
        if len(matches)!=1:raise ValueError('unknown or ambiguous original capture: '+name)
        checked.append(matches[0])
    if len({i for i,_,_,_ in checked})!=3 or len({s for _,_,_,s in checked})!=1:
        raise ValueError('captured stock hashes do not agree on raw layout and palette')
    target=PROFILE/'textures/T20101M';target.mkdir(parents=True,exist_ok=True)
    pending=[]
    for i,lo,result,salt in checked:
        name='%x.png'%(xxhash.xxh32(twiddled(lo),seed=7).intdigest()^salt)
        path=target/name
        if path.exists():
            with Image.open(path) as old_image:
                if old_image.convert('RGBA').tobytes()!=result.tobytes():
                    raise ValueError('different replacement already exists: '+str(path))
        pending.append((path,result,dict(texture=name,segment=i,
                        rgba_sha256=hashlib.sha256(result.tobytes()).hexdigest())))
    for path,result,_ in pending:result.save(path)
    font_style.copy_license(target)
    metadata=dict(font_sha256=font_style.FONT_SHA256,source_captures=CAPTURES,
                  palette_format_salt=checked[0][3],textures=[m for _,_,m in pending],
                  verification='three captured hashes agree; new scene capture pending')
    (bizin_font.OUTPUT/'stock-pack.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print('Installed Bizin stock textures: '+', '.join(m['texture'] for _,_,m in pending))
    return metadata


if __name__=='__main__':install()
