"""Private v12: align list/help rows and admit the original star + Latin.

Uses spare slots96/97 in the existing blank fourth VQ page. No allocation
increase or ceiling change; admission still fails safely at existing limits.
"""
import argparse
import json
import shutil
import struct
import numpy as np
from PIL import Image,ImageDraw
import skies_menu_baseline as previous
import sh4asm

size=previous.size
prior=previous.prior
full=previous.full
ROOT=previous.ROOT
SOURCE=previous.OUT
SOURCE_SHA='48da50f6b4ac2b23a78d5d9de4da4a7cacddf0a629c073593852fd49785673d1'
OUT=ROOT/'build/skies-rayblade-font-v12-ritual-font'
HELPER=0x8C0F5000
HELPER_END=0x8C0F50D8
STAR=90
SLOT=96
GRIDS=((9,7),(8,5),(19,4),(7,2),(10,1))


def geometry_helper(*,vmu_origin=None,system_menu_inset=False):
    a=sh4asm.Asm(HELPER);a.long_('floats',size.v.FLOAT_TAB)
    a.mov(4,0);a.cmp_eq_i(SLOT);a.bt('star')
    if vmu_origin is not None:
        if not 0<vmu_origin<640:raise ValueError('Invalid VMU header origin')
        # Exact shared header context plus its VMU-only8x1 shape. Absolute
        # writes to the owning window origin and local top cannot accumulate.
        a.long_('vmu_context',0x8C1E7780)
        a.long_('window_x',size.v.WIN_TAB+8)
        a.long_('vmu_x',struct.unpack('<I',struct.pack('<f',vmu_origin))[0])
        a.mov_l_pc('vmu_context',0);a.cmp_eq(0,8);a.bf('not_vmu')
        a.mov_w_atd_r0(8,8);a.cmp_eq_i(8);a.bf('not_vmu')
        a.mov_w_atd_r0(10,8);a.cmp_eq_i(1);a.bf('not_vmu')
        a.mov_l_at(8,2);a.mov_i(96,1);a.shll(1);a.cmp_hs(1,2);a.bt('not_vmu')
        a.mov(2,5);a.shll2(2);a.shll2(5);a.shll2(5);a.shll(5);a.sub(2,5)
        a.mov_l_pc('window_x',1);a.add(5,1);a.mov_l_pc('vmu_x',0);a.mov_l_store(0,1)
        a.mov_i(2,7);a.bra('top');a.nop()
        a.label('not_vmu')
    # Opt-in extension for the three five-cell Save/Load/Setup rows. Keep
    # historical defaults byte-identical for older build authentication.
    grids=GRIDS+((5,3),) if system_menu_inset else GRIDS
    for i,(cols,rows) in enumerate(grids):
        a.mov_w_atd_r0(8,8);a.cmp_eq_i(cols);a.bf('grid_next'+str(i))
        a.mov_w_atd_r0(10,8);a.cmp_eq_i(rows);a.bt('inset')
        a.label('grid_next'+str(i))
    a.bra('normal');a.nop()
    a.label('inset')
    a.mov_i(16,4);a.mov_w_atd_r0(14,8);a.cmp_eq_i(1);a.bf('pitch_ready');a.mov_i(14,4)
    a.label('pitch_ready');a.mov_w_atd_r0(8,8);a.mov(0,5);a.mov(9,2);a.mov_i(2,7)
    a.label('row');a.cmp_hs(5,2);a.bf('top');a.sub(5,2);a.add(4,7);a.bra('row');a.nop()
    a.label('top');a.mov_l_pc('floats',1);a.mov(7,0);a.shll2(0);a.mov_l_r0(1,2)
    for off in (16,24):a.mov_i(off,0);a.mov_l_str_r0(2,12)
    a.label('normal');a.add_i(16,6);a.add_i(12,7);a.rts();a.nop()
    a.label('star');a.add_i(28,6);a.add_i(16,7);a.rts();a.nop()
    result=a.assemble()
    if HELPER+len(result)>HELPER_END:raise ValueError('Geometry helper exceeds guarded space')
    return result


def hook():
    return full.uv_hook(native_quad=size.QUAD,sample=size.font.SAMPLE,compact_selector=True,
                        geometry_helper=HELPER,star_slot=SLOT)


def patch_exe(exe):
    result=bytearray(exe);spans=[]
    old=full.uv_hook(native_quad=size.QUAD,sample=size.font.SAMPLE,compact_selector=True,menu_inset=2)
    new=hook();lo=full.UV-prior.atlas.BASE
    if full.UV+len(new)>full.END:raise ValueError('UV arena exceeded')
    if exe[lo:lo+len(old)]!=old:raise ValueError('Unknown v11 UV hook')
    size_uv=max(len(old),len(new));result[lo:lo+size_uv]=new+bytes(size_uv-len(new));spans.append((lo,lo+size_uv))
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes();helper=geometry_helper()
    lo=HELPER-prior.atlas.BASE;hi=lo+len(helper)
    if any(exe[lo:HELPER_END-prior.atlas.BASE]) or any(original[lo:HELPER_END-prior.atlas.BASE]):raise ValueError('Helper space occupied')
    result[lo:hi]=helper;spans.append((lo,hi))
    forward,reverse,_=prior.atlas.tables()
    for addr,expected,replacement in (
        (prior.atlas.FORWARD,forward,forward[:STAR]+bytes([SLOT])+forward[STAR+1:]),
        (prior.atlas.REVERSE,reverse,reverse[:SLOT*2]+struct.pack('<H',STAR)+reverse[SLOT*2+2:])):
        lo=addr-prior.atlas.BASE;hi=lo+len(expected)
        if exe[lo:hi]!=expected:raise ValueError('Unknown canonical mapping')
        result[lo:hi]=replacement;spans.append((lo,hi))
    if forward[STAR]!=255 or any(x in (SLOT,SLOT+1) for x in forward):raise ValueError('Star slots are not spare')
    # Keep the original icon's advance, not the small Latin metric.
    lo=size.SMALL_ADV-prior.atlas.BASE+STAR
    result[lo]=exe[size.v.ADV_TAB-prior.atlas.BASE+STAR];spans.append((lo,lo+1))
    delta=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if any(not any(a<=i<b for a,b in spans) for i in delta):raise ValueError('Unexpected executable edit')
    return bytes(result),delta,spans


def patch_system(system):
    off=prior.FONT_OFFSET+16+full.BANKS[3]*128
    before=full.decode_vq(system[off:off+8192])
    if before.getbbox():raise ValueError('Fourth canonical page is not blank')
    font=system[prior.FONT_OFFSET:prior.FONT_OFFSET+prior.fontdump.FONT_LEN]
    source=prior.cell(font,STAR).crop((0,0,28,16))
    # Original native palette, quantized only to the existing ARGB4444
    # surface. Duplicate rows exactly; GPU quad28x16 restores original shape.
    star=Image.new('RGBA',(28,16));star.putdata([prior.PALETTE[p] for p in source.getdata()])
    page=before.copy();page.paste(star.resize((28,32),Image.Resampling.NEAREST),(0,0))
    payload,count=full.encode_vq(page)
    result=system[:off]+payload+system[off+8192:]
    delta=np.flatnonzero(np.frombuffer(system,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    return result,delta,dict(star_slot=SLOT,star_quad=[28,16],star_sample=[28,32],codebook_entries=count),page


def preview(exe,system):
    forward=exe[prior.atlas.FORWARD-prior.atlas.BASE:prior.atlas.FORWARD-prior.atlas.BASE+256]
    pages=[full.decode_vq(system[prior.FONT_OFFSET+16+b*128:prior.FONT_OFFSET+16+b*128+8192]) for b in full.BANKS]
    out=Image.new('RGBA',(920,430),(18,14,9,255));draw=ImageDraw.Draw(out)
    draw.text((12,10),'Offline font preview; live rendering not verified',fill='white')
    for row,text in enumerate(('Knife','Mercy K.','Foras','Drains HP with your attack.')):
        pen=12
        for ch in text:
            glyph=0 if ch==' ' else prior.latin.charmap()[ch];slot=forward[glyph]
            x=slot%8*16;y=slot%32//8*32
            tile=pages[slot//32].crop((x,y,x+16,y+24)).resize((32,48),Image.Resampling.BILINEAR)
            out.alpha_composite(tile,(pen,52+row*72))
            pen+=exe[size.SMALL_ADV-prior.atlas.BASE+glyph]*2
    out.alpha_composite(pages[3].crop((0,0,28,32)).resize((56,64),Image.Resampling.NEAREST),(800,190))
    out.save(OUT/'font-preview.png')


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source v11 differs')
    exe,elba=prior.read_file(source,'1ST_READ.BIN');system,slba=prior.read_file(source,'SYSTEM.DAT')
    new_exe,edelta,spans=patch_exe(exe);new_system,sdelta,details,_=patch_system(system)
    report=dict(status='verified-skies-ritual-font' if build else 'planned-skies-ritual-font',writes=build,
        disc=2,source=str(SOURCE.relative_to(ROOT)),source_sha256=SOURCE_SHA,
        aligned_grids=GRIDS,inset_native_y=2,changes={'1ST_READ.BIN':len(edelta),'SYSTEM.DAT':len(sdelta)},
        executable_sha256=prior.sha(new_exe),system_sha256=prior.sha(new_system),helper_bytes=len(geometry_helper()),
        uv_hook_bytes=len(hook()),star=details,latin_pixels_and_metrics_unchanged=True,
        allocator_limits_and_page_buffers_unchanged=True,native_objective_cards_retained=24,
        saves_unchanged=True,in_game_verified=False,allowed_executable_spans=spans)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous ritual-font build')
    OUT.mkdir();preview(new_exe,new_system);folder=OUT/'disc2';folder.mkdir();changes={}
    for lba,after,delta in ((elba,new_exe,edelta),(slba,new_system,sdelta)):
        changes.update({(lba-prior.inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i] for i in delta})
    report['track_sha256']=prior.copy_track(source,folder/source.name,SOURCE_SHA,changes)
    for name,expected in (('1ST_READ.BIN',new_exe),('SYSTEM.DAT',new_system)):
        if prior.read_file(folder/source.name,name)[0]!=expected:raise ValueError('Archive readback differs: '+name)
    for name in ('CHAR.DAT','MAP.DAT','SCENARIO.DAT','PARAMETA.DAT'):
        if prior.read_file(source,name)[0]!=prior.read_file(folder/source.name,name)[0]:raise ValueError('Unrelated archive differs: '+name)
    report['companions']=[]
    for path in source.parent.iterdir():
        if path.is_file() and path!=source:
            shutil.copy2(path,folder/path.name);digest=prior.digest(path)
            if prior.digest(folder/path.name)!=digest:raise ValueError('Companion differs')
            report['companions'].append(dict(file=path.name,sha256=digest))
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source changed')
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');a=p.parse_args();run(a.build)
