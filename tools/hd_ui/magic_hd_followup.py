"""Audit captured spell-name and Range/Area fallback font sheets."""
import sys,json,shutil
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import font_record_pack as records
import generate
import ui_upscale as ui
import fallback_font_pack as fallback
import magic_label_size as labels

OUT=ui.ROOT/'build/magic-hd-followup-v1'
PACK=OUT/'pack'
SPELLS={'b788d90c.png':'Zombify ','d4cee333.png':'ZombBomb','f633678d.png':'LumCross'}
AREA='95c9cc6c.png'

def dictionary():
    data=records.noto_font.NATIVE.read_bytes();chars={bytes(512):' '}
    for ch in records.noto_font.latin.charmap():
        glyph=generate.native_glyph(data,ch)
        if glyph:chars.setdefault(glyph[1].tobytes(),ch)
    return chars

def decode(im,chars):
    if im.width not in (32,64,128,256) or im.width!=im.height:return None
    alpha=im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).getchannel('A')
    text=''
    for i in range(im.width*im.height//512):
        x,y=records.pack.cell(i);key=alpha.crop((x,y,x+32,y+16)).tobytes()
        if key not in chars:return None
        text+=chars[key]
    return text

def discover():
    chars=dictionary();found=[]
    for p in ui.DUMPS.glob('*.png'):
        with Image.open(p) as im:text=decode(im,chars)
        if text and any(w in text for w in ('Zomb','LumC','Area','Range')):
            row=dict(texture=p.name,text=text,installed=(ui.TARGET/p.name).exists())
            found.append(row);print(row,flush=True)
    return found

def prepare():
    if OUT.exists():raise ValueError('Refusing to overwrite prepared pack')
    chars=dictionary();glyphs=fallback.dictionary()
    salt,color,sources=records.verified_palette(ui.DUMPS)
    pending=[]
    for name,expected in {**SPELLS,AREA:'  Area 8'}.items():
        with Image.open(ui.DUMPS/name) as im:
            dump=im.convert('RGBA');actual=decode(dump,chars)
        if actual!=expected:raise ValueError('Unexpected captured text: '+name)
        native=dump.transpose(Image.Transpose.FLIP_TOP_BOTTOM).getchannel('A').point(lambda a:1 if a else 0)
        key='%x.png'%(records.xxhash.xxh32(records.twiddled(native),seed=7).intdigest()^salt)
        if key!=name:raise ValueError('Captured font hash convention differs')
        path=ui.TARGET/name
        if name in SPELLS:
            if path.exists():raise ValueError('Spell HD atlas already exists; review required')
            after=fallback.replacement(dump,glyphs)
            if after is None:raise ValueError('Unmatched spell font pixels')
        else:
            with Image.open(path) as im:before=im.convert('RGBA')
            upright=before.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            # Only slots 2..5 are Area. The trailing 8 and all other cells
            # are independent consumers and remain byte-identical.
            alpha=upright.getchannel('A');small=labels.word_mask('Area')
            for slot in range(2,6):
                x,y=records.pack.cell(slot)
                alpha.paste(0,(x*4,y*4,x*4+128,y*4+64))
            x,y=records.pack.cell(2);alpha.paste(small,(x*4,y*4))
            upright.putalpha(alpha)
            after=upright.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        pending.append((name,after,actual))
    # The new Area must match the currently installed compact Range style.
    with Image.open(ui.TARGET/'15e8ff7e.png') as im:
        range_alpha=im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).getchannel('A')
    if range_alpha.crop((0,0,128,64)).tobytes()!=labels.word_mask('Range').tobytes():
        raise ValueError('Range label no longer uses the expected compact style')
    (PACK/'textures').mkdir(parents=True);(PACK/'originals').mkdir()
    entries=[]
    for name,after,text in pending:
        path=ui.TARGET/name;dest=PACK/'textures'/name
        if path.exists():shutil.copy2(path,PACK/'originals'/name)
        after.save(dest)
        entries.append(dict(texture=name,decoded_text=text,
                            original_file_sha256=ui.digest(path.read_bytes()) if path.exists() else None,
                            output_file_sha256=ui.digest(dest.read_bytes()),
                            capture_sha256=ui.digest((ui.DUMPS/name).read_bytes())))
    report=dict(textures=entries,palette_format_salt=salt,palette_sources=sources,
                label_font_size=labels.SIZE,scope='Three spell-name sheets and Area word only; game/native data unchanged',
                in_game_verified=False)
    (PACK/'manifest.json').write_text(json.dumps(report,indent=2))
    preview(pending);print(json.dumps(report,indent=2))

def preview(pending):
    sheet=Image.new('RGB',(650,350),'#13100a');draw=ImageDraw.Draw(sheet)
    draw.text((8,8),'HD spell names / matching Range and Area — offline preview',fill='white')
    advances=records.noto_font.advances()
    for row,(name,after,text) in enumerate(pending):
        atlas=after.transpose(Image.Transpose.FLIP_TOP_BOTTOM);left=8
        for slot,ch in enumerate(text):
            if name==AREA and slot not in range(2,6):continue
            x,y=records.pack.cell(slot);tile=atlas.crop((x*4,y*4,x*4+112,y*4+64))
            sheet.paste(tile,(left,30+row*75),tile);left+=advances[ch]*4
    with Image.open(ui.TARGET/'15e8ff7e.png') as im:
        atlas=im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    tile=atlas.crop((0,0,112,64));sheet.paste(tile,(350,255),tile)
    sheet.save(OUT/'preview.png')

def install():
    import house_composite as composite
    composite.OUT=OUT;composite.PACK=PACK;composite.install()
    path=OUT/'installation.json';report=json.loads(path.read_text())
    report.update(status='installed-magic-hd-followup',in_game_verified=False)
    path.write_text(json.dumps(report,indent=2))

if __name__=='__main__':
    if '--discover' in sys.argv:discover()
    elif '--install' in sys.argv:install()
    else:prepare()
