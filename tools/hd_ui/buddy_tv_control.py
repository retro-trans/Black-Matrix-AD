"""One-variable private TV control, in a new profile; no user app control.

Uses the delivered Disc1 unchanged, NOT the failed native-fallback candidate.
Only the cable differs from the original diagnostic's rendering configuration.
All new BIOS initialization copies, VMUs, logs and captures stay in this profile.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import time
import prepare_disc1_buddy_diagnostic as prep

ROOT = prep.ROOT
OUT = Path('M:/Black-Matrix-AD-private-tests/buddy-tv-20261102')
CUE = ROOT / 'output/patched-discs-2026-11-01/disc1/Black-Matrix Advanced (Japan) (Disc 1).cue'
SOURCE = ROOT / 'build/disc1-buddy-diagnostic-v1'
EXE = ROOT / 'build/disc1-reconstructed-vga-v1/final-payloads/1ST_READ.BIN'
EXE_SHA = '94606624f94c22b12b7bc5b48da513c222c19941722fbbae0511b2f1d7e20e8b'


def settings(output=OUT,cable=3):
    cfg = prep.settings()
    cfg['config']['Dreamcast.Cable'] = str(cable)
    for key, subdir in [('Dreamcast.BiosPath', 'bios'), ('Dreamcast.SavePath', 'data'),
                        ('Dreamcast.SavestatePath', 'data'), ('Dreamcast.VMUPath', 'data')]:
        cfg['config'][key] = str(output / subdir)
    return cfg


def prepare(output=OUT,cable=3,cue=CUE,executable=EXE,expected_sha=EXE_SHA):
    OUT=output;CUE=cue;EXE=executable
    if OUT.exists():
        raise ValueError('Preserve existing TV control')
    files = ['flycast.exe', 'bios/dc_boot.bin', 'bios/dc_flash.bin']
    for name in files:
        if not (SOURCE / name).is_file():raise ValueError('Missing local test dependency')
    if hashlib.sha256((SOURCE/'flycast.exe').read_bytes()).hexdigest()!=prep.EXE_SHA:
        raise ValueError('Unknown local emulator')
    payload = EXE.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=expected_sha:raise ValueError('Unknown test executable')
    if not CUE.is_file():raise ValueError('Missing delivered Disc1')
    if shutil.disk_usage(OUT.anchor).free < 128*1024*1024:
        raise ValueError('Need room for a separate profile and diagnostic captures')
    OUT.mkdir(parents=True);(OUT/'bios').mkdir();(OUT/'data').mkdir()
    for name in files:
        shutil.copy2(SOURCE/name,OUT/name)
        if (SOURCE/name).read_bytes()!=(OUT/name).read_bytes():raise ValueError('Copy mismatch')
    # Same pristine diagnostic initialization, not any user VMU or saved game.
    shutil.copy2(prep.SOURCE/'data/dc_nvmem.bin',OUT/'data/dc_nvmem.bin')
    with (OUT/'emu.cfg').open('x',encoding='utf-8') as f:settings(OUT,cable).write(f)
    lua=(ROOT/'tools/hd_ui/disc1_buddy_diagnostic.lua').read_text()
    words=', '.join(hex(x) for x in struct.unpack('<16I',payload[:64]))
    lua=lua.replace('local expected = {0x00000000}', 'local expected = {'+words+'}')
    # Capture video/list telemetry only. Do not patch RAM or send controls.
    lua=lua.replace("note('read-only buddy diagnostic initialized; no saves imported')", """
local function video_note()
    note(string.format('TV-control sdk_mode=%08x fb=%dx%d list=%08x..%08x bios_vector=%08x',
        flycast.memory.read32(0x8c2c5a18), flycast.memory.read32(0x8c2936fc),
        flycast.memory.read32(0x8c293700), flycast.memory.read32(0x8c2935d0),
        flycast.memory.read32(0x8c2935d4), flycast.memory.read32(0x8c0000bc)))
end
note('read-only buddy diagnostic initialized; no saves imported')
""")
    lua=lua.replace("if frame % 120 == 0 then", "if frame % 120 == 0 then\n            if active() then video_note() end")
    if cable==0:lua=lua.replace('TV-control','VGA-buffer-candidate')
    with (OUT/'buddy-diagnostic.lua').open('x',encoding='utf-8') as f:f.write(lua)
    report=dict(status='prepared-runtime-pending',cue=str(CUE),profile=str(OUT),
                executable_sha256=expected_sha,emulator_sha256=prep.EXE_SHA,
                cable=cable,comparison='TV control' if cable==3 else 'VGA packet-budget candidate',
                original_and_delivered_discs_unchanged=True,user_saves_imported=False,
                user_emulator_changed=False,automated_input=False,guest_writes=False)
    with (OUT/'profile.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2),flush=True)


def launch(output=OUT,cue=CUE,executable=EXE,instructions=None):
    OUT=output;CUE=cue;EXE=executable
    if not OUT.is_dir():raise ValueError('Prepare control first')
    # This new test profile has an independent executable and fresh VMUs.
    with (OUT/('launch-%d.log'%int(time.time()))).open('xb') as log:
        proc=subprocess.Popen([str(OUT/'flycast.exe'),str(CUE)],cwd=OUT,
            stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Private comparison window opened. '+(instructions or 'Choose New Game and reach buddy selection.'),flush=True)
    print('Your regular Flycast, discs and saves are unchanged. Test PID:',proc.pid,flush=True)
    # Wait for BIOS initialization before scanning the owned process context.
    import sys
    sys.path.insert(0,str(ROOT/'tools'))
    import ramdump
    prefix=EXE.read_bytes()[:128]
    reader=ramdump.Proc(proc.pid)
    try:
        ready=False
        for _ in range(45):
            if proc.poll() is not None:break
            for base,size in reader.regions():
                for offset in range(0,min(size,1<<32)-ramdump.RAM_SIZE+1,65536):
                    if (reader.read(base+offset+65536,128)==prefix and
                        reader.read(base+offset+0xce370,4)==struct.pack('<I',0x8c26bb60)):
                        ready=True;break
                if ready:break
            if ready:break
            time.sleep(1)
    finally:ramdump.k32.CloseHandle(reader.h)
    if ready:
        import buddy_cpu_watch
        buddy_cpu_watch.run(proc.pid,OUT)
    else:print('Game did not initialize; no CPU watch started.',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--launch',action='store_true')
    args=p.parse_args()
    if args.prepare:prepare()
    if args.launch:launch()
