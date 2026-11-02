"""Private v9: 80% displayed glyph size and admitted-only text advances.

Keep original glyph pixels, fallback text, selectors and all prior fixes.
Default is a read-only plan. Build writes a new local disc copy only.
"""
import argparse
import json
import shutil
import struct
import numpy as np
import skies_selector_fix as selector
import sh4asm

prior=selector.prior
font=selector.font
full=selector.full
v=prior.vwf
ROOT=prior.ROOT
SOURCE=ROOT/'build/skies-rayblade-font-v8-shop-footer'
SOURCE_SHA='3d837d45e759e10ae87a2e317ab1fec48d30c30e581266287a36822bf44ec425'
OUT=ROOT/'build/skies-rayblade-font-v9-size-match'
QUAD=(16,12)
HELPER=0x8C0F4900
HELPER_END=0x8C0F4A00
SMALL_ADV=0x8C0F4F00


def metric_helper():
    a=sh4asm.Asm(HELPER)
    for name,val in dict(records=v.LINE_RECORDS,states=prior.atlas.STATES,
                         old=v.ADV_TAB,small=SMALL_ADV,stride=400).items():a.long_(name,val)
    for r in (0,4,5,6):a.mov_l_dec(r,15)
    a.mov_l_pc('old',3);a.mov_l_pc('records',4);a.mov_l_pc('states',5);a.mov_i(32,6)
    a.label('scan');a.cmp_eq(1,4);a.bt('found')
    a.mov_l_pc('stride',0);a.add(0,4);a.add_i(1,5);a.add_i(-1,6)
    a.tst(6,6);a.bf('scan');a.bra('restore');a.nop()
    a.label('found');a.mov_b_at(5,0);a.extu_b(0,0);a._w(0xc880);a.bt('restore')
    a.mov_l_pc('small',3)
    a.label('restore')
    for r in (6,5,4,0):a.mov_l_inc(15,r)
    # Expanded dialogue adds four pixels to spaces before this call. Keep
    # menus at round(6*.8)=5, but dialogue at round((6+4)*.8)-4=4.
    a.tst(0,0);a.bf('read');a.mov_l_dec(0,15)
    a.mov_l_pc('small',0);a.cmp_eq(0,3);a.bf('space_restore')
    a.mov_w_atd_r0(8,8);a.cmp_eq_i(33);a.bf('space_restore')
    a.mov_l_inc(15,0);a.mov_b_r0(3,0);a.add_i(-1,0);a.rts();a.nop()
    a.label('space_restore');a.mov_l_inc(15,0)
    a.label('read');a.mov_b_r0(3,0);a.rts();a.nop()
    code=a.assemble()
    if HELPER+len(code)>HELPER_END:raise ValueError('Metric helper exceeds verified zero run')
    return code


def layout_code():
    a=prior.atlas.build_code(True);a.assemble()
    c=v.build_code(a.labels['slot_hook'],ui_fixes=True,natural_font=True,
        pixel_aspect_lut=prior.atlas.FORWARD,main_menu_padding=4,stance_menu_padding=4,
        dialogue_space_extra=4,latin_quad_width=28)
    c.assemble()
    return c


def patch(exe):
    out=bytearray(exe);spans=[]
    origin=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    small=bytes((n*4+2)//5 for n in exe[v.ADV_TAB-prior.atlas.BASE:v.ADV_TAB-prior.atlas.BASE+256])
    for addr,payload in ((HELPER,metric_helper()),(SMALL_ADV,small)):
        lo=addr-prior.atlas.BASE;hi=lo+len(payload)
        if any(exe[lo:hi]) or any(origin[lo:hi]):raise ValueError('Reserved size-match storage occupied')
        out[lo:hi]=payload;spans.append((lo,hi))
    before=full.uv_hook(native_quad=font.QUAD,sample=font.SAMPLE,compact_selector=True)
    after=full.uv_hook(native_quad=QUAD,sample=font.SAMPLE,compact_selector=True)
    lo=full.UV-prior.atlas.BASE;hi=lo+len(before)
    if exe[lo:hi]!=before or len(before)!=len(after):raise ValueError('Unexpected v8 UV hook')
    out[lo:hi]=after;spans.append((lo,hi))
    c=layout_code();site=c.labels['space_done']
    # Replace exactly the original table load + byte lookup, not a guessed
    # address. The subsequent EXTU.B is retained at its original location.
    lo=site-prior.atlas.BASE;expected=c.assemble()[site-v.CODE:site-v.CODE+4]
    if exe[lo:lo+4]!=expected:raise ValueError('Unknown advance lookup call site')
    branch=sh4asm.Asm(site);branch.labels['helper']=HELPER
    branch.bsr('helper');branch.nop();call=branch.assemble()
    if len(call) not in (4,6) or any(call[4:]):raise ValueError('Metric call does not fit original instructions')
    call=call[:4]  # Drop assembler's unused 4-byte literal-pool alignment.
    out[lo:lo+4]=call;spans.append((lo,lo+4))
    offsets=np.flatnonzero(np.frombuffer(exe,dtype='u1')!=np.frombuffer(out,dtype='u1')).tolist()
    if any(not any(a<=i<b for a,b in spans) for i in offsets):raise ValueError('Out-of-scope executable edit')
    return bytes(out),offsets,spans


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source v8 track differs')
    exe,lba=prior.read_file(source,'1ST_READ.BIN');after,offsets,spans=patch(exe)
    report=dict(status='verified-skies-size-match' if build else 'planned-skies-size-match',disc=2,
        writes=build,source=str(SOURCE.relative_to(ROOT)),source_sha256=SOURCE_SHA,
        native_quad=list(QUAD),display_quad=[16,24],sample=list(font.SAMPLE),
        previous_display_quad=[20,30],relative_scale=0.8,uniform_display_scale=1.0,
        changed_executable_bytes=len(offsets),helper_bytes=len(metric_helper()),
        executable_sha256=prior.sha(after),allowed_spans=spans,
        samples=[dict(character=ch,old=exe[v.ADV_TAB-prior.atlas.BASE+prior.latin.charmap()[ch]],
            new=after[SMALL_ADV-prior.atlas.BASE+prior.latin.charmap()[ch]]) for ch in 'StatusMi'],
        glyph_pixels_and_archives_unchanged=True,original_advance_table_unchanged=True,
        fallback_metrics_unchanged=True,selector_actions_and_fallback_unchanged=True,
        native_objective_cards_retained=24,saves_unchanged=True,in_game_verified=False,
        limitations=['Integer advances are rounded to nearest pixel. Nonadmitted fallback keeps its existing size.',
            'Earlier Yes/No corruption remains unresolved; this patch does not claim to repair it.'])
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous size-match build')
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir()
    changes={(lba-prior.inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i] for i in offsets}
    report['track_sha256']=prior.copy_track(source,folder/source.name,SOURCE_SHA,changes)
    if prior.read_file(folder/source.name,'1ST_READ.BIN')[0]!=after:raise ValueError('Executable readback differs')
    for name in ('SYSTEM.DAT','MAP.DAT','SCENARIO.DAT'):
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
