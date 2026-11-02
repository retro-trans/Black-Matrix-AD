"""Localize BP requirement and Normal/Latent battle selectors."""
import struct
import json
import ui_upscale as ui
import patchline
import bmtext
import shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import house_layers as layers
import interface_redraw as pack
import native_translation_parity as native
import native_m6x11 as engine
import native_silver
import noto_font
import hd_silver_fallback as hd
import magic_spacing_fix as text_render
import inject

ROOT=ui.ROOT
OUT=ROOT/'build/attack-mode-labels-v1'
VARIANTS={'hd':('reusable-atlas-noto-ui-r35-hd-magic-panel-v1','reusable-atlas-noto-ui-r35-hd-attack-modes-v1'),
          'native':('reusable-atlas-noto-ui-r35-native-silver-miss-v1','reusable-atlas-noto-ui-r35-native-silver-attack-modes-v1')}
TEXTURE=0x1350
NAME='240fd9ad.png'
BASELINE='e7cf5723e47ad002b7ba3ad14008f014cc72d3de749392ab7b1898ec03202a17'
LABELS={93:('Normal',(112,64,144,80)),94:('Latent',(144,64,176,80)),
        163:('Normal',(0,224,32,240)),164:('Latent',(0,240,32,256))}
RECORD=0x8792A
RECORD_BEFORE=bytes.fromhex('0e00'+'4081'*8+'4b95769761826f82'+'4081'*2)

def patch_executable(before):
    if before[RECORD:RECORD+len(RECORD_BEFORE)]!=RECORD_BEFORE:raise ValueError('BP requirement record changed')
    if before[0x1DAF4:0x1DAF8]!=struct.pack('<I',0x8c010000+RECORD):raise ValueError('BP record pointer changed')
    after=bytearray(before)
    after[0x8793C:0x87944]=struct.pack('<4H',*(patchline.to_sjis(c) for c in ' BP:'))
    return bytes(after)

def artwork(index,is_hd):
    text,_=LABELS[index];scale=4 if is_hd else 1
    sizes=range(37,27,-1) if is_hd else range(19,10,-1)
    for size in sizes:
        font=ImageFont.truetype(str(noto_font.default_font() if is_hd else native_silver.FACE),size)
        box=font.getbbox(text);w,h=box[2]-box[0],box[3]-box[1]
        if w<=29*scale and h<=12*scale:break
    else:raise ValueError('Attack mode does not fit')
    mask=Image.new('L' if is_hd else '1',(32*scale,16*scale))
    ImageDraw.Draw(mask).text(((32*scale-w)//2-box[0],(16*scale-h)//2-box[1]),text,font=font,fill=255)
    color=(222,222,222) if index<160 else (49,49,49)
    art=Image.new('RGBA',mask.size,color+(0,));art.putalpha(mask.convert('L'))
    return art if is_hd else art.resize((128,64),Image.Resampling.NEAREST)

def patch_char(before):
    original=ui.japanese_audit.archive(1,'CHAR.DAT');ref,_=layers.page(original,TEXTURE);page,_=layers.page(before,TEXTURE)
    rows=pack.descriptors(before,TEXTURE);after=bytearray(before);allowed=set()
    for index,(_,rect) in LABELS.items():
        if rows[index]!=rect or page.crop(rect).tobytes()!=ref.crop(rect).tobytes():raise ValueError('Attack selector source differs')
        for pos,value in native.encode(before,TEXTURE,rect,artwork(index,False)):
            after[pos:pos+2]=value;allowed.update((pos,pos+1))
    delta=np.flatnonzero(np.frombuffer(before,dtype='u1')!=np.frombuffer(after,dtype='u1')).tolist()
    if not delta or any(i not in allowed for i in delta):raise ValueError('Unexpected CHAR changes')
    return bytes(after)

def text_pages():
    salt,color,_=hd.records.verified_palette(hd.DUMPS);pending={}
    # Original 14-cell template allocates 8/2/2/2 cells. Name and digits are
    # written separately by the game; only two static pairs change here.
    if hd.records.capacities(14)!=[8,2,2,2]:raise ValueError('Allocator layout changed')
    for font in hd.fonts():
        for text,capacity in [(' B',2),('P:',2),(' BP:',8),(' '*8+' BP:'+' '*2,32)]:
            low,high=text_render.render(text,capacity,font);key=hd.key(low,salt)
            im=Image.new('RGBA',high.size,color[:3]+(0,));im.putalpha(high)
            pending[key]=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return pending

def build():
    if OUT.exists() or any((ROOT/'build'/dst).exists() for _,dst in VARIANTS.values()):raise ValueError('Preserve existing build')
    protected={p.name:pack.sha(p.read_bytes()) for p in ui.TARGET.glob('*.png')}
    if protected[NAME]!=BASELINE:raise ValueError('Unreviewed current battle atlas')
    with Image.open(ui.TARGET/NAME) as im:before_hd=im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    high,changed=pack.compose(before_hd,[(rect,artwork(i,True),text) for i,(text,rect) in LABELS.items()])
    pending={NAME:high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)};reports=[]
    OUT.mkdir()
    for folder in ('textures','originals','upright'):(OUT/folder).mkdir()
    high.save(OUT/'upright'/NAME)
    for mode,(src,dst) in VARIANTS.items():
        source=ROOT/'build'/src;dest=ROOT/'build'/dst;dest.mkdir();mode_rows=[]
        for p in source.iterdir():
            if p.is_file() and p.suffix!='.json':shutil.copy2(p,dest/p.name)
        for disc,folder in ((1,'disc'),(2,'disc2')):
            track_name=f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
            old=source/folder/track_name;old_sha=engine.native.base.digest(old);archives=[];changes={}
            with old.open('rb') as f:
                for filename,patcher in [('1ST_READ.BIN',patch_executable)]+([('CHAR.DAT',patch_char)] if mode=='native' else []):
                    lba,size=inject.find(f,filename);before=inject._extent(f,lba,size);after=patcher(before)
                    if len(before)!=len(after):raise ValueError('Archive size changed')
                    delta=np.flatnonzero(np.frombuffer(before,dtype='u1')!=np.frombuffer(after,dtype='u1')).tolist()
                    changes.update({engine.raw_offset(lba,i):after[i] for i in delta});archives.append((filename,lba,before,after,delta))
                    if filename=='CHAR.DAT':
                        _,key=layers.page(after,TEXTURE);pending[key]=high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            shutil.copytree(source/folder,dest/folder);new=dest/folder/track_name
            with new.open('r+b') as f:
                for filename,lba,before,after,delta in archives:
                    for sector in sorted({i//2048 for i in delta}):
                        f.seek(engine.raw_offset(lba,sector*2048));f.write(after[sector*2048:(sector+1)*2048])
            engine.verify_track(old,new,changes)
            with new.open('rb') as f:
                for filename,lba,before,after,delta in archives:
                    if inject._extent(f,lba,len(after))!=after:raise ValueError('Readback failed')
                    stem,suffix=filename.rsplit('.',1);(dest/(filename if disc==1 else stem+'.disc2.'+suffix)).write_bytes(after)
            if engine.native.base.digest(old)!=old_sha:raise ValueError('Source changed')
            for p in (source/folder).iterdir():
                if p.name!=track_name and engine.native.base.digest(p)!=engine.native.base.digest(dest/folder/p.name):raise ValueError('Other track changed')
            row=dict(mode=mode,disc=disc,changed_bytes=len(changes),archives={n:len(d) for n,l,b,a,d in archives},track_sha256=engine.native.base.digest(new))
            reports.append(row);mode_rows.append(row);print(mode,disc,'verified',flush=True)
        (dest/'manifest.json').write_text(json.dumps(dict(status='verified-attack-mode-labels',variants=mode_rows),indent=2))
    for key,im in text_pages().items():
        if key in pending and pending[key].tobytes()!=im.tobytes():raise ValueError('HD collision')
        if (ui.TARGET/key).exists():
            with Image.open(ui.TARGET/key) as old:
                if old.convert('RGBA').tobytes()!=im.tobytes():raise ValueError('Existing BP label differs')
            continue
        pending[key]=im
    rows=[]
    for name,im in pending.items():
        original=(ui.TARGET/name).read_bytes() if (ui.TARGET/name).exists() else None
        if original is not None:
            if name!=NAME:raise ValueError('Unreviewed existing HD atlas')
            (OUT/'originals'/name).write_bytes(original)
        im.save(OUT/'textures'/name)
        rows.append(dict(texture=name,original_file_sha256=pack.sha(original) if original else None,output_file_sha256=pack.sha((OUT/'textures'/name).read_bytes())))
    report=dict(status='verified-attack-mode-labels',textures=rows,variants=reports,original_hd_hashes=protected,
        labels={i:t for i,(t,r) in LABELS.items()},bp_label=' BP:',record_count=14,record_pointer_unchanged=True,
        ability_and_cost_fields_unchanged=True,live_game_verified=False)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2))
    result=pack.apply(OUT)
    if any(pack.sha((ui.TARGET/n).read_bytes())!=sha for n,sha in protected.items() if n!=NAME):raise ValueError('Unrelated HD art changed')
    result.update(status='installed-attack-mode-labels',other_textures_preserved=len(protected)-1,live_game_verified=False)
    (OUT/'installation.json').write_text(json.dumps(result,indent=2))
    preview=Image.new('RGB',(560,220),'#302a24');draw=ImageDraw.Draw(preview)
    for x,is_hd in ((8,True),(288,False)):
        draw.text((x,4),'HD' if is_hd else 'Native Silver',fill='white')
        for j,index in enumerate(LABELS):
            im=artwork(index,is_hd);preview.paste(im,(x+(j%2)*136,24+(j//2)*80),im)
    preview.save(OUT/'preview.png');print(json.dumps(result))

def inspect():
    data=(ROOT/'build/reusable-atlas-noto-ui-r35-hd-magic-panel-v1/1ST_READ.BIN').read_bytes()
    for text in ('必要','通常','潜在'):
        needle=struct.pack('<%dH'%len(text),*(int.from_bytes(c.encode('cp932'),'big') for c in text))
        start=0
        while (pos:=data.find(needle,start))>=0:
            start=pos+2
            print(text,hex(pos),data[pos-20:pos+40].hex())
            print([bmtext.decode_char(w) for w in struct.unpack_from('<30H',data,pos-20)])
    for off in (0x8792a,0x8792c):
        needle=struct.pack('<I',0x8c010000+off);pos=0
        while (pos:=data.find(needle,pos))>=0:
            print('reference',hex(off),hex(pos));pos+=4

if __name__=='__main__':
    import sys
    build() if 'build' in sys.argv else inspect()
