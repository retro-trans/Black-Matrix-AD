"""Port Rayblade's verified Skies bitmap into Black Matrix's native font."""
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import inject
import latin
import fontdump
import vwf
import reusable_atlas as atlas
import bmtext
import patchline

RAYBLADE = Path('E:/Projects/Seireiki Rayblade')
ASSETS = ROOT/'assets/fonts/skies-rayblade'
SOURCE = ROOT/'build/disc2-hd-story-name-fixes-v1'
OUT = ROOT/'build/skies-rayblade-font-v1'
SOURCE_HASH = '3adb4e51d75bf9f98a27a028aef86ccb8b7de52246d70827ff6d60107d0b5487'
RAY_FONT_HASH = '5fe1480136b8c7d2bb15a32b17588edc0459fcf9c1079c9aa4b1075e11a4d181'
FONT_OFFSET = 0x424E0
LEVELS = (0, 85, 187, 255)
PALETTE = ((0,0,0,0), (198,231,231,255), (156,156,156,255), (74,74,74,255))
TRACK = 'Black-Matrix Advanced (Japan) (Disc 2) (Track 3).bin'


def sha(data): return hashlib.sha256(data).hexdigest()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_file(track, name):
    with track.open('rb') as stream:
        lba, size = inject.find(stream, name)
        return inject._extent(stream, lba, size), lba


def source_bitmap():
    # Freeze only font assets locally. Do not import or execute the other task.
    if (ASSETS/'rayblade-skies-font.bin').exists():
        bitmap=ASSETS/'skies-embedded-latin.png'
        cached=json.loads((ASSETS/'provenance.json').read_text())
        proof=dict(target_font_sha256=cached['rayblade_font_sha256'],
                   source_skies_executable_sha256=cached['original_skies_executable_sha256'])
        font=(ASSETS/'rayblade-skies-font.bin').read_bytes()
        if digest(bitmap)!=cached['source_png_sha256']:
            raise ValueError('Copied source bitmap differs')
    else:
        bitmap = RAYBLADE/'work/ui/skies-font-comparison/skies-embedded-latin.png'
        proof = json.loads((RAYBLADE/'work/output/skies-font-draft-01/component-report.json').read_text())
        archive = (RAYBLADE/'work/output/0.1.40/WIN00.AFS').read_bytes()
        offset, size = struct.unpack_from('<II', archive, 8)
        font = archive[offset:offset+size]
    if sha(font) != RAY_FONT_HASH or proof['target_font_sha256'] != RAY_FONT_HASH:
        raise ValueError('Rayblade font differs from the verified Skies source')
    with Image.open(bitmap) as image:
        image = image.convert('L')
    if image.size == (1152,216):
        native = image.resize((384,72),Image.Resampling.NEAREST)
        if native.resize(image.size,Image.Resampling.NEAREST).tobytes()!=image.tobytes():
            raise ValueError('Source inspection sheet is not an exact 3x bitmap')
        image = native
    if image.size != (384,72) or not set(image.getdata()) <= set(LEVELS):
        raise ValueError('Unknown Skies bitmap dimensions or coverage')
    # Pixel-for-pixel proof against the actual installed Rayblade small bank.
    glyphs = {}
    for code in range(32,127):
        i = code-32; glyph = image.crop((i%32*12, i//32*24, i%32*12+12, i//32*24+24))
        box = glyph.getbbox(); left = box[0] if box else 0
        expected = Image.new('L', (64,32)); expected.paste(glyph,(4-left,4))
        actual = Image.new('L', (64,32))
        for y in range(32):
            for half in range(2):
                word = struct.unpack_from('<I', font, 0x200+i*256+y*8+half*4)[0]
                for x in range(16):
                    actual.putpixel((half*16+x,y), LEVELS[(word>>(30-2*x))&3])
        if actual.tobytes() != expected.tobytes():
            raise ValueError('Rayblade source pixels differ for '+repr(chr(code)))
        glyphs[chr(code)] = glyph
    provenance = dict(source_project=str(RAYBLADE), source_version='0.1.39, retained in 0.1.40',
                      rayblade_font_sha256=RAY_FONT_HASH,
                      original_skies_executable_sha256=proof['source_skies_executable_sha256'],
                      source_png_sha256=digest(bitmap), source_pixels_sha256=sha(image.tobytes()),
                      verified_ascii_glyphs=95, source_cell=[12,24], levels=LEVELS,
                      target_cell=[32,16], target_bitmap=[16,16],
                      method='Same global 4/3 display scale for the entire face; 16x16 source raster compensates Black Matrix 2x vertical display stretch. BOX sampling, nearest native shade; no per-letter stretching or outline reconstruction.',
                      distribution='Private local test; source game bitmap retained locally only')
    return bitmap, glyphs, provenance, font


def snapshot_source(bitmap,provenance,font):
    ASSETS.mkdir(parents=True,exist_ok=True)
    for path,payload in ((ASSETS/'skies-embedded-latin.png',bitmap.read_bytes()),
                         (ASSETS/'rayblade-skies-font.bin',font),
                         (ASSETS/'provenance.json',(json.dumps(provenance,indent=2)+'\n').encode())):
        if path.exists() and path.read_bytes()!=payload:raise ValueError('Existing font asset differs')
        if not path.exists():path.write_bytes(payload)


def cell(font, index):
    image=Image.new('L',(32,16))
    image.putdata([fontdump.pixel(font,0,index,x,y) for y in range(16) for x in range(32)])
    return image


def encoded(image):
    record=latin.blank_record()
    for y in range(16):
        for x in range(32): latin.set_pixel(record,x,y,int(image.getpixel((x,y))))
    return bytes(record)


def patch(exe, system, glyphs):
    a = atlas.build_code(); a.assemble()
    def renderer(width):
        return vwf.build_code(a.labels['slot_hook'], ui_fixes=True,
            natural_font=True, pixel_aspect_lut=atlas.FORWARD,
            main_menu_padding=4, stance_menu_padding=4, dialogue_space_extra=4,
            latin_quad_width=width).assemble()
    old_code, new_code = renderer(56), renderer(28)
    start = vwf.CODE-vwf.LOAD_BASE
    if exe[start:start+len(old_code)] != old_code or len(old_code)!=len(new_code):
        raise ValueError('Unknown complete HD renderer')
    differences=[i for i,(x,y) in enumerate(zip(old_code,new_code)) if x!=y]
    if len(differences)!=1 or (old_code[differences[0]],new_code[differences[0]])!=(56,28):
        raise ValueError('Unexpected native quad change')
    before = system[FONT_OFFSET:FONT_OFFSET+fontdump.FONT_LEN]
    if len(before)!=fontdump.FONT_LEN or before[:16]!=(ROOT/'extracted/FONT.BIN').read_bytes()[:16]:
        raise ValueError('Unknown embedded font')
    font=bytearray(before); result=bytearray(exe); result[start:start+len(new_code)]=new_code
    metrics={}; seen={}; edited=set()
    for ch,index in {' ':0, **latin.charmap()}.items():
        if index in seen:
            metrics[ch]=metrics[seen[index]];continue
        seen[index]=ch
        if exe[vwf.BEAR_TAB-vwf.LOAD_BASE+index]!=0:
            raise ValueError('Unexpected font bearing')
        if ch==' ':
            pixels=cell(before,0); advance=6
        elif ch in glyphs:
            # Uniform display aspect, one common baseline; retain original bitmap shapes.
            small=glyphs[ch].resize((16,16),Image.Resampling.BOX)
            box=small.getbbox()
            if box is None:raise ValueError('Missing source glyph '+repr(ch))
            image=Image.new('L',(32,16)); image.paste(small, (1-box[0],0))
            coverage=np.asarray(image).astype('i2')
            nearest=np.abs(coverage[:,:,None]-np.array(LEVELS)).argmin(axis=2)
            pixels=Image.fromarray(np.array((0,3,2,1),dtype='u1')[nearest])
            advance=box[2]-box[0]+2
        else:
            # Skies has no curly-quote/dash/ellipsis bank. Preserve those existing
            # shapes at their prior screen width when switching Latin quads to 1:1.
            original=cell(before,index)
            pixels=original.resize((64,16),Image.Resampling.NEAREST).crop((0,0,32,16))
            if original.getbbox() and original.getbbox()[2]*2>28:
                raise ValueError('Fallback mark would clip '+repr(ch))
            advance=exe[vwf.ADV_TAB-vwf.LOAD_BASE+index]
        bounds=pixels.getbbox()
        if bounds and bounds[2]>28:raise ValueError('Native glyph exceeds quad')
        off=16+index*128; font[off:off+128]=encoded(pixels)
        result[vwf.ADV_TAB-vwf.LOAD_BASE+index]=advance
        metrics[ch]=dict(index=index,advance=advance,ink=bounds,source='Skies' if ch in glyphs else 'prior punctuation')
        edited.add(index)
    # Keep the two transformed names consistent with the new ASCII face.
    for name,slots in (('Gabriel',range(317,322)),('Metatron',range(322,327))):
        word=Image.new('L',(256,16)); pen=0
        for ch in name:
            glyph=cell(font,latin.charmap()[ch]); layer=Image.new('L',word.size);layer.paste(glyph,(pen,0))
            word=Image.fromarray(np.maximum(np.array(word),np.array(layer)))
            pen+=metrics[ch]['advance']
        width=math.ceil(max(pen,word.getbbox()[2])/5)
        if width>28:raise ValueError('Transformed name exceeds original quads')
        for i,index in enumerate(slots):
            pixels=Image.new('L',(32,16));pixels.paste(word.crop((i*width,0,(i+1)*width,16)))
            font[16+index*128:16+(index+1)*128]=encoded(pixels)
            result[vwf.ADV_TAB-vwf.LOAD_BASE+index]=width;edited.add(index)
    after_system=system[:FONT_OFFSET]+bytes(font)+system[FONT_OFFSET+len(font):]
    allowed_exe={start+differences[0]} | {vwf.ADV_TAB-vwf.LOAD_BASE+i for i in edited}
    if any(x!=y and i not in allowed_exe for i,(x,y) in enumerate(zip(exe,result))):
        raise ValueError('Undeclared executable change')
    allowed_font={byte for index in edited for byte in range(16+index*128,16+(index+1)*128)}
    if any(x!=y and i not in allowed_font for i,(x,y) in enumerate(zip(before,font))):
        raise ValueError('Undeclared font change')
    return bytes(result),after_system,bytes(font),metrics,edited


def audit_scenario(data, old_exe, new_exe):
    maximum=0; count=0; regressions=[]
    reverse={patchline.to_sjis(c):c for c in {' ':0,**latin.charmap()}}
    reverse[patchline.LINE_BREAK]='\n'
    for offset,kind,_,_ in bmtext.strings(data):
        if kind not in ('TALK','NARR'):continue
        units=struct.unpack_from('<H',data,offset+2)[0]
        words=struct.unpack_from('<%dH'%units,data,offset+4)
        if not all(word in reverse for word in words):continue
        text=''.join(reverse[word] for word in words)
        rows=[];row=''
        for c in text:
            if c=='\n' or len(row)==33:
                rows.append(row.rstrip());row=''
                if c=='\n':continue
            row+=c
        if row.strip():rows.append(row.rstrip())
        for row in rows:
            def width(exe):
                return sum(exe[vwf.ADV_TAB-vwf.LOAD_BASE+(0 if c==' ' else latin.charmap()[c])]
                           +(4 if c==' ' else 0) for c in row)
            old,new=width(old_exe),width(new_exe);count+=1; maximum=max(maximum,new)
            if new>476:regressions.append(dict(offset=offset,width=new,prior=old))
    if regressions:raise ValueError('New font exceeds dialogue width: '+repr(regressions[:4]))
    return dict(rows_checked=count,maximum_width=maximum,limit=476,overflow=0,
                wording_and_controls_unchanged=True)


def render_line(font,exe,text,doubled):
    canvas=Image.new('RGBA',(536,32));pen=0
    for ch in text:
        index=0 if ch==' ' else latin.charmap()[ch]
        glyph=cell(font,index)
        tile=Image.new('RGBA',glyph.size);tile.putdata([PALETTE[p] for p in glyph.getdata()])
        tile=tile.resize((64 if doubled else 32,32),Image.Resampling.NEAREST)
        canvas.alpha_composite(tile,(pen,0))
        pen+=exe[vwf.ADV_TAB-vwf.LOAD_BASE+index]+(4 if ch==' ' else 0)
    return canvas


def preview(old_font,new_font,old_exe,new_exe):
    lines=['Beyond this hill is Pandemonium,','The person dear to this fellow,',
           'who was caught by the Inquisitor','for talking about love...',
           'Abel   Status   Ritual   Gabriel','Il1 O0 rn m  gypq  AVW 0123456789']
    image=Image.new('RGB',(1090,1000),'#100e09');draw=ImageDraw.Draw(image)
    for section,(font,exe,doubled,label) in enumerate(((old_font,old_exe,True,'Current embedded Silver fallback'),
            (new_font,new_exe,False,'Skies bitmap copied from Rayblade - native game pixels'))):
        y=section*495+12;draw.text((12,y),label,fill='white')
        for i,text in enumerate(lines):
            line=render_line(font,exe,text,doubled).resize((1072,64),Image.Resampling.NEAREST)
            image.paste(line,(8,y+28+i*70),line)
    image.save(OUT/'comparison.png')


def copy_track(old,new,expected,changes):
    before=hashlib.sha256();after=hashlib.sha256();position=0
    ordered=sorted(changes);cursor=0
    with old.open('rb') as src,new.open('xb') as dst:
        while chunk:=src.read(4*1024*1024):
            before.update(chunk); modified=bytearray(chunk)
            while cursor<len(ordered) and ordered[cursor]<position+len(chunk):
                offset=ordered[cursor];modified[offset-position]=changes[offset];cursor+=1
            dst.write(modified);after.update(modified);position+=len(chunk)
    if before.hexdigest()!=expected or cursor!=len(ordered) or digest(new)!=after.hexdigest():
        raise ValueError('Disc source or readback hash differs')
    # Independent exact-delta scan, including raw sector metadata and other archives.
    cursor=0;position=0
    with old.open('rb') as a,new.open('rb') as b:
        while chunk:=a.read(4*1024*1024):
            actual=b.read(len(chunk))
            for i in np.flatnonzero(np.frombuffer(chunk,dtype='u1')!=np.frombuffer(actual,dtype='u1')):
                offset=position+int(i)
                if cursor>=len(ordered) or offset!=ordered[cursor] or actual[i]!=changes[offset]:
                    raise ValueError('Unexpected raw-track difference')
                cursor+=1
            position+=len(chunk)
    if cursor!=len(changes):raise ValueError('Missing raw-track differences')
    return after.hexdigest()


def build():
    if OUT.exists():raise ValueError('Preserve existing font port')
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    if manifest['track_sha256']!=SOURCE_HASH:raise ValueError('Unexpected complete Disc 2 source')
    bitmap,glyphs,provenance,source_font=source_bitmap()
    old=SOURCE/'disc2'/TRACK
    if digest(old)!=SOURCE_HASH:raise ValueError('Source disc hash differs')
    exe,lba_exe=read_file(old,'1ST_READ.BIN');system,lba_system=read_file(old,'SYSTEM.DAT')
    after_exe,after_system,font,metrics,edited=patch(exe,system,glyphs)
    scenario,_=read_file(old,'SCENARIO.DAT')
    audit=audit_scenario(scenario,exe,after_exe)
    OUT.mkdir();snapshot_source(bitmap,provenance,source_font)
    preview(system[FONT_OFFSET:FONT_OFFSET+fontdump.FONT_LEN],font,exe,after_exe)
    (OUT/'FONT.bin').write_bytes(font)
    changes={};counts={}
    for name,lba,before,after in (('1ST_READ.BIN',lba_exe,exe,after_exe),('SYSTEM.DAT',lba_system,system,after_system)):
        offsets=np.flatnonzero(np.frombuffer(before,dtype='u1')!=np.frombuffer(after,dtype='u1'))
        counts[name]=len(offsets)
        changes.update({(lba-inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i] for i in offsets.tolist()})
    folder=OUT/'disc2';folder.mkdir()
    digest_out=copy_track(old,folder/old.name,SOURCE_HASH,changes)
    for name,expected in (('1ST_READ.BIN',after_exe),('SYSTEM.DAT',after_system),('SCENARIO.DAT',scenario)):
        if read_file(folder/old.name,name)[0]!=expected:raise ValueError('Archive readback differs: '+name)
    import shutil
    for path in old.parent.iterdir():
        if path.is_file() and path!=old:
            shutil.copy2(path,folder/path.name)
            if digest(path)!=digest(folder/path.name):raise ValueError('Companion file differs')
    if digest(old)!=SOURCE_HASH:raise ValueError('Source disc changed')
    report=dict(status='verified-skies-rayblade-font',disc=2,
        source=str(SOURCE.relative_to(ROOT)).replace('\\','/'),source_sha256=SOURCE_HASH,
        track_sha256=digest_out,font_sha256=sha(font),font_source=provenance,
        changed_bytes=counts,mapped_characters=len(metrics),glyph_records_changed=len(edited),
        renderer_change='Single width immediate 56 -> 28; unchanged UVs, row pitch and node allocations',
        display_scale=4/3,metrics=[dict(character=c,**row) for c,row in metrics.items()],dialogue_audit=audit,
        originals_and_other_disc_bytes_preserved=True,hd_texture_files_changed=0,
        live_game_verified=False,distribution='Private/local only',
        limitations=['Black Matrix 16-row font grid requires vertical resampling from the original 24 rows.',
                    'Uses existing four native color shades; source alpha is mapped to those shades.',
                    'This build targets the latest retained complete Disc 2. Older Disc 1 build artifacts are absent.'])
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('metrics','font_source')},indent=2),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['--snapshot-source']:
        bitmap,_,proof,font=source_bitmap();snapshot_source(bitmap,proof,font)
        print('Verified font copied to',ASSETS)
    elif sys.argv[1:]:raise SystemExit('Usage: skies_rayblade_font.py [--snapshot-source]')
    else:build()
