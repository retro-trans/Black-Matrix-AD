"""Private name-entry-only English controls; retain all three keyboard pages.

Use ten previously empty native MFD cells, not Japanese glyph replacements.
The two control quads are adjacent (28px), so words have normal letter spacing.
Only the name-entry initializer defaults to page2; no keyboard tables are moved.
"""
import hashlib
import json
from pathlib import Path
import shutil
import struct

from PIL import Image, ImageDraw
import numpy as np
import latin
import sh4asm
import skies_rayblade_font as font
import buddy_vga_buffer as budget
import package_vga_buffer_pair as pair
import mode1_sector

ROOT=budget.ROOT
SOURCE=pair.OUT
OUT=Path('M:/Black-Matrix-AD-private-tests/name-entry-english-v1')
EXE_SHA='7825782b7e85f3e1085e9aa330094d69f83972ab5b58bbbecdf1e1186904ee5b'
BASE=0x8c010000
HELPER=0x8c0f48c0
END=0x8c0f48e0
MODE=0x8c1eb250
INIT=0x8c0641aa
NAME=0x1cd6a0
CONTROLS=NAME+16+3*192
FIRST=327
LABELS=('Hira','Kata','Latin','Back','Done')
PITCH_SITES=(0x8c064f42,0x8c064f48,0x8c064f4e,0x8c064f54,
             0x8c065146,0x8c06514c,0x8c065152,0x8c065158)
CAPTURE=Path('M:/Black-Matrix-AD-private-tests/name-entry-20261102/name-screen-ram.bin')
CAPTURE_SHA='bc483742e25848d38ee26dd9d1e800482eedf68502de6ea2b3bc69385a688cd1'


def sha(b):return hashlib.sha256(b).hexdigest()


def helper():
    # Entry R2=1. Preserve every register, PR, SP and T, restoring the original
    # R1=MODE too. The original state-store is in the caller's JMP delay slot.
    a=sh4asm.Asm(HELPER);a.long_('mode',MODE)
    a.mov_l_pc('mode',1);a.add_i(1,2);a.mov_w_store(2,1)
    a._w(0x000b);a.add_i(-1,2)
    return a.assemble()


def labels(exe,system):
    native=system[font.FONT_OFFSET:font.FONT_OFFSET+589856]
    result=[]
    for label in LABELS:
        image=Image.new('L',(80,16));pen=0
        for ch in label:
            index=latin.charmap()[ch]
            glyph=font.cell(native,index)
            image.paste(glyph,(pen,0),glyph.point(lambda p:255 if p else 0))
            pen+=exe[font.vwf.ADV_TAB-BASE+index]-1
        if image.getbbox()[2]>56:raise ValueError('Label exceeds two native control quads')
        image=image.crop((0,0,56,16));result.append(image)
    return result


def patch(exe,system,ram):
    if sha(exe)!=EXE_SHA:raise ValueError('Unknown VGA-buffer executable')
    if sha(ram)!=CAPTURE_SHA or ram[0x10000:0x11000]!=exe[:4096]:
        raise ValueError('Name-entry capture is not authenticated')
    original=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    lo,hi=HELPER-BASE,END-BASE
    if any(exe[lo:hi]) or any(original[lo:hi]) or any(ram[HELPER-0x8c000000:END-0x8c000000]):
        raise ValueError('Initializer helper reservation occupied')
    if system[NAME:NAME+16]!=b'NAME\x10'+bytes(11):raise ValueError('Unknown NAME archive')
    expected=struct.pack('<12H',11,*[int.from_bytes(c.encode('cp932'),'big') for c in 'かなカナ英字戻る終了'],0x8151)
    if system[CONTROLS:CONTROLS+24]!=expected:raise ValueError('Unknown controls record')
    ex,sy=bytearray(exe),bytearray(system);ex_spans=[];sy_spans=[]
    def edit(address,before,after):
        off=address-BASE
        if exe[off:off+len(before)]!=before:raise ValueError('Unknown instruction '+hex(address))
        ex[off:off+len(after)]=after;ex_spans.append((off,off+len(after)))
    edit(0x8c064274,struct.pack('<I',MODE),struct.pack('<I',HELPER))
    edit(0x8c0641d4,bytes.fromhex('22230b004121'),bytes.fromhex('2b4122230900'))
    ex[lo:lo+len(helper())]=helper();ex_spans.append((lo,lo+len(helper())))
    for address in PITCH_SITES:edit(address,b'\x22\x70',b'\x1c\x70')
    images=labels(exe,system)
    original_font=(ROOT/'extracted/FONT.BIN').read_bytes()
    for row,image in enumerate(images):
        for half in range(2):
            index=FIRST+row*2+half;off=font.FONT_OFFSET+16+index*128
            if any(system[off:off+128]) or any(original_font[16+index*128:16+(index+1)*128]):
                raise ValueError('Native glyph slot is not empty')
            tile=Image.new('L',(32,16));tile.paste(image.crop((half*28,0,half*28+28,16)))
            sy[off:off+128]=font.encoded(tile);sy_spans.append((off,off+128))
            code=0x8240+index-128
            if latin.sjis_to_index(code)!=index:raise ValueError('Native glyph mapping differs')
            struct.pack_into('<H',sy,CONTROLS+2+(row*2+half)*2,code)
    sy_spans.append((CONTROLS+2,CONTROLS+22))
    for before,after,spans in [(exe,ex,ex_spans),(system,sy,sy_spans)]:
        changes=np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(after,'u1'))
        if any(not any(a<=int(i)<z for a,z in spans) for i in changes):raise ValueError('Out-of-scope edit')
    return bytes(ex),bytes(sy),dict(executable_spans=ex_spans,system_spans=sy_spans,
        labels=list(LABELS),default_page=2,all_keyboard_tables_and_default_names_unchanged=True,
        vga_buffer_correction_unchanged=True,source_executable_sha256=sha(exe),
        executable_sha256=sha(ex),system_sha256=sha(sy),helper_address=hex(HELPER))


def preview(images,path):
    canvas=Image.new('RGB',(560,410),'#151510');draw=ImageDraw.Draw(canvas)
    draw.text((16,12),'Native font preview (not a gameplay capture)',fill='white')
    palette=font.PALETTE
    for row,(label,im) in enumerate(zip(LABELS,images)):
        rgba=Image.new('RGBA',im.size);rgba.putdata([palette[p] for p in im.getdata()])
        # Same 28x14 source sampling and 2x vertical display as the live nodes.
        shown=rgba.crop((0,0,56,14)).resize((224,112),Image.Resampling.NEAREST)
        # At 2x inspection scale: 56x28 display ->112x56.
        shown=shown.resize((112,56),Image.Resampling.NEAREST)
        canvas.paste(shown,(22,46+row*70),shown)
        draw.text((160,64+row*70),label+(' (default)' if row==2 else ''),fill='#eeb848')
    canvas.save(path)


def build():
    if OUT.exists():raise ValueError('Preserve previous name-entry build')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient free space')
    inputs=json.loads((SOURCE/'manifest.json').read_text())
    expected={row['path']:row['sha256'] for row in inputs['files']}
    prior=budget.legacy.footer.prior
    ram=CAPTURE.read_bytes();OUT.mkdir();reports=[];files=[];shared=None
    for disc in (1,2):
        folder=SOURCE/f'disc{disc}';track=folder/f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
        exe,elba=prior.read_file(track,'1ST_READ.BIN');system,slba=prior.read_file(track,'SYSTEM.DAT')
        new_exe,new_system,report=patch(exe,system,ram)
        if shared is not None and new_exe!=shared:raise ValueError('Disc executables diverged')
        shared=new_exe;changes={};touched=[]
        for lba,before,after in [(elba,exe,new_exe),(slba,system,new_system)]:
            delta=np.flatnonzero(np.frombuffer(before,'u1')!=np.frombuffer(after,'u1')).tolist()
            edits,sectors=budget.legacy.sectors.sector_changes(track,lba,after,delta)
            if set(edits)&set(changes):raise ValueError('Overlapping file edits')
            changes.update(edits);touched+=sectors
        out=OUT/f'disc{disc}';out.mkdir();target=out/track.name
        source_hash=expected[track.relative_to(SOURCE).as_posix()]
        digest=prior.copy_track(track,target,source_hash,changes)
        with track.open('rb') as f:
            directory=list(prior.inject.iso_files(f));boot=prior.inject._extent(f,45000,32768)
        with target.open('rb') as f:
            if list(prior.inject.iso_files(f))!=directory or prior.inject._extent(f,45000,32768)!=boot:
                raise ValueError('Boot or directory changed')
            for sector in touched:
                f.seek(sector*2352);raw=f.read(2352)
                if mode1_sector.regenerate(raw)!=raw:raise ValueError('Sector parity invalid')
        for name,_,_ in directory:
            old,_=prior.read_file(track,name);actual,_=prior.read_file(target,name)
            want={'1ST_READ.BIN':new_exe,'SYSTEM.DAT':new_system}.get(name,old)
            if actual!=want:raise ValueError('Payload verification failed: '+name)
        files.append(dict(path=target.relative_to(OUT).as_posix(),sha256=digest,bytes=target.stat().st_size))
        for p in folder.iterdir():
            if p.is_file() and p!=track:
                dst=out/p.name
                with p.open('rb') as src,dst.open('xb') as dest:shutil.copyfileobj(src,dest)
                h=pair.digest(dst)
                if h!=expected[p.relative_to(SOURCE).as_posix()]:raise ValueError('Companion changed')
                files.append(dict(path=dst.relative_to(OUT).as_posix(),sha256=h,bytes=dst.stat().st_size))
        report.update(disc=disc,source_track_sha256=source_hash,track_sha256=digest,parity_sectors=touched)
        reports.append(report)
        if disc==1:
            (OUT/'1ST_READ.BIN').write_bytes(new_exe)
            preview(labels(exe,system),OUT/'controls-preview.png')
        print('Disc',disc,'name-entry build and payload verification complete.',flush=True)
    for row in files:
        if pair.digest(OUT/row['path'])!=row['sha256']:raise ValueError('Final artifact hash mismatch')
    for row in inputs['files']:
        if pair.digest(SOURCE/row['path'])!=row['sha256']:raise ValueError('Previous delivery changed')
    result=dict(status='private-name-entry-runtime-pending',files=files,discs=reports,
        gameplay_verified=False,physical_hardware_verified=False,private_local_only=True,
        previous_delivery_and_originals_unchanged=True,read_only_reference_capture_sha256=CAPTURE_SHA)
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    print('New local pair:',OUT,flush=True)


if __name__=='__main__':build()
