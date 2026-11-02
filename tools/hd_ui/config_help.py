"""English config/help text and Noto sprites; no settings or navigation writes.

Config sprites use 1x screen X and 2x displayed Y. Render in display space,
then encode that fixed pixel aspect into each original UV rectangle. Do not
fit/squeeze words individually or alter the PVX/selector geometry.
"""
import csv
import hashlib
import json
import struct

from PIL import Image, ImageDraw, ImageFont
import noto_font
import config_load_ui
import cooking
import patchline
import pvr_atlas
import seed_noto_pack
import uistr
import xxhash

ROOT = noto_font.ROOT
UI = ROOT/'script/ui/config_help.tsv'
PVX = 0x629040
PAGES = (0x6294D0,0x6494F0)
CAPTURES = ('bbbb0a8f.png','56f04294.png')
SOURCE_HASHES = ('b5c2ad0ab7ed63eb58f1b375dac7258ea6acdc864c66118cbb2cb12295b6d483',
                 '174d9d676482eb8fdb6fef59d3b795f9fc0966f8cccc0cd7d14c0ea37d33e052')
SCALE, SIZE, BASELINE, LEFT = 4, 10, 11.75, 2
SPRITES = ((0,17,'show'),(0,18,'hide'),(0,19,'manual'),(0,20,'defaults'),
           (1,40,'heading'),(1,45,'show'),(1,46,'hide')) + tuple(
    (1,47+i,k) for i,k in enumerate(('shop','status','items','ritual','exit','deploy',
        'arrange','assign_bp','placement','move','attack','magic','tools','refill',
        'stance','summon','victory','level_up')))
# Count-word offsets, original counts, translation keys. All records remain
# in place; context-specific widths and callbacks are never changed.
RECORDS = ((0x8831E,14,'stereo_desc'),(0x8833C,14,'mono_desc'),
           (0x8835A,11,'music_off_desc'),(0x88372,13,'music_low_desc'),
           (0x8838E,13,'music_mid_desc'),(0x883AA,13,'music_high_desc'),
           (0x883C6,12,'voice_on_desc'),(0x883E0,12,'voice_off_desc'),
           (0x883FA,11,'sound_on_desc'),(0x88412,11,'sound_off_desc'),
           (0x88514,34,'shop_desc'),(0x8855A,32,'status_desc'),
           (0x8859C,34,'items_desc'),(0x885E2,32,'ritual_desc'),
           (0x88624,32,'exit_desc'),(0x88666,32,'deploy_desc'),
           (0x886A8,21,'arrange_desc'),(0x886D4,25,'assign_bp_desc'),
           (0x88708,25,'placement_desc'),(0x8873C,20,'move_desc'),
           (0x88766,20,'attack_desc'),(0x88790,20,'magic_desc'),
           (0x887BA,20,'tools_desc'),(0x887E4,20,'refill_desc'),
           (0x8880E,21,'stance_desc'),(0x8883A,21,'summon_desc'),
           (0x88866,15,'victory_desc'),(0x88886,17,'level_up_desc'),
           (0x888AA,14,'back_desc'))


def strings():
    return cooking.strings(UI)


def padded(text,count):
    rows=text.split('\\n')
    if len(rows)>2 or any(len(row)>19 for row in rows):
        raise ValueError('config help exceeds two 19-cell rows')
    result=''.join(row.ljust(19) for row in rows[:-1])+rows[-1]
    if len(result)>count:
        raise ValueError('config help exceeds its original record capacity')
    return result.ljust(count)


def records():
    text=strings()
    return [padded(text[key],count) for _,count,key in RECORDS]


def patch_executable(data):
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    with UI.open(encoding='utf-8') as stream:
        sources={r['id']:r['japanese'] for r in csv.DictReader(
            (line for line in stream if not line.startswith('#')),delimiter='\t')}
    normalize=lambda s:s.replace('\u3000','').replace('\n','')
    pending=[]
    for (offset,count,key),text in zip(RECORDS,records()):
        _,n,japanese=next(uistr.walk(original,offset,1))
        if n!=count or normalize(japanese)!=normalize(sources[key]):
            raise ValueError('unknown original config help record at %X'%offset)
        encoded=struct.pack('<%dH'%count,*(patchline.to_sjis(c) for c in text))
        source=original[offset:offset+2+count*2]
        target=struct.pack('<H',count)+encoded
        if data[offset:offset+len(source)] not in (source,target):
            raise ValueError('unknown config help text at %X'%offset)
        pending.append((offset+2,encoded))
    for offset,payload in pending:data[offset:offset+len(payload)]=payload
    return dict(records=len(pending),columns=19,rows=2,
                scope='fixed text records only; counts, pointers and settings untouched')


def labels():
    source=(ROOT/'extracted/SYSTEM.DAT').read_bytes();text=strings();result=[]
    font_path=noto_font.default_font()
    faces={size:ImageFont.truetype(str(font_path),round(size*2*SCALE))
           for size in (SIZE,noto_font.SIZE)}
    for page,sprite,key in SPRITES:
        rect=config_load_ui.sprite_rect(source,PVX,sprite,expected_page=page)
        w,h=rect[2]-rect[0],rect[3]-rect[1]
        size=noto_font.SIZE if key=='heading' else SIZE
        # Draw at final-display proportions; the fixed 2:1 display transform
        # is the same for every word. Leave the face's X advances unmodified.
        face=faces[size]
        probe=Image.new('L',(2048,256))
        ImageDraw.Draw(probe).text((LEFT*SCALE,BASELINE*2*SCALE),
                                  text[key],font=face,fill=255,anchor='ls')
        box=probe.getbbox()
        if not box or box[0]<LEFT*SCALE or box[1]<0 or box[2]>(w-1)*SCALE or box[3]>=h*2*SCALE:
            raise ValueError('config caption does not fit original sprite: '+key)
        display=probe.crop((0,0,w*SCALE,h*2*SCALE))
        mask=display.resize((w*SCALE,h*SCALE),Image.Resampling.LANCZOS)
        result.append((page,sprite,rect,mask))
    return result


def previous_system():
    """Only the pre-existing captions on these two pages, not unrelated art."""
    data=bytearray((ROOT/'extracted/SYSTEM.DAT').read_bytes())
    text=cooking.strings(config_load_ui.UI)
    for sprite,key in ((17,'show'),(18,'hide'),(19,'manual'),(20,'defaults')):
        config_load_ui.paint(data,PAGES[0],config_load_ui.sprite_rect(data,PVX,sprite),
                             text[key],(255,255,255))
    config_load_ui.paint(data,PAGES[1],config_load_ui.sprite_rect(data,PVX,56,1),
                         text['move_heading'],(255,255,255))
    return data


def pixel_sites(page,rect):
    x,y,xx,yy=rect
    return [PAGES[page]+16+2*pvr_atlas.pixel_index(col,row)
            for row in range(y,yy) for col in range(x,xx)]


def patch_system(data):
    original=(ROOT/'extracted/SYSTEM.DAT').read_bytes();previous=previous_system()
    if data[PVX:PVX+48+66*16]!=original[PVX:PVX+48+66*16]:
        raise ValueError('config sprite descriptors changed')
    for page in PAGES:
        if data[page:page+16]!=original[page:page+16]:
            raise ValueError('config texture header changed')
    pending=[]
    for page,sprite,rect,mask in labels():
        w,h=rect[2]-rect[0],rect[3]-rect[1]
        low=mask.resize((w,h),Image.Resampling.LANCZOS)
        values=[]
        for level in low.getdata():
            c=level*31//255
            values.append(struct.pack('<H',0x8000|(c<<10)|(c<<5)|c if level>=64 else 0))
        sites=pixel_sites(page,rect)
        current=b''.join(data[o:o+2] for o in sites)
        target=b''.join(values)
        allowed=[b''.join(src[o:o+2] for o in sites) for src in (original,previous)]
        if current not in (*allowed,target):
            raise ValueError('unknown config caption pixels for sprite %d'%sprite)
        pending.extend(zip(sites,values))
    for offset,value in pending:data[offset:offset+2]=value
    return dict(labels={str(i):strings()[k] for _,i,k in SPRITES},
                font_size=SIZE,heading_font_size=noto_font.SIZE,
                display_y_scale=2,scope='25 caption rectangles only; PVX and controls unchanged')


def decoded(data,page):
    image=pvr_atlas.decode(data,PAGES[page])
    image.putdata([tuple(((v*31+127)//255<<3 | (v*31+127)//255>>2) for v in p[:3])+(p[3],)
                   for p in image.getdata()])
    return image


def raw_hash(data,page):
    offset=PAGES[page]+16
    return '%x.png'%xxhash.xxh32(data[offset:offset+131072],seed=7).intdigest()


def prepare_pack(patched,captures):
    source=bytearray(patched);previous=previous_system()
    for page,_,rect,_ in labels():
        for o in pixel_sites(page,rect):source[o:o+2]=previous[o:o+2]
    check=bytearray(source);patch_system(check)
    if check!=patched:raise ValueError('unknown patched config captions')
    pending=[]
    for page,capture in enumerate(captures):
        native=decoded(source,page)
        pixels=capture.convert('RGBA')
        if (pixels.size!=(256,256) or hashlib.sha256(pixels.tobytes()).hexdigest()!=SOURCE_HASHES[page]
                or pixels.tobytes()!=native.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
                or raw_hash(source,page)!=CAPTURES[page]):
            raise ValueError('config capture does not match verified source')
        high=native.resize((1024,1024),Image.Resampling.NEAREST)
        for p,_,rect,mask in labels():
            if p!=page:continue
            label=Image.new('RGBA',mask.size,(255,255,255,0));label.putalpha(mask)
            high.paste(label,(rect[0]*SCALE,rect[1]*SCALE))
        pending.append((high.transpose(Image.Transpose.FLIP_TOP_BOTTOM),dict(
            texture=raw_hash(patched,page),source=CAPTURES[page],source_rgba_sha256=SOURCE_HASHES[page])))
    return pending


def install_pack(patched):
    profile=ROOT/'build/stock-atlas-run/data';dumps=profile/'texdump/T20101M'
    missing=[n for n in CAPTURES if not (dumps/n).exists()]
    if missing:return dict(status='pending verified config captures',missing=missing)
    with Image.open(dumps/CAPTURES[0]) as a,Image.open(dumps/CAPTURES[1]) as b:
        pending=prepare_pack(patched,(a,b))
    target=profile/'textures/T20101M'
    seed_noto_pack.write_pack(target,pending);noto_font.copy_license(target)
    # Contact sheet in corrected display aspect, not stretched English glyphs.
    preview=Image.new('RGBA',(1040,13*72),'#181820')
    for i,(page,_,rect,_) in enumerate(labels()):
        high=pending[page][0].transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        tile=high.crop(tuple(v*SCALE for v in rect))
        tile=tile.resize((tile.width//2,tile.height),Image.Resampling.LANCZOS)
        preview.alpha_composite(tile,((i//13)*520,(i%13)*72))
    out=ROOT/'build/hd-ui';out.mkdir(exist_ok=True)
    preview.save(out/'config-help-labels-english.png')
    meta=dict(font_sha256=noto_font.FONT_SHA256,size=SIZE,heading_size=noto_font.SIZE,
              scale=SCALE,textures=[m for _,m in pending],
              verification='both complete source pages and raw hashes verified; post-restart check pending')
    (out/'config-help-pack.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta


if __name__=='__main__':
    pending=[]
    for name,fn in (('1ST_READ.vwf.bin',patch_executable),('SYSTEM.vwf.dat',patch_system)):
        file=ROOT/'build'/name;data=bytearray(file.read_bytes());fn(data);pending.append((file,data))
    for file,data in pending:file.write_bytes(data)
    print('Localized 29 configuration descriptions and 25 help-setting sprites.')
