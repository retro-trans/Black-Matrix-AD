"""Private native font comparison: Rayblade coverage/shadow, uniform aspect.

Builds from the authenticated first port, never overwrites prior discs. Reuses
the v2 bounded native VQ upload and admission/fallback mechanism.
"""
import json
import configparser
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import skies_full_texture as full

prior=full.prior
ROOT=prior.ROOT
OUT=ROOT/'build/skies-rayblade-font-v3'
QUAD=(20,15)
SAMPLE=(16,24)
ALIASES={'‘':"'",'’':"'",'“':'"','”':'"','—':'-','–':'-'}


def mask(ch,glyphs):
    if ch=='…':
        dot=glyphs['.'];box=dot.getbbox();out=Image.new('L',(12,24))
        for x in (0,4,8):out.paste(dot.crop(box),(x,box[1]))
        return out
    return glyphs[ALIASES.get(ch,ch)]


def glyph(ch,glyphs):
    """Rayblade's direct ARGB4444 writes, not source-over compositing.

    At the usual medium 4x surface scale its two-source-pixel horizontal
    shadow is written first; nonzero white foreground samples overwrite it.
    There is no downward shadow offset or multiplication of edge opacity.
    """
    source=mask(ch,glyphs);box=source.getbbox();left=box[0] if box else 0
    out=Image.new('RGBA',(16,32))
    for y in range(24):
        for x in range(12):
            alpha=source.getpixel((x,y));px=2+x-left
            if 0<=px+2<16:out.putpixel((px+2,y),(0,0,0,alpha))
            if alpha and 0<=px<16:out.putpixel((px,y),(255,255,255,alpha))
    if out.crop((0,24,16,32)).getbbox():raise ValueError('Glyph exceeds sample')
    return out


def pages(glyphs=None):
    if glyphs is None:_,glyphs,_,_=prior.source_bitmap()
    images=[Image.new('RGBA',(128,128)) for _ in range(4)]
    forward,_,chars=prior.atlas.tables();seen=set()
    for ch,index in chars.items():
        if index in seen:continue
        seen.add(index);slot=forward[index];local=slot%32
        images[slot//32].paste(glyph(ch,glyphs),(local%8*16,local//8*32))
    encoded=[];counts=[]
    for im in images:
        payload,count=full.encode_vq(im);encoded.append(payload);counts.append(count)
    return images,encoded,counts


def patch(exe,system,raw):
    result,sy,details=full.patch(exe,system,raw)
    old=full.uv_hook();new=full.uv_hook(native_quad=QUAD,sample=SAMPLE)
    if len(new)!=len(old):raise ValueError('Unexpected UV wrapper size')
    off=full.UV-prior.atlas.BASE
    if result[off:off+len(old)]!=old:raise ValueError('Unexpected UV wrapper')
    result=result[:off]+new+result[off+len(old):]
    return result,sy,details


def comparison(exe,images):
    old=[full.decode_vq((full.OUT/('font-page-%d.vq'%i)).read_bytes()) for i in range(4)]
    texts=['Beyond this hill is Pandemonium,','The person dear to this fellow,',
           'who was caught by the Inquisitor','for talking about love...',
           'Abel   Status   Ritual   Gabriel','Il1 O0 rn m  gypq  AVW 0123456789']
    out=Image.new('RGB',(1088,960),'#302e2b');draw=ImageDraw.Draw(out)
    forward=prior.atlas.tables()[0]
    for section,(sheets,sample,quad,label) in enumerate((
            (old,(14,26),(19,17),'v2: blended diagonal shadow / unequal X-Y scale'),
            (images,SAMPLE,QUAD,'v3: Rayblade coverage + horizontal shadow / uniform scale'))):
        y=section*470;draw.text((8,y+8),label+' (offline illustration)',fill='white')
        for row,text in enumerate(texts):
            line=Image.new('RGBA',(536,36));pen=0
            for ch in text:
                index=0 if ch==' ' else prior.latin.charmap()[ch]
                slot=forward[index];x=slot%8*16;sy=slot%32//8*32
                tile=sheets[slot//32].crop((x,sy,x+sample[0],sy+sample[1]))
                # Single display-space sample, NOT a 240-row raster followed
                # by another resample. This still is not live GPU evidence.
                tile=tile.resize((quad[0],quad[1]*2),Image.Resampling.BILINEAR)
                line.alpha_composite(tile,(pen,0))
                pen+=exe[prior.vwf.ADV_TAB-prior.vwf.LOAD_BASE+index]+(4 if ch==' ' else 0)
            big=line.resize((1072,72),Image.Resampling.NEAREST)
            out.paste(big,(8,y+30+row*71),big)
    out.save(OUT/'comparison.png')


def prepare_profile():
    """One-time isolated profile; copy saves, never link or overwrite them."""
    folder=OUT/'run480'
    if folder.exists():raise ValueError('Preserve existing comparison profile')
    stock=ROOT/'build/stock-atlas-run'
    source=json.loads((stock/'stock-source.json').read_text())
    emulator=Path(source['executable'])
    if prior.digest(emulator)!=source['sha256'] or prior.digest(stock/'flycast.exe')!=source['sha256']:
        raise ValueError('Unexpected stock emulator')
    cfg=configparser.ConfigParser(interpolation=None,strict=False);cfg.optionxform=str
    cfg.read(stock/'emu.cfg',encoding='utf-8')
    # Keep BM input assignments, but freeze renderer settings from the ACTUAL
    # shared executable profile used by the running Rayblade, not its obsolete
    # work/emulator profile. Never write to the other game's profile.
    render=snapshot_renderer()
    for section in cfg.sections():
        for key in list(cfg[section]):
            if key.startswith('rend.') or key=='pvr.rend':del cfg[section][key]
    for section in ('config','window','audio'):
        if not cfg.has_section(section):cfg.add_section(section)
    cfg['config'].update(render['settings'])
    cfg['config'].update({'UseReios':'yes','Debug.GDBEnabled':'no',
        'rend.Resolution':render['settings']['rend.Resolution'],
        'rend.DumpTextures':'yes','rend.CustomTextures':'no',
        'Dreamcast.AutoLoadState':'no','Dreamcast.AutoSaveState':'no'})
    cfg['window'].update({'fullscreen':'no','maximized':'no','width':'640','height':'480',
                         'left':'80','top':'80'})
    cfg['audio']['volume']='0'
    folder.mkdir();shutil.copy2(emulator,folder/'flycast.exe')
    with (folder/'emu.cfg').open('w',encoding='utf-8') as stream:cfg.write(stream)
    data=folder/'data';data.mkdir();copied=[]
    for path in (stock/'data').iterdir():
        if path.is_file() and (path.name.startswith(('vmu_save_','T20101M_vmu_save_')) or
                              path.name in ('dc_nvmem.bin','dc_flash.bin','dc_boot.bin')):
            shutil.copy2(path,data/path.name)
            digest=prior.digest(path)
            if prior.digest(data/path.name)!=digest:raise ValueError('Profile copy differs')
            copied.append(dict(file=path.name,sha256=digest))
    for filename in ('dc_boot.bin','dc_flash.bin'):
        if (stock/filename).is_file():shutil.copy2(stock/filename,folder/filename)
    report=dict(emulator_sha256=source['sha256'],source_profile='build/stock-atlas-run',
        source_saves_unchanged=True,save_copies=copied,resolution=int(render['settings']['rend.Resolution']),
        filtering='Snapshot of active Rayblade renderer; optional -Linear forces bilinear',
        no_custom_textures=True,audio_muted=True,auto_states_disabled=True)
    (OUT/'profile.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def snapshot_renderer():
    source=json.loads((ROOT/'build/stock-atlas-run/stock-source.json').read_text())
    path=Path(source['executable']).parent/'emu.cfg'
    cfg=configparser.ConfigParser(interpolation=None,strict=False);cfg.optionxform=str
    cfg.read(path,encoding='utf-8')
    settings={k:v for k,v in cfg['config'].items() if k.startswith('rend.') or k=='pvr.rend'}
    if 'rend.Resolution' not in settings or 'pvr.rend' not in settings:
        raise ValueError('Active renderer snapshot is incomplete')
    record=dict(source=str(path),source_sha256=prior.digest(path),settings=settings,
        source_unchanged=True,note='Launch-only snapshot; no changes to Rayblade or shared settings')
    (OUT/'renderer-settings.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def verify_dumps():
    expected=[np.array(full.decode_vq((OUT/('font-page-%d.vq'%i)).read_bytes())) for i in range(3)]
    for a in expected:a[a[:,:,3]==0]=0
    found={};files=list((OUT/'run480/data/texdump/T20101M').glob('*.png'))
    for path in files:
        with Image.open(path) as source:im=source.convert('RGBA')
        if im.size!=(128,128):continue
        for flipped in (False,True):
            actual=np.array(im.transpose(Image.Transpose.FLIP_TOP_BOTTOM) if flipped else im)
            actual[actual[:,:,3]==0]=0
            for i,ref in enumerate(expected):
                if np.array_equal(actual,ref):
                    found[i]=dict(file=path.name,flipped_y=flipped,sha256=prior.digest(path))
    result=dict(status='pass' if len(found)==3 else 'incomplete',
        texture_dump_files_checked=len(files),matched_nonblank_native_pages=len(found),
        pages=found,comparison='RGBA exact, ignoring RGB only where alpha is zero',
        scope='Actual Flycast-decoded native textures, not final blend/UV/framebuffer proof')
    (OUT/'texture-runtime-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if len(found)!=3:raise ValueError('Not all enhanced font pages were observed')
    return result


def build():
    if OUT.exists():raise ValueError('Preserve previous comparison build')
    source=full.SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=full.SOURCE_HASH:raise ValueError('Unknown source track')
    exe,elba=prior.read_file(source,'1ST_READ.BIN')
    system,slba=prior.read_file(source,'SYSTEM.DAT')
    images,raw,counts=pages();new_exe,new_system,details=patch(exe,system,raw)
    spans=[(full.FILL-prior.atlas.BASE,full.FILL-prior.atlas.BASE+256),
           (full.UV-prior.atlas.BASE,full.END-prior.atlas.BASE),
           (full.TRAMP-prior.atlas.BASE,full.TRAMP-prior.atlas.BASE+12),
           (details['uv_return']-prior.atlas.BASE,details['uv_return']-prior.atlas.BASE+4),
           (details['budget_offset'],details['budget_offset']+4),
           (prior.atlas.FILL_START-prior.atlas.BASE,prior.atlas.SIZE_STUB-prior.atlas.BASE)]
    sy_spans=[(prior.FONT_OFFSET+16+b*128,prior.FONT_OFFSET+16+b*128+8192) for b in full.BANKS]
    changes={};counts_changed={}
    for name,lba,before,after,allowed in (
            ('1ST_READ.BIN',elba,exe,new_exe,spans),
            ('SYSTEM.DAT',slba,system,new_system,sy_spans)):
        offsets=np.flatnonzero(np.frombuffer(before,dtype='u1')!=np.frombuffer(after,dtype='u1'))
        if any(not any(lo<=i<hi for lo,hi in allowed) for i in offsets):
            raise ValueError('Change outside declared font ranges')
        counts_changed[name]=len(offsets)
        changes.update({(lba-prior.inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i]
                        for i in offsets.tolist()})
    scenario,_=prior.read_file(source,'SCENARIO.DAT')
    audit=prior.audit_scenario(scenario,exe,new_exe)
    OUT.mkdir();comparison(exe,images)
    for i,(im,data) in enumerate(zip(images,raw)):
        im.resize((512,512),Image.Resampling.NEAREST).save(OUT/('font-page-%d.png'%i))
        (OUT/('font-page-%d.vq'%i)).write_bytes(data)
    folder=OUT/'disc2';folder.mkdir()
    track_hash=prior.copy_track(source,folder/source.name,full.SOURCE_HASH,changes)
    for name,expected in (('1ST_READ.BIN',new_exe),('SYSTEM.DAT',new_system),('SCENARIO.DAT',scenario)):
        if prior.read_file(folder/source.name,name)[0]!=expected:raise ValueError('Readback differs: '+name)
    companions=[]
    for path in source.parent.iterdir():
        if path.is_file() and path!=source:
            shutil.copy2(path,folder/path.name)
            digest=prior.digest(path)
            if digest!=prior.digest(folder/path.name):raise ValueError('Companion differs')
            companions.append(dict(file=path.name,sha256=digest))
    if prior.digest(source)!=full.SOURCE_HASH:raise ValueError('Source changed')
    report=dict(status='verified-skies-rayblade-match',disc=2,source='build/skies-rayblade-font-v1',
        source_sha256=full.SOURCE_HASH,track_sha256=track_hash,companions=companions,
        changed_bytes=counts_changed,codebook_entries=counts,source_cell=[12,24],
        sample=list(SAMPLE),native_quad=list(QUAD),display_quad=[QUAD[0],QUAD[1]*2],
        uniform_display_scale=1.25,alpha_levels=[0,5,11,15],
        shadow='two source pixels right, no Y offset; direct foreground overwrite, no source-over',
        metrics_line_breaks_and_grid_positions_unchanged=True,scenario_audit=audit,
        font_page_buffer_sizes_unchanged=True,no_extra_sprite_nodes=True,
        native_fallback_retained=True,hd_texture_files_changed=0,hook_details=details,
        live_game_verified=False,limitations=[
            'Nonadmitted or mixed Japanese records retain v1 fallback.',
            'Game video mode unchanged; 480-render comparison profile is emulator-only.',
            'No pixel-identical GPU or physical Dreamcast appearance claimed.'])
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    prepare_profile()
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['build']:build()
    elif sys.argv[1:]==['verify-dumps']:verify_dumps()
    elif sys.argv[1:]==['snapshot-renderer']:snapshot_renderer()
    else:print('VQ codebooks:',pages()[2])
