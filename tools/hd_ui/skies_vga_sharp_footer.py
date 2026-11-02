"""Private VGA v9: submit footer glyphs through the existing full-detail font.

No new nodes, atlases, texture allocations or SYSTEM edits. A transient stack
node borrows a validated LIVE canonical record for each draw, never its lifetime.
Original persistent footer nodes and native fallback remain authoritative.
"""
import argparse
import json
import shutil
import struct
import numpy as np
from PIL import Image,ImageDraw
import skies_vga_font_metrics as previous
import sh4asm
import mode1_sector

ROOT=previous.ROOT
prior=previous.prior
v=prior.vwf
SOURCE=previous.OUT
SOURCE_SHA='e49535425a98d6390c349f2d9a98a8886b1a6ad9d82fc49cc0dc0bedc30615b4'
EXE_SHA='577626debafc203b97d654467d34b6abd32f32781a7448a3f8bad0b72384bfea'
OUT=ROOT/'build/skies-vga-compat-v9-sharp-footer'
STATUS='verified-skies-vga-sharp-footer'
ENTRY=0x8c06c1ac
ENTRY_END=0x8c06c1ce
# Only authenticated unused tails of existing private code reservations, NOT
# blank original font/lookup data. Each block also has a read-only RAM guard.
MAIN,MAIN_END=0x8c0f269c,0x8c0f2800
FIND,FIND_END=0x8c0f2518,0x8c0f2600
GEOMETRY,GEOMETRY_END=0x8c0f2d00,0x8c0f2e00
DRAW,DRAW_END=0x8c0f4970,0x8c0f4a00
TABLE,TABLE_END=0x8c0f2160,0x8c0f2200
MANAGER=0x8c1eb8d8
CAPTURE=ROOT/'build/skies-vga-sharp-footer-probe-20261031/ram.bin'
CAPTURE_SHA='e2a8c2053cd787eb5957042cf433ec413da01f0d47276c7dd034a5173827a477'


def fbits(n):return struct.unpack('<I',struct.pack('<f',n))[0]


def label_table():
    result=bytearray()
    for index,text in previous.LABELS.items():
        gids=bytes(prior.latin.charmap()[c] for c in text)
        x,y,xx,yy=previous.RECTS[index]
        result+=bytes([index])+gids+bytes(7-len(gids))+struct.pack('<4H',x,y,xx,yy)
    assert len(result)==144
    return bytes(result)


def draw():
    # R4=node, R5=window, R6=perform normal geometry. Preserve R8..R10/PR.
    a=sh4asm.Asm(DRAW)
    for key,val in dict(bind=0x8c06c914,blend=0x8c06c984,colour=0x8c06c9cc,
                        geometry=0x8c06cad0,submit=0x8c0a53c8).items():a.long_(key,val)
    for r in (8,9,10):a.mov_l_dec(r,15)
    a.sts_l_pr(15);a.mov(4,8);a.mov(5,9);a.mov(6,10)
    a.mov_l_pc('bind',2);a.jsr(2);a.mov(8,4)
    a.mov_l_pc('blend',2);a.jsr(2);a.mov(8,4)
    a.mov(9,5);a.mov_l_pc('colour',2);a.jsr(2);a.mov(8,4)
    a.tst(10,10);a.bt('submit')
    a.mov(8,4);a.mov(9,5);a.mov_l_pc('geometry',2);a.jsr(2);a.nop()
    a.label('submit')
    a.mov(8,4);a.add_i(68,4);a.mov_l_atd(44,8,6);a.mov_i(4,5)
    a._w(0xf4fc)  # FMOV FR15,FR4: exactly the displaced submit depth.
    a.mov_l_pc('submit',2);a.jsr(2);a.nop()
    a.lds_l_pr(15)
    for r in (10,9,8):a.mov_l_inc(15,r)
    a.rts();a.nop()
    return a.assemble()


def find_font():
    # Leaf, clobbers only R0..R7/MACL. Never use cached/released handles.
    a=sh4asm.Asm(FIND)
    for key,val in dict(records=v.LINE_RECORDS,states=prior.atlas.STATES,
                        stride=400,flags=0x184,handle=0x188,live=0x800,
                        manager=MANAGER,mstride=3264,active=0x8000).items():a.long_(key,val)
    a.mov_l_pc('records',1);a.mov_l_pc('states',2);a.mov_i(32,3)
    a.label('scan');a.mov_l_pc('flags',0);a.mov_w_r0(1,4)
    a.mov_l_pc('live',0);a.tst(0,4);a.bt('next')
    a.mov_b_at(2,0);a._w(0xc880);a.bt('next')
    a.mov_l_pc('handle',0);a.mov_l_r0(1,4);a.mov_i(80,0)
    a.cmp_hs(0,4);a.bt('next')
    a.mov_l_pc('mstride',5);a.mul_l(4,5);a.sts_macl(5)
    a.mov_l_pc('manager',6);a.add(5,6)
    a.mov_w_at(6,5);a.mov_l_pc('active',0);a.tst(0,5);a.bt('next')
    a.mov_w_atd_r0(2,6);a.extu_w(0,0);a.mov_i(64,5);a.shll(5)
    a.cmp_eq(5,0);a.bf('next')
    a.mov_w_atd_r0(4,6);a.cmp_eq_i(4);a.bf('next')
    a.rts();a.mov(4,0)
    a.label('next');a.mov_l_pc('stride',0);a.add(0,1);a.add_i(1,2)
    a.add_i(-1,3);a.tst(3,3);a.bf('scan');a.rts();a.mov_i(-1,0)
    return a.assemble()


def geometry(*,vertical_texel_center=False,equip_fallback=False):
    # R8=original node (normal geometry already evaluated), R14=stack copy,
    # R13=integer display pen, R10=glyph id. Screen quads bypass sprite X2.
    a=sh4asm.Asm(GEOMETRY)
    for key,val in dict(forward=prior.atlas.FORWARD,floats=v.FLOAT_TAB,
                        half=fbits(.5),width=fbits(16),height=fbits(12),
                        gold=0xffffb828).items():a.long_(key,val)
    a.mov(10,0);a.mov_l_pc('forward',1);a.mov_b_r0(1,7);a.extu_b(7,7)
    a.mov(7,0);a.mov_w_stored_r0(8,14)
    a.mov(7,0);a._w(0xc907);a.shll2(0);a.shll2(0);a.shll(0);a.mov(0,4)
    a.mov(7,0);a._w(0x4009);a._w(0x4001);a._w(0xc903)
    a.shll2(0);a.shll2(0);a.shll2(0);a.mov(0,5)
    a.mov(4,6);a.add_i(32,6);a.mov(5,7);a.add_i(48,7)
    if vertical_texel_center:
        # Same half-source-texel V bias as canonical dialogue/header glyphs.
        a.add_i(1,5);a.add_i(1,7)
    a.mov(14,1);a.add_i(74,1);a.add_i(74,1)
    for off,reg in ((0,4),(2,5),(4,6),(6,5),(8,6),(10,7),(12,4),(14,7)):
        a.mov(reg,0);a.mov_w_stored_r0(off,1)
    # Exact 1:1 physical source X and source24 -> native12 Y. Nothing is
    # reduced/rasterised into the old ARGB1555 caption bitmap.
    a.mov(8,1);a.add_i(84,1);a._w(0xf018);a.add_i(4,1);a._w(0xf118)
    a.mov_l_pc('floats',1);a.mov(13,0);a.shll2(0);a.add(0,1);a._w(0xf218)
    if equip_fallback:
        # R12=0 only for a guarded Equip fallback draw: subtract the old/new
        # advance difference, retain its existing +2 row inset and vertex tint.
        a.tst(12,12);a.bf('footer_x');a._w(0xf021);a.bra('x_done');a.nop()
        a.label('footer_x');a._w(0xf020);a.label('x_done')
        a.tst(12,12);a.bt('y_done')
    else:a._w(0xf020)  # FADD FR2,FR0
    a.mov_l_pc('half',1);a.mov_l_dec(1,15);a._w(0xf2f8);a.add_i(4,15);a._w(0xf120)
    if equip_fallback:a.label('y_done')
    a.mov_l_pc('width',1);a.mov_l_dec(1,15);a._w(0xf2f8);a.add_i(4,15)
    a._w(0xf30c);a._w(0xf320)  # right=left+16
    a.mov(14,1);a.add_i(84,1)
    for off,fr in ((0,0),(4,1),(8,3),(12,1),(16,3),(24,0)):
        a.mov_i(off,0);a._w(0xf007|(fr<<4)|(1<<8))
    a.mov_l_pc('height',2);a.mov_l_dec(2,15);a._w(0xf2f8);a.add_i(4,15);a._w(0xf120)
    for off in (20,28):a.mov_i(off,0);a._w(0xf117)
    if equip_fallback:a.tst(12,12);a.bt('return')
    a.mov(14,1);a.add_i(66,1);a.add_i(66,1);a.mov_l_pc('gold',2)
    for off in (0,4,8,12):a.mov_l_stored(2,off,1)
    if equip_fallback:a.label('return')
    a.rts();a.nop()
    return a.assemble()


def main(*,defer_fallback=False,extra_table=None,extra_count=3,equip_gate=None,single_caption=None):
    a=sh4asm.Asm(MAIN)
    for key,val in dict(table=TABLE,find=FIND,draw=DRAW,geometry=GEOMETRY,
                        normal_geometry=0x8c06cad0,adv=previous.ritual.size.SMALL_ADV,
                        shared=MANAGER+3264).items():a.long_(key,val)
    if extra_table is not None:a.long_('extra_table',extra_table)
    if equip_gate is not None:a.long_('equip_gate',equip_gate)
    if single_caption is not None:
        if extra_table is None or not 0<=single_caption[0]<=127:raise ValueError('Invalid extra single caption')
        a.long_('single_caption',single_caption[1])
    for r in range(8,15):a.mov_l_dec(r,15)
    a.sts_l_pr(15);a.add_i(-84,15);a.add_i(-84,15)
    a.mov(4,8);a.mov(13,9);a.mov(15,14)
    a.mov_l_atd(4,8,0);a.cmp_eq_i(1);a.bf('fallback')
    a.mov_l_pc('shared',1);a.mov_w_atd_r0(2,1);a.extu_w(0,0)
    a.mov_i(-125,2);a.extu_b(2,2);a.cmp_eq(2,0);a.bf('fallback')
    a.mov_w_atd_r0(8,8);a.mov(0,5);a.mov_l_pc('table',12);a.mov_i(10 if extra_table is not None else 9,6)
    a.label('lookup');a.mov_b_at(12,0);a.extu_b(0,0);a.cmp_eq(5,0);a.bt('check')
    a.add_i(16,12)
    if single_caption is None:a.add_i(-1,6);a.tst(6,6)
    else:a._w(0x4610)  # DT R6: same counter/zero test, two bytes smaller.
    a.bf('lookup')
    if extra_table is not None:
        # Four additional captions use authenticated existing table/draw
        # padding. The old nine-row default remains byte-identical.
        if not 1 <= extra_count <= 127:raise ValueError('Invalid secondary caption count')
        a.mov_l_pc('extra_table',12);a.mov_i(extra_count,6)
        a.label('lookup_extra');a.mov_b_at(12,0);a.extu_b(0,0);a.cmp_eq(5,0);a.bt('check')
        a.add_i(16,12)
        if single_caption is None:a.add_i(-1,6);a.tst(6,6)
        else:a._w(0x4610)
        a.bf('lookup_extra')
    if single_caption is None:a.bra('fallback');a.nop()
    else:
        a.mov(5,0);a.cmp_eq_i(single_caption[0]);a.bf('fallback')
        a.mov_l_pc('single_caption',12);a.bra('check');a.nop()
    a.label('check')
    for off,toff in ((148,8),(156,12)):
        a.mov(8,1);a.add_i(off//2,1);a.add_i(off-off//2,1)
        a.mov_l_at(1,2);a.mov_l_atd(toff,12,3);a.cmp_eq(3,2);a.bf('fallback')
    # Nonwhite/disabled vertices retain the original bitmap, rather than
    # silently losing their tint or fade. No graphics state is changed yet.
    a.mov(8,1);a.add_i(66,1);a.add_i(66,1);a.mov_i(-1,3)
    if equip_gate is None:
        for off in (0,4,8,12):
            a.mov_l_atd(off,1,2);a.cmp_eq(3,2);a.bf('fallback')
    else:
        a.mov_i(4,6);a.label('white');a.mov_l_inc(1,2);a.cmp_eq(3,2);a.bf('fallback')
        a.add_i(-1,6);a.tst(6,6);a.bf('white')
    a.mov_l_pc('find',2);a.jsr(2);a.nop();a.cmp_pz(0);a.bf('fallback');a.mov(0,11)
    # Preserve normal animation/origin/clipping calculations on the original.
    a.label('copy_start');a.mov(8,4);a.mov(9,5);a.mov_l_pc('normal_geometry',2);a.jsr(2);a.nop()
    a.mov(8,1);a.mov(14,2);a.mov_i(42,3)
    a.label('copy');a.mov_l_inc(1,0);a.mov_l_store(0,2);a.add_i(4,2)
    a.add_i(-1,3);a.tst(3,3);a.bf('copy')
    a.mov_l_stored(11,4,14)
    a.mov(14,1);a.add_i(68,1);a.mov(14,2);a.add_i(84,2)
    for off,extra in ((0,0),(4,32),(8,32)):
        if extra:a.add_i(extra,2)
        a.mov_l_stored(2,off,1)
    if equip_gate is not None:a.tst(12,12);a.bt('equip_letter')
    a.mov_i(0,13);a.add_i(1,12)
    a.label('letter');a.mov_b_at(12,10);a.extu_b(10,10);a.tst(10,10);a.bt('handled' if defer_fallback else 'done')
    if equip_gate is not None:a.label('equip_letter')
    a.mov_l_pc('geometry',2);a.jsr(2);a.nop()
    a.mov(14,4);a.mov(9,5);a.mov_i(0,6);a.mov_l_pc('draw',2);a.jsr(2);a.nop()
    if equip_gate is not None:a.tst(12,12);a.bt('done')
    a.mov_l_pc('adv',1);a.mov(10,0);a.mov_b_r0(1,0);a.extu_b(0,0);a.add(0,13)
    # Seven bytes per label, then the UV guard begins: cap even a 7-letter word.
    a.add_i(1,12);a.mov(12,0);a._w(0xc90f);a.cmp_eq_i(8);a.bf('letter')
    if defer_fallback:
        a.label('handled');a.mov_i(1,0);a.bra('done');a.nop()
        a.label('fallback');a.mov_i(0,0)
    else:
        a.bra('done');a.nop()
        a.label('fallback')
        if equip_gate is not None:
            a.mov_l_pc('equip_gate',2);a.jsr(2);a.nop();a.tst(0,0);a.bf('copy_start')
        a.mov(8,4);a.mov(9,5);a.mov_i(1,6)
        a.mov_l_pc('draw',2);a.jsr(2);a.nop()
    a.label('done');a.add_i(84,15);a.add_i(84,15);a.lds_l_pr(15)
    for r in reversed(range(8,15)):a.mov_l_inc(15,r)
    a.rts();a.nop()
    return a.assemble()


def entry():
    a=sh4asm.Asm(ENTRY);a.long_('helper',MAIN)
    a.mov_l_pc('helper',2);a.jsr(2);a.mov(14,4)
    a.long_('resume',ENTRY_END);a.mov_l_pc('resume',2);a.jmp(2);a.nop()
    data=a.assemble()
    return data+struct.pack('<H',9)*((ENTRY_END-ENTRY-len(data))//2)


def blocks():
    result={MAIN:main(),FIND:find_font(),GEOMETRY:geometry(),DRAW:draw(),TABLE:label_table()}
    for addr,end in ((MAIN,MAIN_END),(FIND,FIND_END),(GEOMETRY,GEOMETRY_END),(DRAW,DRAW_END),(TABLE,TABLE_END)):
        if addr+len(result[addr])>end:raise ValueError('Sharp footer block overflow: '+hex(addr)+' '+str(len(result[addr])))
    return result


def patch_exe(exe):
    if prior.sha(exe)!=EXE_SHA:raise ValueError('Unknown VGA v8 executable')
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes();capture=CAPTURE.read_bytes()
    if prior.sha(capture)!=CAPTURE_SHA:raise ValueError('Unknown read-only capture')
    result=bytearray(exe);allowed=set();payloads=blocks()
    for addr,payload in payloads.items():
        lo=addr-prior.atlas.BASE;hi=lo+len(payload)
        if any(exe[lo:hi]) or any(original[lo:hi]) or any(capture[addr-0x8c000000:addr-0x8c000000+len(payload)]):
            raise ValueError('Sharp footer reservation occupied: '+hex(addr))
        result[lo:hi]=payload;allowed.update(range(lo,hi))
    lo=ENTRY-prior.atlas.BASE;hi=ENTRY_END-prior.atlas.BASE
    if exe[lo:hi]!=original[lo:hi]:raise ValueError('Unknown original sprite draw chain')
    stub=entry()
    if len(stub)!=hi-lo:raise ValueError('Entry veneer overflow')
    result[lo:hi]=stub;allowed.update(range(lo,hi))
    delta=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    assert set(delta)<=allowed
    return bytes(result),delta,payloads


def preview(exe,system):
    """Offline source/geometry comparison, not a live GPU screenshot."""
    pages=[previous.ritual.full.decode_vq(system[prior.FONT_OFFSET+16+b*128:
        prior.FONT_OFFSET+16+b*128+8192]) for b in previous.ritual.full.BANKS]
    atlas=previous.previous.pvr_atlas.decode(system,previous.TEXTURE)
    out=Image.new('RGBA',(730,590),'#100e0a');d=ImageDraw.Draw(out)
    d.text((10,8),'OFFLINE: v8 reduced bitmap / v9 full header glyph textures (2x inspection)',fill='white')
    d.text((12,30),'Previous footer',fill='white');d.text((370,30),'Full-detail glyph path',fill='white')
    for row,(index,text) in enumerate(previous.LABELS.items()):
        y=55+row*56;r=previous.RECTS[index]
        old=atlas.crop(r).resize(((r[2]-r[0])*2,32),Image.Resampling.NEAREST)
        out.alpha_composite(old.resize((old.width*2,64),Image.Resampling.NEAREST),(12,y))
        line=Image.new('RGBA',(160,32));pen=0
        for ch in text:
            gid=prior.latin.charmap()[ch];slot=exe[prior.atlas.FORWARD-prior.atlas.BASE+gid]
            x=slot%8*16;sy=(slot%32//8)*32
            tile=pages[slot//32].crop((x,sy,x+16,sy+24))
            # White foreground is vertex-tinted; black shadow stays black.
            a=np.asarray(tile).copy()
            for c,gold in enumerate((255,184,40)):a[:,:,c]=(a[:,:,c].astype('u2')*gold//255).astype('u1')
            line.alpha_composite(Image.fromarray(a),(pen,1))
            pen+=exe[previous.ritual.size.SMALL_ADV-prior.atlas.BASE+gid]
        out.alpha_composite(line.resize((320,64),Image.Resampling.NEAREST),(370,y))
    out.save(OUT/'sharp-footer-preview.png')


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v8 track differs')
    exe,lba=prior.read_file(source,'1ST_READ.BIN');after,delta,payloads=patch_exe(exe)
    report=dict(status=STATUS if build else 'planned-skies-vga-sharp-footer',disc=2,
        source_sha256=SOURCE_SHA,source_executable_sha256=EXE_SHA,executable_sha256=prior.sha(after),
        changed_executable_bytes=len(delta),blocks={hex(a):len(b) for a,b in payloads.items()},
        same_header_glyph_textures_and_alpha=True,no_bitmap_downsampling=True,
        no_new_texture_allocations_or_nodes=True,system_and_icons_unchanged=True,
        vga_boot_and_existing_layout_unchanged=True,same_existing_save_folder=True,
        native_fallback_retained=True,in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous sharp-footer build')
    changes,touched=previous.sectors.sector_changes(source,lba,after,delta)
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir();target=folder/source.name
    system,_=prior.read_file(source,'SYSTEM.DAT');preview(after,system)
    report['track_sha256']=prior.copy_track(source,target,SOURCE_SHA,changes)
    report.update(changed_raw_bytes=len(changes),parity_repaired_sectors=touched)
    with source.open('rb') as stream:
        directory=list(prior.inject.iso_files(stream));boot=prior.inject._extent(stream,45000,32768)
    with target.open('rb') as stream:
        if list(prior.inject.iso_files(stream))!=directory or prior.inject._extent(stream,45000,32768)!=boot:raise ValueError('Boot/directory changed')
        for sector in touched:
            stream.seek(sector*2352);raw=stream.read(2352)
            if mode1_sector.regenerate(raw)!=raw:raise ValueError('Output parity invalid')
    report['files']=[]
    for name,_,_ in directory:
        old,_=prior.read_file(source,name);new,_=prior.read_file(target,name)
        if new!=(after if name=='1ST_READ.BIN' else old):raise ValueError('Unrelated payload changed: '+name)
        report['files'].append(dict(name=name,sha256=prior.sha(new)))
    report['companions']=[]
    for path in source.parent.iterdir():
        if path.is_file() and path!=source:
            shutil.copy2(path,folder/path.name);digest=prior.digest(path)
            if prior.digest(folder/path.name)!=digest:raise ValueError('Companion changed')
            report['companions'].append(dict(file=path.name,sha256=digest))
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');run(p.parse_args().build)
