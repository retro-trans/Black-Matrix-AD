"""Full Skies glyph coverage in native VQ/ARGB4444 font pages.

Keeps the original four 8192-byte canonical texture allocations. Unadmitted
records retain the v1 native fallback. No emulator texture replacement.
"""
import json
import struct
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import skies_rayblade_font as prior
import sh4asm

ROOT=prior.ROOT
OUT=ROOT/'build/skies-rayblade-font-v2'
SOURCE=prior.OUT
SOURCE_HASH='ef08e98f7a956150b55c12204ba79a8f58a64ce5d7b02f34e5019cb7be7e5cd0'
FILL=0x8C0F2C00
UV=0x8C0F2F00
END=0x8C0F3100
TRAMP=0x8C0F46E0
BANKS=(606,862,1118,1374)
FONT_BASE=0x8C75F800
RAW_TABLE=0x8C1E7740
FONT_POINTER=0x8C1D8318


def morton(x,y):
    return sum(((y>>b)&1)<<(2*b)|((x>>b)&1)<<(2*b+1) for b in range(7))


def rgba_glyph(ch,glyphs):
    aliases={'‘':"'",'’':"'",'“':'"','”':'"','—':'-','–':'-'}
    if ch=='…':
        dot=glyphs['.'];box=dot.getbbox();source=Image.new('L',(12,24))
        for x in (0,4,8):source.paste(dot.crop(box),(x,box[1]))
    else:source=glyphs[aliases.get(ch,ch)]
    box=source.getbbox();left=box[0] if box else 0
    result=Image.new('RGBA',(16,32))
    # The first revision's opaque gray edges are replaced with true alpha.
    # A one-source-pixel black shadow follows the Rayblade reference treatment.
    shadow=Image.new('RGBA',source.size);shadow.putalpha(source)
    result.alpha_composite(shadow,(2-left,1))
    white=Image.new('RGBA',source.size,(255,255,255,0));white.putalpha(source)
    result.alpha_composite(white,(1-left,0))
    if result.crop((14,0,16,32)).getbbox() or result.crop((0,26,16,32)).getbbox():
        raise ValueError('Full source glyph exceeds sample '+repr(ch))
    return result


def encode_vq(image):
    a=np.asarray(image,dtype='u2')
    rgba=((a+8)//17).clip(0,15)
    words=rgba[:,:,3]<<12|rgba[:,:,0]<<8|rgba[:,:,1]<<4|rgba[:,:,2]
    patterns={};book=[];indices=bytearray(4096)
    for y in range(64):
        for x in range(64):
            block=tuple(int(words[y*2+dy,x*2+dx]) for dx,dy in ((0,0),(0,1),(1,0),(1,1)))
            if block not in patterns:
                patterns[block]=len(book);book.append(block)
            if patterns[block]>=256:raise ValueError('Lossless VQ codebook exceeds 256')
            indices[morton(x,y)]=patterns[block]
    payload=b''.join(struct.pack('<4H',*v) for v in book)
    payload+=bytes(2048-len(payload))+indices
    if len(payload)!=6144:raise AssertionError('VQ size')
    decoded=decode_vq(payload)
    expected=np.empty((128,128,4),dtype='u1')
    for c,shift in enumerate((8,4,0,12)):expected[:,:,c]=((words>>shift)&15)*17
    if decoded.tobytes()!=expected.tobytes():raise AssertionError('VQ exact roundtrip')
    return payload+bytes(2048),len(book)


def decode_vq(payload):
    out=Image.new('RGBA',(128,128))
    for y in range(64):
        for x in range(64):
            code=payload[2048+morton(x,y)]
            values=struct.unpack_from('<4H',payload,code*8)
            for word,(dx,dy) in zip(values,((0,0),(0,1),(1,0),(1,1))):
                out.putpixel((x*2+dx,y*2+dy),tuple(((word>>s)&15)*17 for s in (8,4,0,12)))
    return out


def pages():
    _,glyphs,_,_=prior.source_bitmap()
    pages=[Image.new('RGBA',(128,128)) for _ in range(4)]
    forward,_,chars=prior.atlas.tables();seen=set()
    for ch,index in chars.items():
        if index in seen:continue
        seen.add(index);slot=forward[index];local=slot%32
        pages[slot//32].paste(rgba_glyph(ch,glyphs),(local%8*16,local//8*32))
    encoded=[];counts=[]
    for page in pages:
        raw,count=encode_vq(page);encoded.append(raw);counts.append(count)
    return pages,encoded,counts


def fill_hook(*,reset_fallback=False,fallback_header=0x0105):
    # Historical default is retained byte-for-byte for older build guards.
    # New variants explicitly use the original game's native 0x0500 header.
    if fallback_header not in (0x0105,0x0500):raise ValueError('Unsupported fallback header')
    atlas=prior.atlas.build_code(True);atlas.assemble()
    a=sh4asm.Asm(FILL)
    a.long_('state',atlas.labels['state_pointer'])
    a.long_('old',atlas.labels['fill_hook'])
    a.long_('font',FONT_POINTER);a.long_('destinations',RAW_TABLE)
    a.long_('header',0x0302);a.long_('words',2048)
    if reset_fallback:a.long_('native_header',fallback_header)
    for i,bank in enumerate(BANKS):a.long_('bank'+str(i),16+bank*128)
    for r in (8,9,10):a.mov_l_dec(r,15)
    a.sts_l_pr(15);a.mov(14,4);a.mov_l_pc('state',3);a.jsr(3);a.nop()
    a.tst(7,7);a.bt('fallback');a.mov_b_at(7,0);a.extu_b(0,0)
    a._w(0xc880);a.bt('fallback')  # TST #128,R0
    a.mov_l_pc('destinations',8)
    for i in range(4):
        a.mov_l_pc('font',1);a.mov_l_at(1,1)
        a.mov_l_pc('bank'+str(i),2);a.add(2,1)
        a.mov_l_inc(8,9);a.mov(9,2);a.add_i(-8,2)
        a.mov_l_pc('header',0);a.mov_w_store(0,2)
        a.mov_l_pc('words',10)
        a.label('copy'+str(i));a.mov_l_inc(1,0);a.mov_l_store(0,9);a.add_i(4,9)
        a.add_i(-1,10);a.tst(10,10);a.bf('copy'+str(i))
    a.lds_l_pr(15)
    for r in (10,9,8):a.mov_l_inc(15,r)
    a.rts();a.nop()
    a.label('fallback')
    if reset_fallback:
        # Native size() rebuilds lengths/dimensions, NOT the PVRT format.
        # Shared staging buffers may have just held admitted VQ/ARGB4444.
        # Restore all four headers before the original 4bpp fill/upload.
        a.mov_l_pc('destinations',1);a.mov_i(4,2)
        a.mov_l_pc('native_header',0)
        a.label('reset_headers');a.mov_l_inc(1,3);a.add_i(-8,3)
        a.mov_w_store(0,3);a.add_i(-1,2);a.tst(2,2);a.bf('reset_headers')
    a.lds_l_pr(15)
    for r in (10,9,8):a.mov_l_inc(15,r)
    a.mov_l_pc('old',3);a.jmp(3);a.nop()
    return a.assemble()


def uv_hook(*,native_quad=(19,17),sample=(14,26),compact_selector=False,menu_inset=0,
            geometry_helper=None,star_slot=None,vertical_texel_center=False):
    if not (1<=native_quad[0]<=32 and 1<=native_quad[1]<=32 and
            1<=sample[0]<=16 and 1<=sample[1]<=32):
        raise ValueError('Invalid native font geometry')
    if not 0<=menu_inset<=3:raise ValueError('Invalid main-menu vertical inset')
    if star_slot is not None and (geometry_helper is None or star_slot!=96):
        raise ValueError('Unsupported dedicated star slot')
    if vertical_texel_center and (sample!=(16,24) or geometry_helper is None or star_slot!=96):
        raise ValueError('Vertical sampling bias requires the guarded full-detail Latin path')
    a=sh4asm.Asm(UV)
    for key,value in dict(records=prior.vwf.LINE_RECORDS,states=prior.atlas.STATES,
                          stride=400,forward=prior.atlas.FORWARD,
                          floats=prior.vwf.FLOAT_TAB,limit=prior.vwf.NTAB).items():a.long_(key,value)
    if geometry_helper is not None:a.long_('geometry_helper',geometry_helper)
    a.word_('flags',0x184);a.word_('handle',0x188)
    a.tst(12,12);a.bt('return')
    a.mov_l_pc('records',4);a.mov_l_pc('states',5);a.mov_i(32,6)
    a.label('scan');a.mov_w_pc('flags',0);a.mov_w_r0(4,1)
    a.mov_i(8,2);a._w(0x4218);a.tst(2,1);a.bt('next')
    a.mov_w_pc('handle',0);a.mov_l_r0(4,1);a.cmp_eq(11,1);a.bt('found')
    a.label('next');a.mov_l_pc('stride',0);a.add(0,4);a.add_i(1,5)
    a.add_i(-1,6);a.tst(6,6);a.bf('scan');a.bra('return');a.nop()
    a.label('found');a.mov_b_at(5,0);a.extu_b(0,0);a._w(0xc880);a.bt('return')
    a.mov_w_at(4,1);a.extu_w(1,1);a.cmp_hs(1,10);a.bt('return')
    a.mov(10,0);a.shll(0);a.add_i(4,0);a.mov_w_r0(4,0);a.extu_w(0,0)
    a.mov(0,1);a.extu_b(0,0);a.cmp_eq(1,0);a.bf('return')
    a.mov_l_pc('forward',1);a.mov_b_r0(1,7);a.extu_b(7,7)
    a.mov(7,0);a._w(0xc880);a.bf('return')  # Reject sentinel 255, accept slots <128.
    a.mov_l_dec(7,15)
    a.mov_i(12,0);a.mov_l_r0(12,4);a.mov_i(16,0);a.mov_l_r0(12,5)
    a.mov_l_pc('floats',1);a.mov_i(0,2);a.mov_l_pc('limit',3)
    a.mov_i(-1,6);a.mov_i(-1,7)
    a.label('float_scan');a.mov_l_inc(1,0);a.cmp_eq(4,0);a.bf('not_x');a.mov(2,6)
    a.label('not_x');a.cmp_eq(5,0);a.bf('not_y');a.mov(2,7)
    a.label('not_y');a.cmp_pz(6);a.bf('more');a.cmp_pz(7);a.bt('position')
    a.label('more');a.add_i(1,2);a.cmp_hs(3,2);a.bf('float_scan')
    a.mov_l_inc(15,7);a.bra('return');a.nop()
    a.label('position')
    if geometry_helper is not None:
        a.mov_l_at(15,4)  # saved canonical slot; helper preserves R3 and R8..R15
        a.sts_l_pr(15);a.mov_l_pc('geometry_helper',0);a.jsr(0);a.nop();a.lds_l_pr(15)
    elif menu_inset:
        # Only the two known 9x7 main menus. Reconstruct their local row Y
        # from the cell index, not the adjusted node, so redraws cannot drift.
        # This runs only after the admitted English-glyph checks above.
        a.mov_w_atd_r0(8,8);a.cmp_eq_i(9);a.bf('menu_inset_done')
        a.mov_w_atd_r0(10,8);a.cmp_eq_i(7);a.bf('menu_inset_done')
        a.mov_i(16,4);a.mov_w_atd_r0(14,8);a.cmp_eq_i(1);a.bf('menu_pitch_ready')
        a.mov_i(14,4)
        a.label('menu_pitch_ready');a.mov(9,2);a.mov_i(menu_inset,7);a.mov_i(9,5)
        a.label('menu_row');a.cmp_hs(5,2);a.bf('menu_top')
        a.sub(5,2);a.add(4,7);a.bra('menu_row');a.nop()
        a.label('menu_top');a.mov_l_pc('floats',1);a.mov(7,0);a.shll2(0);a.mov_l_r0(1,2)
        for offset in (16,24):a.mov_i(offset,0);a.mov_l_str_r0(2,12)
        a.label('menu_inset_done')
    if geometry_helper is None:
        a.add_i(native_quad[0],6);a.add_i(native_quad[1],7)
    a.cmp_hs(3,6);a.bt('pop_return');a.cmp_hs(3,7);a.bt('pop_return')
    a.mov_l_pc('floats',1);a.mov(6,0);a.shll2(0);a.mov_l_r0(1,2)
    for offset in (20,28):a.mov_i(offset,0);a.mov_l_str_r0(2,12)
    a.mov(7,0);a.shll2(0);a.mov_l_r0(1,2)
    for offset in (32,40):a.mov_i(offset,0);a.mov_l_str_r0(2,12)
    a.mov_l_inc(15,7)
    if star_slot is not None:
        a.mov_i(sample[0]*2,2);a.mov_i(sample[1]*2,3)
        a.mov(7,0);a.cmp_eq_i(star_slot);a.bf('sample_ready')
        a.mov_i(56,2);a.mov_i(64,3)
        a.label('sample_ready')
    a.mov(7,0);a._w(0xc907);a.shll2(0);a.shll2(0);a.shll(0);a.mov(0,4)
    a.mov(7,0);a._w(0x4009);a._w(0x4001);a._w(0xc903)
    a.shll2(0);a.shll2(0);a.shll2(0);a.mov(0,5)
    if star_slot is None:
        a.mov(4,6);a.add_i(sample[0]*2,6);a.mov(5,7);a.add_i(sample[1]*2,7)
    else:a.mov(4,6);a.add(2,6);a.mov(5,7);a.add(3,7)
    if vertical_texel_center:
        # 8.8 UV units over128 texels: +1 means half a source texel.
        # Keep the24-texel span and all geometry/ink unchanged. Do not bias
        # U (already full horizontal sampling) or the original star icon.
        a.mov(3,0);a.cmp_eq_i(48);a.bf('vertical_center_done')
        a.add_i(1,5);a.add_i(1,7)
        a.label('vertical_center_done')
    for offset,reg in ((148,4),(150,5),(152,6),(154,5),(156,6),(158,7),(160,4),(162,7)):
        a.mov_i(offset-128,0);a.add_i(127,0);a.add_i(1,0);a.mov_w_str_r0(reg,12)
    a.bra('return');a.nop()
    a.label('pop_return');a.mov_l_inc(15,7)
    a.label('return')
    if compact_selector:
        # Apply to BOTH admitted and fallback Yes/No, after their UV path.
        # Derive from cell index, never an already adjusted Y (idempotent).
        a.tst(12,12);a.bt('selector_done')
        a.mov_w_atd_r0(8,8);a.cmp_eq_i(3);a.bf('selector_done')
        a.mov_w_atd_r0(10,8);a.cmp_eq_i(2);a.bf('selector_done')
        a.mov_i(2,2);a.mov_i(3,0);a.cmp_hs(0,9);a.bf('selector_top')
        a.add_i(16,2)
        a.label('selector_top');a.mov_l_pc('floats',1)
        a.mov(2,0);a.shll2(0);a.mov_l_r0(1,3)
        for offset in (16,24):a.mov_i(offset,0);a.mov_l_str_r0(3,12)
        a.add_i(11,2);a.mov(2,0);a.shll2(0);a.mov_l_r0(1,3)
        for offset in (32,40):a.mov_i(offset,0);a.mov_l_str_r0(3,12)
        a.label('selector_done')
    a.rts();a.nop()
    return a.assemble()


def patch(exe,system,raw_pages):
    fill,uv=fill_hook(),uv_hook()
    if len(fill)>256 or UV+len(uv)>END:raise ValueError('Hook exceeds cave')
    origin=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    for lo,hi in ((FILL,FILL+256),(UV,END)):
        if any(exe[lo-prior.atlas.BASE:hi-prior.atlas.BASE]) or any(origin[lo-prior.atlas.BASE:hi-prior.atlas.BASE]):
            raise ValueError('Hook storage occupied')
    a=prior.atlas.build_code(True);old=a.assemble()
    code=prior.vwf.build_code(a.labels['slot_hook'],ui_fixes=True,natural_font=True,
        pixel_aspect_lut=prior.atlas.FORWARD,main_menu_padding=4,stance_menu_padding=4,
        dialogue_space_extra=4,latin_quad_width=28);blob=code.assemble()
    start=prior.vwf.CODE-prior.atlas.BASE
    if exe[start:start+len(blob)]!=blob:raise ValueError('Unknown first-port renderer')
    if any(exe[TRAMP-prior.atlas.BASE:TRAMP-prior.atlas.BASE+12]) or any(origin[TRAMP-prior.atlas.BASE:TRAMP-prior.atlas.BASE+12]):
        raise ValueError('Trampoline occupied')
    if not prior.vwf.BEAR_TAB+prior.vwf.NGLYPH<=TRAMP<TRAMP+12<=0x8C0F4700:
        raise ValueError('Trampoline overlaps reserved data')
    result=bytearray(exe);sy=bytearray(system)
    expected=struct.pack('<I',a.labels['fill_hook'])
    lo=prior.atlas.FILL_START-prior.atlas.BASE;hi=prior.atlas.SIZE_STUB-prior.atlas.BASE
    if exe[lo:hi].count(expected)!=1:raise ValueError('Unknown fill hook call')
    off=lo+exe[lo:hi].index(expected);struct.pack_into('<I',result,off,FILL)
    # Use more of the existing guarded pool, not a larger allocation pool.
    # The original 448-unit forecast ceiling still reserves pending records.
    old_limit=struct.pack('<I',129)
    if old.count(old_limit)!=1:raise ValueError('Ambiguous canonical extra-budget limit')
    budget_offset=prior.atlas.CODE-prior.atlas.BASE+old.index(old_limit)
    if exe[budget_offset:budget_offset+4]!=old_limit:raise ValueError('Unknown canonical budget')
    struct.pack_into('<I',result,budget_offset,385)
    tail=code.labels['uvf_out']
    if exe[tail-prior.atlas.BASE:tail-prior.atlas.BASE+4]!=bytes.fromhex('0b000900'):
        raise ValueError('Unknown UV return')
    branch=sh4asm.Asm(tail);branch.bra('tramp');branch.nop();branch.labels['tramp']=TRAMP
    result[tail-prior.atlas.BASE:tail-prior.atlas.BASE+4]=branch.assemble()
    trampoline=sh4asm.Asm(TRAMP);trampoline.long_('target',UV)
    trampoline.mov_l_pc('target',0);trampoline.jmp(0);trampoline.nop()
    for address,data in ((FILL,fill),(UV,uv),(TRAMP,trampoline.assemble())):
        result[address-prior.atlas.BASE:address-prior.atlas.BASE+len(data)]=data
    for bank,data in zip(BANKS,raw_pages):
        off=prior.FONT_OFFSET+16+bank*128
        if len(data)!=8192 or any(system[off:off+8192]):raise ValueError('Font padding not empty')
        sy[off:off+8192]=data
    return bytes(result),bytes(sy),dict(fill_bytes=len(fill),uv_bytes=len(uv),uv_return=tail,
        budget_offset=budget_offset,extra_budget_units=384,forecast_ceiling_units=448)


def comparison(exe,system,images):
    from PIL import ImageDraw
    atlas=prior.atlas.tables()[0]
    font=system[prior.FONT_OFFSET:prior.FONT_OFFSET+589840]
    texts=['Beyond this hill is Pandemonium,','The person dear to this fellow,',
           'who was caught by the Inquisitor','for talking about love...',
           'Abel   Status   Ritual   Gabriel','Il1 O0 rn m  gypq  AVW 0123456789']
    result=Image.new('RGB',(1090,1000),'#100e09');draw=ImageDraw.Draw(result)
    for section,label in enumerate(('First port: reduced glyphs and opaque gray shading',
                                    'New native texture path: full glyphs, true alpha and shadow (offline sampling preview)')):
        y=section*495+12;draw.text((12,y),label,fill='white')
        for row,text in enumerate(texts):
            if section==0:line=prior.render_line(font,exe,text,False)
            else:
                line=Image.new('RGBA',(536,34));pen=0
                for ch in text:
                    index=0 if ch==' ' else prior.latin.charmap()[ch]
                    slot=atlas[index];local=slot%32
                    glyph=images[slot//32].crop((local%8*16,local//8*32,local%8*16+14,local//8*32+26))
                    # Texture retains all original rows; this approximates native GPU sampling.
                    glyph=glyph.resize((19,17),Image.Resampling.BILINEAR).resize((19,34),Image.Resampling.NEAREST)
                    line.alpha_composite(glyph,(pen,0))
                    pen+=exe[prior.vwf.ADV_TAB-prior.vwf.LOAD_BASE+index]+(4 if ch==' ' else 0)
            big=line.resize((1072,line.height*2),Image.Resampling.NEAREST)
            result.paste(big,(8,y+28+row*70),big)
    result.save(OUT/'comparison.png')


def build():
    import shutil
    if OUT.exists():raise ValueError('Preserve prior full-texture build')
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    if manifest['track_sha256']!=SOURCE_HASH:raise ValueError('Unknown first-port source')
    old=SOURCE/'disc2'/prior.TRACK
    if prior.digest(old)!=SOURCE_HASH:raise ValueError('Source track hash differs')
    exe,exe_lba=prior.read_file(old,'1ST_READ.BIN');system,sys_lba=prior.read_file(old,'SYSTEM.DAT')
    images,raw,counts=pages();new_exe,new_system,details=patch(exe,system,raw)
    allowed=[(FILL-prior.atlas.BASE,FILL-prior.atlas.BASE+256),
             (UV-prior.atlas.BASE,END-prior.atlas.BASE),
             (TRAMP-prior.atlas.BASE,TRAMP-prior.atlas.BASE+12),
             (details['uv_return']-prior.atlas.BASE,details['uv_return']-prior.atlas.BASE+4),
             (details['budget_offset'],details['budget_offset']+4),
             (prior.atlas.FILL_START-prior.atlas.BASE,prior.atlas.SIZE_STUB-prior.atlas.BASE)]
    sys_allowed=[(prior.FONT_OFFSET+16+b*128,prior.FONT_OFFSET+16+b*128+8192) for b in BANKS]
    changes={};count={}
    for name,lba,before,after,spans in (('1ST_READ.BIN',exe_lba,exe,new_exe,allowed),
                                     ('SYSTEM.DAT',sys_lba,system,new_system,sys_allowed)):
        offsets=np.flatnonzero(np.frombuffer(before,dtype='u1')!=np.frombuffer(after,dtype='u1'))
        if any(not any(lo<=i<hi for lo,hi in spans) for i in offsets):raise ValueError('Out-of-scope archive change')
        count[name]=len(offsets)
        changes.update({(lba-prior.inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i] for i in offsets.tolist()})
    OUT.mkdir();comparison(exe,system,images)
    for i,(image,data) in enumerate(zip(images,raw)):
        image.resize((512,512),Image.Resampling.NEAREST).save(OUT/('font-page-%d.png'%i))
        (OUT/('font-page-%d.vq'%i)).write_bytes(data)
    folder=OUT/'disc2';folder.mkdir()
    track_hash=prior.copy_track(old,folder/old.name,SOURCE_HASH,changes)
    for name,expected in (('1ST_READ.BIN',new_exe),('SYSTEM.DAT',new_system)):
        if prior.read_file(folder/old.name,name)[0]!=expected:raise ValueError('Archive readback differs')
    for path in old.parent.iterdir():
        if path.is_file() and path!=old:
            shutil.copy2(path,folder/path.name)
            if prior.digest(path)!=prior.digest(folder/path.name):raise ValueError('Companion differs')
    if prior.digest(old)!=SOURCE_HASH:raise ValueError('Source changed')
    report=dict(status='verified-skies-full-texture',disc=2,source=str(SOURCE.relative_to(ROOT)).replace('\\','/'),
        source_sha256=SOURCE_HASH,track_sha256=track_hash,changed_bytes=count,
        texture_format='Native VQ ARGB4444, lossless codebook per 128x128 page',codebook_entries=counts,
        original_source_cell=[12,24],atlas_cell=[16,32],sample=[14,26],native_quad=[19,17],
        source_glyph_rows_preserved=24,alpha='true ARGB4444 alpha plus one-source-pixel black shadow',
        bytes_per_page=8192,pages_per_admitted_record=4,font_page_buffer_sizes_unchanged=True,
        no_extra_sprite_nodes=True,native_fallback_retained=True,hd_texture_files_changed=0,
        hook_details=details,live_game_verified=False,
        limitations=['Framebuffer remains 640x240; cannot claim identical 640x480 Rayblade output.',
                    'Nonadmitted and mixed Japanese records retain the previous safe native fallback.',
                    'Preview approximates GPU filtering; fresh-boot rendering check required.'])
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['build']:build()
    else:
        p,r,c=pages();print('Lossless VQ codebooks:',c)
        print('Hook bytes:',len(fill_hook()),len(uv_hook()))
