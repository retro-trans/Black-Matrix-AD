"""Opt-in Disc2 VGA boot compatibility; no forced renderer/video conversion.

Enable only the existing IP.BIN VGA bit. Rebuild raw sector EDC/ECC inherited
from emulator-only ancestors, while preserving all other user-data bytes.
"""
import argparse
import json
import shutil
import struct
import sys
import numpy as np
import skies_confirm_footer as previous
sys.path.insert(0,str(previous.ROOT/'tools'))
import mode1_sector
import sh4asm

prior=previous.prior
ROOT=previous.ROOT
SOURCE=previous.OUT
SOURCE_SHA='df0f6f1ab40dd21fed902afe8f98e2499eeb53a5772288b50b578776cdcd3563'
OUT=ROOT/'build/skies-vga-compat-v1'
CABLE_OUT=ROOT/'build/skies-vga-compat-v2'
HELPER=0x8C0F4860
HELPER_END=0x8C0F4900
WRAPPER=0x8C0102D8
CALL_POINTER=0x278
BOOT_OFFSET=0x3d
CHUNK_SECTORS=4096


def patch_boot(boot):
    if len(boot)!=32768 or boot[:16]!=b'SEGA SEGAKATANA ' or boot[0x80:0x8f]!=b'BLACK MATRIX AD':
        raise ValueError('Unexpected Black Matrix boot sector')
    if boot[BOOT_OFFSET]!=ord('0'):raise ValueError('Unknown/already enabled VGA flag')
    after=bytearray(boot);after[BOOT_OFFSET]=ord('1')
    if [i for i,(a,b) in enumerate(zip(boot,after)) if a!=b]!=[BOOT_OFFSET]:raise ValueError('Unexpected boot change')
    return bytes(after)


def cable_helper():
    a=sh4asm.Asm(HELPER);a.long_('gpio',0xff800030);a.long_('original',WRAPPER)
    a.mov_l_pc('gpio',0);a.mov_w_at(0,0)
    for _ in range(4):a._w(0x4009)  # SHLR2 R0; cable ID is bits8..9
    a._w(0xc903);a.tst(0,0);a.bf('tv')
    a.mov_i(0x11,4)  # Existing SDK VGA cable selector, NOT forced480 mode34.
    a.label('tv');a.mov_l_pc('original',0);a.jmp(0);a.nop()
    result=a.assemble()
    if HELPER+len(result)>HELPER_END:raise ValueError('Cable helper exceeds guarded space')
    return result


def patch_exe(exe):
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    if exe[CALL_POINTER:CALL_POINTER+4]!=struct.pack('<I',WRAPPER) or exe[0xc4:0xce]!=original[0xc4:0xce]:
        raise ValueError('Unknown startup video call')
    lo=HELPER-prior.atlas.BASE;hi=lo+len(cable_helper())
    if any(original[lo:hi]) or any(exe[lo:hi]):raise ValueError('Cable helper storage occupied')
    after=bytearray(exe);struct.pack_into('<I',after,CALL_POINTER,HELPER);after[lo:hi]=cable_helper()
    return bytes(after)


def run(build=False,cable_aware=False):
    output=CABLE_OUT if cable_aware else OUT
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source v14 track differs')
    with source.open('rb') as f:
        boot=prior.inject._extent(f,45000,32768);directory=list(prior.inject.iso_files(f))
    target=patch_boot(boot)
    exe,_=prior.read_file(source,'1ST_READ.BIN')
    new_exe=patch_exe(exe) if cable_aware else exe
    if exe[0xcc:0xce]!=bytes.fromhex('10e4'):raise ValueError('Original startup mode was changed')
    exe_delta=[i for i,(a,b) in enumerate(zip(exe,new_exe)) if a!=b]
    _,exe_lba=prior.read_file(source,'1ST_READ.BIN')
    user_edits={BOOT_OFFSET:ord('1')}
    user_edits.update({(exe_lba-45000+i//2048)*2048+i%2048:new_exe[i] for i in exe_delta})
    report=dict(status=('sector-verified-vga-cable-test' if cable_aware else 'sector-verified-vga-boot-test') if build else 'planned-vga-compatibility-test',writes=build,
        disc=2,source=str(SOURCE.relative_to(ROOT)),source_sha256=SOURCE_SHA,
        boot_flag_offset=BOOT_OFFSET,boot_flag_before='0',boot_flag_after='1',changed_user_data_bytes=len(user_edits),
        executable_sha256=prior.sha(new_exe),changed_executable_bytes=len(exe_delta),all_other_game_payloads_unchanged=True,
        startup_mode='0x11 for VGA, original0x10 for other cables' if cable_aware else '0x10 unchanged',
        cable_aware=cable_aware,forced_480_conversion=False,sector_edc_ecc='pending' if build else 'will regenerate/verify',
        vga_cold_boot_verified=False,non_vga_cold_boot_verified=False,physical_hardware_verified=False,
        normal_launcher_unchanged=True,saves_unchanged=True,private_local_test_only=True)
    if not build:print(json.dumps(report,indent=2));return
    if output.exists():raise ValueError('Preserve previous VGA test')
    output.mkdir();folder=output/'disc2';folder.mkdir();dest=folder/source.name
    sectors=0;changed=0;user_changes=0
    with source.open('rb') as inp,dest.open('xb') as out:
        while raw:=inp.read(2352*CHUNK_SECTORS):
            candidate=bytearray(raw)
            for offset,value in user_edits.items():
                sector,inside=divmod(offset,2048)
                if sectors<=sector<sectors+len(raw)//2352:candidate[(sector-sectors)*2352+16+inside]=value
            repaired=mode1_sector.regenerate(candidate)
            a=np.frombuffer(raw,dtype='u1').reshape(-1,2352)
            b=np.frombuffer(repaired,dtype='u1').reshape(-1,2352)
            dif=np.argwhere(a[:,16:2064]!=b[:,16:2064])
            if len(dif):
                if any(user_edits.get((sectors+int(row))*2048+int(col))!=int(b[row,16+col]) for row,col in dif):
                    raise ValueError('Unrelated user data changed')
                user_changes+=len(dif)
            if not np.array_equal(a[:,:16],b[:,:16]):raise ValueError('Raw sector header changed')
            changed+=int(np.any(a!=b,axis=1).sum());sectors+=len(a);out.write(repaired)
            if sectors%(CHUNK_SECTORS*16)==0:print('Checked/copied %d sectors'%sectors,flush=True)
    if user_changes!=len(user_edits) or dest.stat().st_size!=source.stat().st_size:raise ValueError('Invalid complete-track delta')
    # Independent readback over the complete output, not just changed extents.
    with dest.open('rb') as f:
        while raw:=f.read(2352*CHUNK_SECTORS):
            if mode1_sector.regenerate(raw)!=raw:raise ValueError('Output EDC/ECC readback failed')
    with dest.open('rb') as f:
        if prior.inject._extent(f,45000,32768)!=target or list(prior.inject.iso_files(f))!=directory:
            raise ValueError('Boot/directory readback differs')
    report['files']=[]
    for name,lba,length in directory:
        before,_=prior.read_file(source,name);after,_=prior.read_file(dest,name)
        if after!=(new_exe if name=='1ST_READ.BIN' else before):raise ValueError('Payload changed: '+name)
        report['files'].append(dict(name=name,size=length,sha256=prior.sha(after)))
    report['companions']=[]
    for path in source.parent.iterdir():
        if path.is_file() and path!=source:
            shutil.copy2(path,folder/path.name);digest=prior.digest(path)
            if prior.digest(folder/path.name)!=digest:raise ValueError('Companion differs')
            report['companions'].append(dict(file=path.name,sha256=digest))
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('Source changed')
    report.update(track_sha256=prior.digest(dest),checked_sectors=sectors,
                  changed_raw_sectors=changed,sector_edc_ecc='all output sectors regenerated and readback verified')
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('files','companions')},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--cable-aware',action='store_true')
    a=p.parse_args();run(a.build,a.cable_aware)
