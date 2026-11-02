"""Match native house depth sprites to the assembled approved panorama."""
import json
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image,ImageDraw
import house_texture as house
import ui_upscale as ui
import xxhash

OUT=house.ROOT/'build/house-layers-v1'
PACK=OUT/'pack-v2'
LABELS=('barrels-crate','table','cooking-left','cooking-right','fire-0','fire-1','fire-2')


def page(data,offset):
    px,fmt=data[offset+8:offset+10]
    w,h=struct.unpack_from('<HH',data,offset+12)
    if fmt!=1 or w!=h:raise ValueError('Unsupported depth sprite page')
    raw=data[offset+16:offset+16+w*h*2]
    im=Image.fromarray(ui.colors(np.frombuffer(raw,dtype='<u2')[ui.morton(w)],px))
    name='%x.png'%(xxhash.xxh32(raw,seed=7).intdigest() ^ (px<<27))
    return im,name


def locate(sprite,background):
    a=np.array(sprite);b=np.array(background.convert('RGB'))
    sh,sw=a.shape[:2];bh,bw=b.shape[:2]
    ys,xs=np.nonzero(a[:,:,3]>0)
    selected=np.linspace(0,len(xs)-1,min(40,len(xs)),dtype=int)
    errors=np.zeros((bh-sh+1,bw-sw+1),dtype=np.float32)
    for i in selected:
        x,y=xs[i],ys[i]
        errors+=np.abs(b[y:y+bh-sh+1,x:x+bw-sw+1].astype(np.float32)-a[y,x,:3]).mean(axis=2)
    candidates=np.argpartition(errors.ravel(),30)[:30]
    best=None
    for index in candidates:
        y,x=divmod(int(index),errors.shape[1])
        err=np.abs(b[y+ys,x+xs].astype(float)-a[ys,xs,:3]).mean()
        if best is None or err<best[0]:best=(float(err),x,y)
    return best


def locate_full(sprite,background):
    a=np.array(sprite).astype(float); b=np.array(background.convert('RGB')).astype(float)
    sh,sw=a.shape[:2];bh,bw=b.shape[:2]
    shape=(1<<(bh+sh-2).bit_length(),1<<(bw+sw-2).bit_length())
    mask=a[:,:,3]/255
    def corr(image,kernel):
        full=np.fft.irfft2(np.fft.rfft2(image,s=shape)*np.fft.rfft2(kernel[::-1,::-1],s=shape),s=shape)
        return full[sh-1:bh,sw-1:bw]
    score=corr(np.sum(b*b,axis=2),mask)
    for c in range(3):score-=2*corr(b[:,:,c],a[:,:,c]*mask)
    score+=np.sum(a[:,:,:3]**2*mask[:,:,None])
    y,x=np.unravel_index(np.argmin(score),score.shape)
    return float(np.sqrt(max(0,score[y,x])/(3*mask.sum()))),int(x),int(y)


def inspect():
    OUT.mkdir(exist_ok=True)
    data=house.source();bg=house.decode(data,house.OFFSETS[0])
    pvx=0x4FC9C0;offset=0x4FCA90
    atlas,name=page(data,offset)
    atlas.resize((768,768),Image.Resampling.NEAREST).save(OUT/'depth-native-atlas.png')
    rows=[]
    for i in range(struct.unpack_from('<I',data,pvx+32)[0]):
        desc=struct.unpack_from('<8H',data,pvx+48+i*16)
        sw,sh,x,y,xx,yy,p,flags=desc
        sprite=atlas.crop((x,y,xx,yy))
        match=locate_full(sprite.resize((sprite.width*2,sprite.height),Image.Resampling.NEAREST),bg)
        sprite.resize((sprite.width*4,sprite.height*8),Image.Resampling.NEAREST).save(OUT/f'depth-{i}-native.png')
        rows.append(dict(index=i,descriptor=desc,match=match))
    result=dict(pvx=pvx,page=offset,texture=name,matches=rows,
                second_state_same=data[0x4FC9C0:0x51CAA0]==data[0x6031C0:0x6232A0])
    (OUT/'source-matches.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


def registered_sprite(generated,original,rect):
    """Register each isolated generated cutout to the original alpha bounds."""
    x,y,xx,yy=rect
    factor=generated.width/256
    # The generated fire row extends slightly below its source slot. Exclude
    # that neighboring row when registering the barrels/crate sprite below it.
    crop_top=164 if rect==(0,160,96,224) else y-1
    crop_bottom=228 if rect==(0,160,96,224) else yy+1
    area=generated.crop((max(0,round((x-1)*factor)),max(0,round(crop_top*factor)),
                         min(generated.width,round((xx+1)*factor)),min(generated.height,round(crop_bottom*factor))))
    colored=np.any(np.array(area.convert('RGB'))>14,axis=2).astype('uint8')*255
    bounds=Image.fromarray(colored).getbbox()
    if bounds is None:raise ValueError('Generated object missing')
    native=original.crop(rect)
    target=native.getchannel('A').getbbox()
    if target is None:raise ValueError('Original object missing')
    left,top,right,bottom=target
    output=Image.new('RGBA',(native.width*4,native.height*4))
    rgb=area.crop(bounds).resize(((right-left)*4,(bottom-top)*4),Image.Resampling.LANCZOS)
    output.paste(rgb,(left*4,top*4))
    output.putalpha(native.getchannel('A').resize(output.size,Image.Resampling.NEAREST))
    return output


def background_updates(data):
    """Narrow the previous broad native fireplace guard to the stateful grate."""
    old=house.OUT/'review-pack'
    with Image.open(house.OUT/'house-upscale-generated-v1.png') as im:
        high=im.convert('RGB').resize((7040,1792),Image.Resampling.LANCZOS)
    source_black=np.all(np.array(house.decode(data,house.OFFSETS[1]))==0,axis=2)
    rgb=np.array(high);rgb[np.repeat(np.repeat(source_black,4,0),4,1)]=0
    high=Image.fromarray(rgb)
    protected=(583*4,187*4,649*4,196*4)
    rect=(576*4,176*4,656*4,208*4)
    outputs={}; masters={}
    for offset in house.OFFSETS:
        with Image.open(old/f'house-{offset:x}-assembled.png') as im: before=im.convert('RGB')
        after=before.copy(); after.paste(high.crop(rect),rect[:2]);after.paste(before.crop(protected),protected[:2])
        changed=np.any(np.array(before)!=np.array(after),axis=2)
        allowed=np.zeros(changed.shape,bool);allowed[rect[1]:rect[3],rect[0]:rect[2]]=True
        allowed[protected[1]:protected[3],protected[0]:protected[2]]=False
        if np.any(changed & ~allowed):raise ValueError('Background changed outside fireplace guard')
        masters[offset]=after
        pages=house.split(data,offset,after,4)
        for o,im in zip(house.pvr_atlas.scl_layout(data,offset)[3],pages):
            _,name=page(data,o)
            final=im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if name in outputs and outputs[name].tobytes()!=final.tobytes():raise ValueError('Shared atlas collision')
            outputs[name]=final
    return outputs,masters


def prepare():
    dest=PACK
    if dest.exists():raise ValueError('Pack already exists')
    data=house.source();atlas,name=page(data,0x4FCA90)
    if page(data,0x603290)[0].tobytes()!=atlas.tobytes():raise ValueError('House state sprite atlas differs')
    with Image.open(ui.DUMPS/name) as capture:
        if capture.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()!=atlas.tobytes():
            raise ValueError('Captured object sheet differs')
    house.verify_pack(ui.TARGET)
    background,masters=background_updates(data)
    with Image.open(OUT/'depth-generated-v1.png') as im:generated=im.convert('RGB')
    high=atlas.resize((1024,1024),Image.Resampling.NEAREST)
    objects=[];rects=[]
    for i in range(7):
        sw,sh,x,y,xx,yy,p,flags=struct.unpack_from('<8H',data,0x4FC9C0+48+i*16)
        if p or (xx-x,yy-y)!=(sw,sh):raise ValueError('Unexpected sprite geometry')
        rects.append((x,y,xx,yy));objects.append(registered_sprite(generated,atlas,rects[-1]))
    # All fire frames share the same stationary masonry. Only the original
    # flame/glow region can differ, with a smooth transition to the fixed rim.
    frame0=np.array(objects[4]).astype(float)
    yy,xx=np.indices(frame0.shape[:2]);distance=np.minimum.reduce((xx,255-xx,yy,159-yy))
    rim=np.clip(distance/12,0,1)[:,:,None]
    surround=masters[house.OFFSETS[0]].crop((560*4,161*4,688*4,201*4)).resize((256,160),Image.Resampling.LANCZOS)
    frame0[:,:,:3]=np.array(surround)*(1-rim)+frame0[:,:,:3]*rim
    dynamic=np.minimum.reduce((xx-44,228-xx,yy-28)).astype(float)
    weight=np.clip(dynamic/8,0,1)[:,:,None]
    for i in range(4,7):
        variant=np.array(objects[i]).astype(float)
        # The common first frame is also used for the non-varying interior rim.
        rgb=frame0[:,:,:3]*(1-weight)+variant[:,:,:3]*weight
        variant[:,:,:3]=rgb
        objects[i]=Image.fromarray(np.clip(variant,0,255).astype('uint8'))
    allowed=np.zeros((1024,1024),bool)
    for i,(obj,rect) in enumerate(zip(objects,rects)):
        x,y,xx,yy=rect;high.paste(obj,(x*4,y*4));allowed[y*4:yy*4,x*4:xx*4]=True
        obj.resize((obj.width*2,obj.height*2),Image.Resampling.NEAREST).save(OUT/(LABELS[i]+'-hd.png'))
    a=np.array(high);original=np.array(atlas.resize((1024,1024),Image.Resampling.NEAREST))
    if not np.array_equal(a[:,:,3],original[:,:,3]):raise ValueError('Sprite alpha/depth silhouette changed')
    if np.any(np.any(a!=original,axis=2)&~allowed):raise ValueError('Unrelated atlas pixels changed')
    if len({o.tobytes() for o in objects[4:]})!=3:raise ValueError('Fire animation lost')
    high.save(OUT/'depth-final-upright.png')
    background[name]=high.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    dest.mkdir();(dest/'textures').mkdir();(dest/'originals').mkdir()
    rows=[]
    for filename,im in background.items():
        target=ui.TARGET/filename
        if target.exists():
            with Image.open(target) as current:
                if current.convert('RGBA').tobytes()==im.tobytes():continue
            before=target.read_bytes();(dest/'originals'/filename).write_bytes(before)
        else:before=None
        im.save(dest/'textures'/filename)
        rows.append(dict(texture=filename,original_file_sha256=ui.digest(before) if before else None,
                         output_file_sha256=ui.digest((dest/'textures'/filename).read_bytes())))
    for offset,im in masters.items():im.save(dest/f'house-{offset:x}-assembled.png')
    manifest=dict(status='prepared-house-depth-layers',textures=rows,source_sha256=house.SOURCE_SHA,
        sprite_texture=name,sprite_rectangles=rects,sprites=7,fire_frames=3,alpha_exact=True,
        animated_region=[11,7,57,40],unchanged_outside_sprite_rectangles=True,
        background_edit='Only narrow original fireplace guard; stateful grate retained',
        generated_size=generated.size,in_game_verified=False)
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


def install():
    dest=PACK;manifest=json.loads((dest/'manifest.json').read_text())
    names={r['texture'] for r in manifest['textures']}
    protected={p.name:ui.digest(p.read_bytes()) for p in ui.TARGET.glob('*.png') if p.name not in names}
    result=ui.apply(dest)
    for r in manifest['textures']:
        if ui.digest((ui.TARGET/r['texture']).read_bytes())!=r['output_file_sha256']:raise ValueError('Install readback failed')
    if any(ui.digest((ui.TARGET/n).read_bytes())!=sha for n,sha in protected.items()):raise ValueError('Other HD texture changed')
    result.update(status='installed-house-depth-layers',other_textures_preserved=len(protected),in_game_verified=False)
    (OUT/'installation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    if '--prepare' in sys.argv:prepare()
    elif '--install' in sys.argv:install()
    else:inspect()
