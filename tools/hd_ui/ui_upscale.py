"""Reversible, palette-preserving 4x UI overlay for the stock Flycast profile.

Two edge-aware Scale2x passes, not AI redrawing. No executable, disc, save,
geometry, text or emulator configuration changes. Existing HD artwork is kept.
Hash layout follows Flycast ComputeHash; 8-bit face palettes are authenticated
against complete captured textures before any uncaptured variants are seeded.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from functools import lru_cache

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))

import numpy as np
from PIL import Image
import xxhash
import japanese_audit
import pac

DEFAULT_BUILD=ROOT/'build/reusable-atlas-noto-ui-r35'
DEFAULT_OUT=ROOT/'build/ui-upscale-4x-v1'
PROFILE=ROOT/'build/stock-atlas-run/data'
TARGET=PROFILE/'textures/T20101M'
DUMPS=PROFILE/'texdump/T20101M'
CHAR_UI={0x1350,0xC18B0,0x1469B0,0x1669D0,0x1869F0,0x1AD990}
# These two SYSTEM sheets are moving unit sprites, not UI artwork.
SYSTEM_EXCLUDE={0x4E4E50,0x5C6650}


def digest(data):return hashlib.sha256(data).hexdigest()


def scale2x(rgba):
    """Select existing neighboring colors only; alpha is part of equality."""
    p=np.ascontiguousarray(rgba,dtype=np.uint8).view('<u4').reshape(rgba.shape[:2])
    a=np.pad(p,1,mode='edge'); e=a[1:-1,1:-1]
    b,d,f,h=a[:-2,1:-1],a[1:-1,:-2],a[1:-1,2:],a[2:,1:-1]
    gate=(b!=h)&(d!=f)
    out=np.empty((p.shape[0]*2,p.shape[1]*2),dtype='<u4')
    for yy,xx,test,color in ((0,0,d==b,d),(0,1,b==f,f),(1,0,d==h,d),(1,1,h==f,f)):
        out[yy::2,xx::2]=np.where(gate&test,color,e)
    return out.view('u1').reshape(out.shape+(4,))


def upscale(native,existing=None,rectangles=(),tiled=False):
    low=np.array(native.convert('RGBA')); h,w=low.shape[:2]
    nearest=np.repeat(np.repeat(low,4,0),4,1)
    high=scale2x(scale2x(low))
    protect=np.zeros((h,w),dtype=bool)
    protect[[0,-1],:]=True;protect[:,[0,-1]]=True
    if tiled:
        # Keep both sides of every tile boundary identical to the source;
        # never sample the unrelated adjacent tile in the packed atlas.
        protect[::16,:]=True;protect[15::16,:]=True
        protect[:,::16]=True;protect[:,15::16]=True
    for x,y,xx,yy in rectangles:
        if not (0<=x<xx<=w and 0<=y<yy<=h):raise ValueError('sprite rectangle outside texture')
        protect[y,x:xx]=True;protect[yy-1,x:xx]=True
        protect[y:yy,x]=True;protect[y:yy,xx-1]=True
    if existing is not None:
        if existing.size!=(w*4,h*4):raise ValueError('existing UI replacement is not 4x')
        old=np.array(existing.convert('RGBA'))
        changed=np.any((old!=nearest).reshape(h,4,w,4,4),axis=(1,3,4))
        padded=np.pad(changed,1)
        expanded=np.logical_or.reduce([padded[y:y+h,x:x+w] for y in range(3) for x in range(3)])
        protect|=expanded
    else:old=nearest
    mask=np.repeat(np.repeat(protect,4,0),4,1)
    high[mask]=old[mask]
    return Image.fromarray(high),dict(protected_native_pixels=int(protect.sum()),
        changed_hd_pixels=int(np.any(high!=old,axis=2).sum()))


@lru_cache(maxsize=8)
def morton(w):
    y,x=np.indices((w,w))
    return sum(((y>>b)&1)<<(2*b)|((x>>b)&1)<<(2*b+1) for b in range(w.bit_length()-1))


def colors(values,px):
    v=values.astype(np.uint32)
    if px==0:
        channels=[(v>>s)&31 for s in (10,5,0)]
        parts=[(c<<3)|(c>>2) for c in channels]+[np.where(v&0x8000,255,0)]
    elif px==1:
        r,g,b=(v>>11)&31,(v>>5)&63,v&31
        parts=[(r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2),np.full(v.shape,255)]
    elif px==2:parts=[((v>>s)&15)*17 for s in (8,4,0,12)]
    else:raise ValueError('unsupported PVR color format')
    return np.stack(parts,axis=-1).astype('u1')


def pages(data,archive,excluded_raw=()):
    """Inventory supported native sheets; reject malformed recognized pages."""
    containers=[]
    for tag in (b'PVX ',b'SCL '):
        pos=0
        while True:
            pos=data.find(tag,pos)
            if pos<0:break
            containers.append((pos,tag));pos+=4
    containers.sort(); groups=list(pac.groups(data))
    pos=0
    while True:
        pos=data.find(b'PVRT',pos)
        if pos<0:break
        o=pos;pos+=4
        if archive=='CHAR' and o not in CHAR_UI:continue
        size,px,fmt,_,w,h=struct.unpack_from('<IBBHHH',data,o+4)
        if (px not in (0,1,2) or fmt not in (1,7,9)
                or (fmt!=9 and w!=h) or w not in (32,64,128,256,512)
                or h not in (32,64,128,256,512)):
            raise ValueError('unhandled UI PVR header: %s/%x'%(archive,o))
        raw=data[o+16:o+8+size]
        if archive=='SYSTEM' and digest(raw) in excluded_raw:continue
        owner=max((item for item in containers if item[0]<o),default=(0,b''))
        rectangles=[]; tiled=owner[1]==b'SCL '
        if owner[1]==b'PVX ':
            start=owner[0]; count=struct.unpack_from('<I',data,start+32)[0]
            page=data.count(b'PVRT',start,o)
            if not 0<count<=4096:raise ValueError('invalid sprite count')
            for i in range(count):
                sw,sh,x,y,xx,yy,p,flags=struct.unpack_from('<8H',data,start+48+i*16)
                if p==page and 0<=x<xx<=w and 0<=y<yy<=h:
                    rectangles.append((x,y,xx,yy))
        palhash=0
        if fmt in (1,9):
            if len(raw)!=w*h*2:raise ValueError('invalid raw texture length')
            words=np.frombuffer(raw,dtype='<u2')
            words=words.reshape(h,w) if fmt==9 else words[morton(w)]
            image=Image.fromarray(colors(words,px))
            salt=(px<<27)|(0x04000000 if fmt==9 else 0)
        else:
            if archive!='FACE' or px!=0 or len(raw)!=w*h:raise ValueError('unsupported indexed UI texture')
            _,start,length=next(g for g in groups if g[1]<=o<g[1]+g[2])
            pal=data.find(b'PVPL',start,start+length)
            if pal<0 or struct.unpack_from('<I',data,pal+4)[0]!=520:raise ValueError('unknown face palette')
            values=np.frombuffer(data,dtype='<u2',count=256,offset=pal+16)
            rgba=colors(values,0)
            image=Image.fromarray(rgba[np.frombuffer(raw,dtype='u1')[morton(w)]])
            palhash=xxhash.xxh32(values.astype('<u4').tobytes(),seed=7).intdigest()
            salt=0x30000000
        name='%x.png'%(xxhash.xxh32(raw,seed=7).intdigest()^palhash^salt)
        yield name,image,dict(offset=o,format=fmt,pixel_format=px,native_size=[w,h],
            raw_sha256=digest(raw),rectangles=rectangles,tiled=tiled)


def prepare(build=DEFAULT_BUILD,out=DEFAULT_OUT):
    build,out=Path(build),Path(out)
    if not out.resolve().is_relative_to((ROOT/'build').resolve()) or out.resolve()==(ROOT/'build').resolve():
        raise ValueError('output must be a dedicated directory under build')
    if (out/'manifest.json').exists():raise ValueError('pack already prepared; use install/restore or a new output directory')
    pending={}; captures=[]; resources=[]
    system=(build/'SYSTEM.DAT').read_bytes()
    excluded_raw={digest(system[o+16:o+16+131072]) for o in SYSTEM_EXCLUDE}
    for disc in (1,2):
        for archive in ('SYSTEM','GRAPHIC','CHAR','FACE'):
            if archive=='SYSTEM':
                filename='SYSTEM.DAT' if disc==1 else 'SYSTEM.disc2.DAT'
                data=(build/filename).read_bytes()
            else:data=japanese_audit.archive(disc,archive+'.DAT')
            source_sha=digest(data)
            # Shared resources need only one decode, but retain both-disc coverage.
            prior=next((r for r in resources if r['archive']==archive and r['sha256']==source_sha),None)
            resources.append(dict(disc=disc,archive=archive,sha256=source_sha,shared_with=prior['disc'] if prior else None))
            if prior:continue
            for name,native,meta in pages(data,archive,excluded_raw):
                upright=native; capture=DUMPS/name
                if capture.exists():
                    with Image.open(capture) as im:
                        if im.convert('RGBA').tobytes()!=native.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes():
                            raise ValueError('complete capture disagrees: '+name)
                    captures.append(dict(texture=name,format=meta['format'],archive=archive))
                path=TARGET/name; existing=None
                if path.exists():
                    with Image.open(path) as im:existing=im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                high,stats=upscale(upright,existing,meta['rectangles'],meta['tiled'])
                high=high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if name in pending:
                    # Reused pages can have different sprite lists. Preserve the
                    # union of protected pixels by falling back wherever outputs differ.
                    old,entry=pending[name]
                    if entry['native_rgba_sha256']!=digest(native.tobytes()):
                        raise ValueError('different native textures share a hash: '+name)
                    a=np.array(old);b=np.array(high);different=np.any(a!=b,axis=2)
                    base=existing if existing is not None else native.resize(high.size,Image.Resampling.NEAREST)
                    base=np.array(base.transpose(Image.Transpose.FLIP_TOP_BOTTOM))
                    a[different]=base[different];pending[name]=(Image.fromarray(a),entry)
                    entry['sources'].append(dict(disc=disc,archive=archive,**meta))
                    continue
                pending[name]=(high,dict(texture=name,sources=[dict(disc=disc,archive=archive,**meta)],
                    native_rgba_sha256=digest(native.tobytes()),
                    original_file_sha256=digest(path.read_bytes()) if path.exists() else None,
                    original_rgba_sha256=digest(existing.tobytes()) if existing is not None else None,**stats))
            print('Prepared Disc %d %s'%(disc,archive),flush=True)
    # Multiple complete raw and indexed captures authenticate the hash/decoder.
    if len({r['texture'] for r in captures if r['format']==1})<3 or len({r['texture'] for r in captures if r['format']==7})<3:
        raise ValueError('insufficient captured evidence for both texture formats')
    (out/'textures').mkdir(parents=True);(out/'originals').mkdir()
    entries=[]
    for name,(image,entry) in pending.items():
        if entry['original_file_sha256'] is not None:
            source=TARGET/name
            if digest(source.read_bytes())!=entry['original_file_sha256']:raise ValueError('texture changed during preparation')
            (out/'originals'/name).write_bytes(source.read_bytes())
        image.save(out/'textures'/name)
        entry['output_file_sha256']=digest((out/'textures'/name).read_bytes())
        entry['output_rgba_sha256']=digest(image.tobytes());entries.append(entry)
    report=dict(version=1,scale=4,method='two palette-preserving Scale2x passes; protected sprite/tile edges and existing HD details',
        source_build=str(build.resolve()),resources=resources,captures=captures,textures=entries,
        excluded='3D/map textures, battle effects/unit sprites, movie frames; existing HD text retained',
        in_game_verification='pending user restart')
    (out/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def apply(out=DEFAULT_OUT,restore=False):
    out=Path(out);report=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    pending=[]
    # Entire batch validates before writes. Recovery also rejects user edits.
    for row in report['textures']:
        name=row['texture']
        if Path(name).name!=name or not name.endswith('.png'):raise ValueError('invalid texture filename')
        dst=TARGET/name; current=digest(dst.read_bytes()) if dst.exists() else None
        if dst.resolve().parent!=TARGET.resolve():raise ValueError('texture resolves outside target directory')
        if current not in (row['original_file_sha256'],row['output_file_sha256']):
            raise ValueError('texture modified outside this pack: '+name)
        expected=row['original_file_sha256'] if restore else row['output_file_sha256']
        src=out/('originals' if restore else 'textures')/name
        data=src.read_bytes() if expected else None
        if data is not None and digest(data)!=expected:raise ValueError('pack payload changed: '+name)
        if current!=expected:pending.append((dst,data))
    TARGET.mkdir(parents=True,exist_ok=True)
    for dst,data in pending:
        if data is None:dst.unlink()  # Exact verified pack-added file; reproducible from out/textures.
        else:dst.write_bytes(data)
    return dict(action='restore' if restore else 'install',changed=len(pending),textures=len(report['textures']))


def installed(out=DEFAULT_OUT):
    manifest=Path(out)/'manifest.json'
    if not manifest.exists():return False
    report=json.loads(manifest.read_text(encoding='utf-8'))
    return any((TARGET/r['texture']).exists()
               and digest((TARGET/r['texture']).read_bytes())==r['output_file_sha256']
               and r['output_file_sha256']!=r['original_file_sha256'] for r in report['textures'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('prepare','install','restore'))
    p.add_argument('--build',type=Path,default=DEFAULT_BUILD)
    p.add_argument('--out',type=Path,default=DEFAULT_OUT)
    a=p.parse_args()
    result=prepare(a.build,a.out) if a.command=='prepare' else apply(a.out,a.command=='restore')
    print(json.dumps({k:v for k,v in result.items() if k not in ('textures','captures','resources')},indent=2))
    if a.command=='prepare':print('Textures:',len(result['textures']),'verified captures:',len(result['captures']))


if __name__=='__main__':main()
