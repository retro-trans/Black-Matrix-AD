"""Native/HD title-card localization across both original discs.

Only authenticated SCL descriptor tables and their allocated RGB565 pixels
change. Retiling keys include HD pixels, avoiding lossy native dedup collisions.
"""
import csv
import hashlib
import struct
import math
import shutil
from functools import lru_cache
from pathlib import Path

import xxhash
from PIL import Image,ImageDraw,ImageFont
import battle_intro_card
import chapter_cards
import cooking
import inject
import pvr_atlas
import seed_noto_pack

ROOT=cooking.ROOT
UI=ROOT/'script/ui/all_title_cards.tsv'
SCALE=4
FONT=chapter_cards.FONT
SALT=0x08000000
RECTS={
 'open':((152,66,492,114),(48,116,592,176)),
 'end':((20,10,450,56),(20,88,620,164),(508,188,636,232)),
 'battle':((20,12,400,66),(12,62,628,166),(12,166,640,240)),
}


def entries(disc=None,archive=None):
    with UI.open(encoding='utf-8-sig') as f:
        rows=list(csv.DictReader((s for s in f if not s.startswith('#')),delimiter='\t'))
    seen=set()
    for r in rows:
        r['disc']=int(r['disc']);r['offset']=int(r['offset'],0);r['end']=int(r['end'],0)
        key=(r['disc'],r['archive'],r['offset'])
        if key in seen or r['disc'] not in (1,2) or r['archive'] not in ('EVENT','MAP') or r['kind'] not in RECTS:
            raise ValueError('unknown or duplicate title card')
        seen.add(key)
    if len(rows)!=78 or sum(r['kind']=='open' for r in rows)!=12 or sum(r['kind']=='end' for r in rows)!=11:
        raise ValueError('incomplete title-card catalog')
    return [r for r in rows if (disc is None or r['disc']==disc) and (archive is None or r['archive']==archive)]


@lru_cache(maxsize=4)
def source(disc,archive):
    track=ROOT/('Black-Matrix Advanced (Japan) (Disc %d) (Track 3).bin'%disc)
    with track.open('rb') as f:
        lba,size=inject.find(f,archive+'.DAT')
        return inject._extent(f,lba,size)


def layout(original,row):
    o,end=row['offset'],row['end']
    if hashlib.sha256(original[o:end]).hexdigest()!=row['sha256']:
        raise ValueError('unknown source card: %s %X'%(row['archive'],o))
    cols,rows,descriptors,pages=pvr_atlas.scl_layout(original,o)
    if (cols,rows)!=(40,15) or pages[-1]+16+131072!=end:
        raise ValueError('card allocation changed')
    return descriptors,pages


def is_escape(row):
    return row['disc']==1 and row['archive']=='MAP' and row['offset']==battle_intro_card.SCL


@lru_cache(maxsize=1)
def paper():
    return pvr_atlas.decode_scl(source(1,'MAP'),battle_intro_card.SCL).crop((0,168,160,240))


@lru_cache(maxsize=32)
def face(size):return ImageFont.truetype(FONT,size*SCALE)


def caption(high,text,rect,size,color,align='center',max_lines=2):
    x,y,xx,yy=(n*SCALE for n in rect)
    for s in range(size,15,-1):
        font=face(s);lines=[];current=''
        for word in text.split():
            candidate=(current+' '+word).strip()
            if current and font.getlength(candidate)>xx-x-24*SCALE:
                lines.append(current);current=word
            else:current=candidate
        if current:lines.append(current)
        if len(lines)>max_lines or any(font.getlength(line)>xx-x-16*SCALE for line in lines):continue
        spacing=6*SCALE
        bbox=ImageDraw.Draw(high).multiline_textbbox((0,0),'\n'.join(lines),font=font,spacing=spacing,align=align)
        w,h=math.ceil(bbox[2]-bbox[0]+8),math.ceil(bbox[3]-bbox[1]+8)
        if h/2>yy-y-8*SCALE:continue
        layer=Image.new('RGBA',(w,h))
        ImageDraw.Draw(layer).multiline_text((4-bbox[0],4-bbox[1]),'\n'.join(lines),font=font,
            fill=color,spacing=spacing,align=align)
        layer=layer.resize((w,max(1,h//2)),Image.Resampling.LANCZOS)
        dx=x+8*SCALE if align=='left' else x+(xx-x-w)//2
        high.alpha_composite(layer,(dx,y+(yy-y-layer.height)//2))
        return
    raise ValueError('title does not fit: '+text)


def render(original,row):
    layout(original,row)
    if is_escape(row):return battle_intro_card.render(original)
    low=pvr_atlas.decode_scl(original,row['offset'])
    high=low.resize((2560,960),Image.Resampling.NEAREST).convert('RGBA')
    rects=RECTS[row['kind']];draw=ImageDraw.Draw(high)
    for rect in rects:
        x,y,xx,yy=(v*SCALE for v in rect)
        if row['kind']=='battle':
            fill=paper().resize((rect[2]-rect[0],rect[3]-rect[1]),Image.Resampling.BICUBIC)
            high.paste(fill.resize((xx-x,yy-y),Image.Resampling.NEAREST),(x,y))
            draw.rectangle((x,y,xx-1,yy-1),outline='#414141',width=4)
        else:
            draw.rectangle((x,y,xx-1,yy-1),fill='#100c0a' if row['kind']=='open' else 'black',
                           outline='#967962' if row['kind']=='open' else 'black',width=4)
    if row['kind']=='battle':
        caption(high,row['chapter'],(20,12,350,62),38,'#151515',max_lines=1)
        caption(high,row['title'],(16,64,624,124),44,'#151515')
        caption(high,'Victory Condition',(20,124,300,164),25,'#151515',max_lines=1)
        if row['objective']:caption(high,row['objective'],rects[2],36,'#151515')
    else:
        caption(high,row['chapter'],rects[0],44,'#dedede',align='left' if row['kind']=='end' else 'center',max_lines=1)
        caption(high,row['title'],rects[1],48,'#dedede')
        if row['kind']=='end':caption(high,'End',rects[2],44,'#dedede',max_lines=1)
    for rect in rects:
        crop=high.crop(tuple(v*SCALE for v in rect)).convert('RGB')
        low.paste(crop.resize((rect[2]-rect[0],rect[3]-rect[1]),Image.Resampling.LANCZOS),rect[:2])
    return low,high


def retile(data,row,low,high):
    _,_,_,pages=pvr_atlas.scl_layout(data,row['offset']);unique={};tiles=[];mapping=[]
    for i in range(600):
        x,y=i%40*16,i//40*16
        words=tuple(((r*31+127)//255)<<11|((g*63+127)//255)<<5|((b*31+127)//255)
                    for r,g,b in low.crop((x,y,x+16,y+16)).getdata())
        key=(words,high.crop((x*4,y*4,(x+16)*4,(y+16)*4)).tobytes())
        if key not in unique:unique[key]=len(tiles);tiles.append(words)
        page,local=divmod(unique[key],256);tx,ty=local//16*16,local%16*16
        mapping.append(ty|tx<<8|page<<16)
    if len(tiles)>len(pages)*256:raise ValueError('native/HD card exceeds allocated tiles')
    struct.pack_into('<600I',data,row['offset']+32,*mapping)
    for o in pages:data[o+16:o+16+131072]=bytes(131072)
    for i,words in enumerate(tiles):
        page,local=divmod(i,256);tx,ty=local//16*16,local%16*16
        for k,w in enumerate(words):
            struct.pack_into('<H',data,pages[page]+16+2*pvr_atlas.pixel_index(tx+k%16,ty+k//16),w)
    return len(tiles)


@lru_cache(maxsize=1)
def legacy_event():
    data=bytearray(source(1,'EVENT'));chapter_cards.patch(data);return data


def patch(data,disc,archive,previews=None):
    original=source(disc,archive);pending=[];metadata=[]
    if len(data)!=len(original):raise ValueError('archive size changed')
    for row in entries(disc,archive):
        _,pages=layout(original,row);o,end=row['offset'],row['end']
        low,high=render(original,row);expected=bytearray(original)
        if is_escape(row):count=battle_intro_card.patch(expected,original)['tiles']
        else:count=retile(expected,row,low,high)
        accepted=[original[o:end],expected[o:end]]
        if disc==1 and archive=='EVENT' and o in (chapter_cards.END_SCL,chapter_cards.OPEN_SCL):
            accepted.append(legacy_event()[o:end])
        if data[o:end] not in accepted:raise ValueError('unknown installed card at %X'%o)
        pending.append((o,end,expected[o:end]))
        metadata.append(dict(offset=o,kind=row['kind'],chapter=row['chapter'],title=row['title'],tiles=count,capacity=len(pages)*256))
        if previews:
            previews=Path(previews);previews.mkdir(parents=True,exist_ok=True)
            name='d%d-%s-%x'%(disc,archive.lower(),o)
            high.resize((1280,960),Image.Resampling.LANCZOS).save(previews/(name+'.png'))
    for o,end,payload in pending:data[o:end]=payload
    return metadata


def hd_pages(original,patched,row):
    layout(original,row);low,high=render(original,row)
    expected=bytearray(original)
    if is_escape(row):battle_intro_card.patch(expected,original)
    else:retile(expected,row,low,high)
    o,end=row['offset'],row['end']
    if patched[o:end]!=expected[o:end]:raise ValueError('noncanonical patched title card')
    cols,rows,descriptors,pages=pvr_atlas.scl_layout(patched,row['offset'])
    sheets=[Image.new('RGBA',(1024,1024),(0,0,0,255)) for _ in pages];seen={}
    for i,d in enumerate(descriptors):
        tile=high.crop((i%40*64,i//40*64,(i%40+1)*64,(i//40+1)*64))
        if d in seen and seen[d]!=tile.tobytes():raise ValueError('HD tile collision')
        seen[d]=tile.tobytes();sheets[d>>16].paste(tile,((d>>8&255)*4,(d&255)*4))
    for im,o in zip(sheets,pages):
        if patched[o+8:o+10]!=b'\x01\x01':raise ValueError('unsupported title pixel/hash format')
        name='%x.png'%(xxhash.xxh32(patched[o+16:o+16+131072],seed=7).intdigest()^SALT)
        yield im.transpose(Image.Transpose.FLIP_TOP_BOTTOM),dict(texture=name,disc=row['disc'],archive=row['archive'],offset=row['offset'])


def install_pack(archives):
    if set(archives)!={(1,'EVENT'),(1,'MAP'),(2,'EVENT'),(2,'MAP')}:
        raise ValueError('all four title archives are required')
    profile=ROOT/'build/stock-atlas-run/data'
    # Authenticate the RGB565 raw-hash convention using three whole captures.
    original=source(1,'MAP');escape=bytearray(original);battle_intro_card.patch(escape,original)
    battle_intro_card.prepare_pack(original,escape,profile/'texdump/T20101M')
    pending={};metadata=[]
    for (disc,archive),data in archives.items():
        for row in entries(disc,archive):
            for im,meta in hd_pages(source(disc,archive),data,row):
                name=meta['texture']
                if name in pending and pending[name].tobytes()!=im.tobytes():raise ValueError('title hash collision')
                pending[name]=im;metadata.append(meta)
    seed_noto_pack.write_pack(profile/'textures/T20101M',[(im,dict(texture=name)) for name,im in pending.items()])
    return dict(cards=78,textures=metadata,unique_pages=len(pending),scale=4,format_salt=SALT,
                verification='source blocks and RGB565 hash format authenticated; in-game verification pending')


def build_disc2(out,previews=None):
    """Separate original-disc copy: title cards only, never saves or originals."""
    disc=Path(out)/'disc2';disc.mkdir(parents=True,exist_ok=True)
    names=['Black-Matrix Advanced (Japan) (Disc 2).cue']+[
        'Black-Matrix Advanced (Japan) (Disc 2) (Track %d).bin'%i for i in (1,2,3)]
    for name in names:
        if not (disc/name).exists():shutil.copy2(ROOT/name,disc/name)
    track=disc/names[-1];archives={};metadata={}
    for archive in ('EVENT','MAP'):
        with track.open('rb') as f:
            lba,size=inject.find(f,archive+'.DAT');data=bytearray(inject._extent(f,lba,size))
        metadata[archive]=patch(data,2,archive,previews)
        payload=Path(out)/(archive+'.disc2.DAT');payload.write_bytes(data)
        inject.put(str(track),archive+'.DAT',str(payload))
        with track.open('rb') as f:
            lba,size=inject.find(f,archive+'.DAT')
            if inject._extent(f,lba,size)!=data:raise ValueError('Disc 2 readback failed')
        archives[(2,archive)]=data
    return archives,dict(cue=str(disc/names[0]),scope='Title cards only; other Disc 2 content remains original',cards=metadata)
