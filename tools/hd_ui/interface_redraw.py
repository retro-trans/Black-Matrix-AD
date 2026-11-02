"""Prepare/install/restore a guarded redraw of shared non-text UI sprites.

Matched sprite copies in SYSTEM and the primary CHAR HUD are updated together.
Already approved copper panels and existing HD English text remain exact.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image,ImageDraw
import interface_art
import ui_upscale
import panel_redraw
import install_panel_redraw

ROOT=panel_redraw.ROOT
DEFAULT_OUT=ROOT/'build/ui-redraw-interface-v2'
ANCHORS={'common':0xf50,'equipment':0x21890,'config':0x6294d0}


def sha(data):return hashlib.sha256(data).hexdigest()


def descriptors(data,offset):
    pvx=data.rfind(b'PVX ',0,offset)
    if pvx<0:raise ValueError('sprite page lacks PVX')
    page=data.count(b'PVRT',pvx,offset)
    rows={}
    for index in range(struct.unpack_from('<I',data,pvx+32)[0]):
        sw,sh,x,y,xx,yy,p,flags=struct.unpack_from('<8H',data,pvx+48+index*16)
        if p==page and 0<=x<xx<=256 and 0<=y<yy<=256:
            rows[index]=(x,y,xx,yy)
    return rows


def signature(image):return (image.size,sha(image.tobytes()))


def compose(baseline,updates):
    if baseline.size!=(1024,1024):raise ValueError('unexpected existing HD atlas')
    before=np.array(baseline.convert('RGBA'))
    after=baseline.convert('RGBA').copy()
    mask=np.zeros((1024,1024),dtype=bool)
    for rect,art,label in updates:
        x,y,xx,yy=rect
        if not (0<=x<xx<=256 and 0<=y<yy<=256):raise ValueError('invalid sprite rectangle')
        if art.size!=((xx-x)*4,(yy-y)*4):raise ValueError('new sprite has different dimensions: '+label)
        after.paste(art,(x*4,y*4))
        mask[y*4:yy*4,x*4:xx*4]=True
    changed=np.any(np.array(after)!=before,axis=2)
    if np.any(changed & ~mask):raise ValueError('unrelated HD artwork changed')
    return after,int(changed.sum())


def prepare(out=DEFAULT_OUT):
    out=Path(out).resolve()
    if not out.is_relative_to((ROOT/'build').resolve()) or out==(ROOT/'build').resolve():
        raise ValueError('use dedicated build subdirectory')
    if (out/'manifest.json').exists():raise ValueError('pack exists; use a fresh versioned directory')
    system=(ui_upscale.DEFAULT_BUILD/'SYSTEM.DAT').read_bytes()
    if sha(system)!=panel_redraw.SOURCE_SHA:raise ValueError('not verified r35 SYSTEM')
    system2=(ui_upscale.DEFAULT_BUILD/'SYSTEM.disc2.DAT').read_bytes()
    if sha(system2)!='7333756ee1da5dbc9f1854873b55a21dbf86f6987e8439f932cdd08222991121':
        raise ValueError('not verified r35 Disc 2 SYSTEM')
    char=ui_upscale.japanese_audit.archive(1,'CHAR.DAT')
    if sha(char)!='5ec8e1f70bb80abdf5aba6084249a5048bd7292c707ee6bd2992493733a749dd':
        raise ValueError('unexpected CHAR resource')
    catalog=interface_art.catalog()
    firstpages={m['offset']:(n,im,m) for n,im,m in ui_upscale.pages(system,'SYSTEM')}
    anchor_names={firstpages[offset][0] for offset in ANCHORS.values()}
    known={}; previews=[]
    for kind,offset in ANCHORS.items():
        name,native,meta=firstpages[offset]; rows=descriptors(system,offset)
        for index,(art,label) in catalog[kind].items():
            rect=rows[index]; low=native.crop(rect)
            if art.size!=(low.width*4,low.height*4):raise ValueError('wrong sprite dimensions '+kind+'/'+str(index))
            sig=signature(low)
            # Repeated animation frames that were originally identical must
            # remain identical; use the first canonical redraw for that image.
            if sig in known:art=known[sig][0]
            else:known[sig]=(art,label)
            previews.append((kind,index,label,low,art))
    charpages={m['offset']:(n,im,m) for n,im,m in ui_upscale.pages(char,'CHAR')}
    char_native=charpages[0x1350][1]
    for index,(art,label) in catalog['battle'].items():
        rect=descriptors(char,0x1350)[index];low=char_native.crop(rect)
        if art.size!=(low.width*4,low.height*4):raise ValueError('wrong battle sprite dimensions')
        sig=signature(low)
        if sig in known:art=known[sig][0]
        else:known[sig]=(art,label)
        previews.append(('battle',index,label,low,art))
    old=json.loads((ui_upscale.DEFAULT_OUT/'manifest.json').read_text())
    acceptable={r['texture']:r['original_file_sha256'] for r in old['textures']}
    acceptable[panel_redraw.TEXTURE]=install_panel_redraw.APPROVED_SHA
    pending={}
    for disc,archive,data in ((1,'SYSTEM',system),(2,'SYSTEM',system2),(1,'CHAR',char)):
        for name,native,meta in ui_upscale.pages(data,archive):
            # Restrict fan-out to UI-only PVX atlases, never portraits/scenes.
            if archive=='SYSTEM' and name not in anchor_names:continue
            if archive=='CHAR' and meta['offset']!=0x1350:continue
            updates=[]; refs=[]
            for index,rect in descriptors(data,meta['offset']).items():
                match=known.get(signature(native.crop(rect)))
                if match is not None:
                    art,label=match;updates.append((rect,art,label))
                    refs.append(dict(disc=disc,archive=archive,offset=meta['offset'],sprite=index,rect=rect,label=label))
            if name==panel_redraw.TEXTURE:
                for rect,art,label in interface_art.hud_parts():
                    updates.append((rect,art,label))
                    refs.append(dict(disc=disc,archive=archive,offset=meta['offset'],sprite=103,rect=rect,label=label))
            if not updates:continue
            if name in pending:
                if pending[name][2]!=sha(native.tobytes()):raise ValueError('hash collision')
                pending[name][1]['references']+=refs
                continue
            capture=ui_upscale.DUMPS/name
            if capture.exists():
                with Image.open(capture) as im:
                    if im.convert('RGBA').tobytes()!=native.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes():
                        raise ValueError('native capture mismatch: '+name)
            target=ui_upscale.TARGET/name
            previous=target.read_bytes() if target.exists() else None
            original_sha=sha(previous) if previous is not None else None
            if name not in acceptable or original_sha!=acceptable[name]:raise ValueError('unexpected existing user art: '+name)
            if previous is not None:
                with Image.open(target) as im:baseline=im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            else:baseline=native.resize((1024,1024),Image.Resampling.NEAREST)
            high,count=compose(baseline,updates)
            pending[name]=(high,dict(texture=name,original_file_sha256=original_sha,
                                    references=refs,changed_hd_pixels=count,
                                    unchanged_outside_sprite_rectangles=True),sha(native.tobytes()),previous)
    (out/'textures').mkdir(parents=True)
    (out/'originals').mkdir()
    (out/'upright').mkdir()
    entries=[]
    for name,(high,row,nativesha,previous) in pending.items():
        target=ui_upscale.TARGET/name
        if (sha(target.read_bytes()) if target.exists() else None)!=row['original_file_sha256']:
            raise ValueError('profile changed during preparation')
        if previous is not None:(out/'originals'/name).write_bytes(previous)
        high.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(out/'textures'/name)
        high.save(out/'upright'/name)
        row['output_file_sha256']=sha((out/'textures'/name).read_bytes())
        row['native_rgba_sha256']=nativesha;entries.append(row)
    # Each row shows native and newly drawn art at the same enlargement.
    sheet=Image.new('RGB',(960,((len(previews)+3)//4)*122),'#191919')
    draw=ImageDraw.Draw(sheet)
    for i,(kind,index,label,low,art) in enumerate(previews):
        x,y=(i%4)*240,(i//4)*122
        factor=min(5,104/low.width,82/low.height)
        size=(round(low.width*factor),round(low.height*factor))
        a=low.resize(size,Image.Resampling.NEAREST);b=art.resize(size,Image.Resampling.LANCZOS)
        sheet.paste(a,(x,y),a);sheet.paste(b,(x+116,y),b)
        draw.text((x,y+84),kind+' '+str(index)+': '+label,fill='#dddddd')
    sheet.save(out/'comparison.png')
    report=dict(version=1,scope='shared non-text geometric UI sprite redraw; original portraits/backgrounds and all text preserved',
                status='prepared',textures=entries,unique_designs=len(previews),
                matched_sprite_references=sum(len(e['references']) for e in entries),
                artwork_sha256=sha(Path(interface_art.__file__).read_bytes()),
                renderer_sha256=sha(Path(__file__).read_bytes()),
                limitations=['Not a claim that every game UI asset is redrawn.',
                             'Native stat lettering, special illustrated gauges/backgrounds and unclassified icons remain.',
                             'No live in-game visual verification yet.'])
    (out/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def apply(out=DEFAULT_OUT,restore=False,target_dir=ui_upscale.TARGET):
    out=Path(out);target_dir=Path(target_dir).resolve()
    report=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    pending=[];seen=set()
    for row in report['textures']:
        name=row['texture']
        if Path(name).name!=name or not name.endswith('.png'):raise ValueError('invalid texture filename')
        if name in seen:raise ValueError('duplicate texture entry in pack')
        seen.add(name)
        dst=target_dir/name
        if dst.is_symlink() or dst.resolve().parent!=target_dir:raise ValueError('redirected target')
        current=sha(dst.read_bytes()) if dst.exists() else None
        if current not in (row['original_file_sha256'],row['output_file_sha256']):
            raise ValueError('unknown user modification: '+name)
        desired=row['original_file_sha256'] if restore else row['output_file_sha256']
        path=out/('originals' if restore else 'textures')/name
        payload=path.read_bytes() if desired else None
        if payload is not None and sha(payload)!=desired:raise ValueError('pack payload changed')
        if current!=desired:pending.append((dst,payload))
    target_dir.mkdir(parents=True,exist_ok=True)
    for dst,payload in pending:
        if payload is None:dst.unlink() # exact pack addition; retained in textures/
        else:dst.write_bytes(payload)
    for row in report['textures']:
        dst=target_dir/row['texture']
        expected=row['original_file_sha256'] if restore else row['output_file_sha256']
        if (sha(dst.read_bytes()) if dst.exists() else None)!=expected:raise ValueError('readback failed')
    return dict(action='restore' if restore else 'install',changed=len(pending),textures=len(report['textures']))


def installed(out=DEFAULT_OUT):
    path=Path(out)/'manifest.json'
    if not path.exists():return False
    return any((ui_upscale.TARGET/r['texture']).exists() and
               sha((ui_upscale.TARGET/r['texture']).read_bytes())==r['output_file_sha256']
               for r in json.loads(path.read_text())['textures'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('prepare','install','restore'))
    p.add_argument('--out',type=Path,default=DEFAULT_OUT)
    a=p.parse_args()
    result=prepare(a.out) if a.command=='prepare' else apply(a.out,a.command=='restore')
    print(json.dumps({k:v for k,v in result.items() if k!='textures'},indent=2))
