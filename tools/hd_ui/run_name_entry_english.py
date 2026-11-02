"""Independent local name-entry test; never controls another running game."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import buddy_tv_control as profile

BUILD=Path('M:/Black-Matrix-AD-private-tests/name-entry-english-v1')
OUT=BUILD/'play'
CUE=BUILD/'disc1/Black-Matrix Advanced (Japan) (Disc 1).cue'
EXE=BUILD/'1ST_READ.BIN'
SELECTION_BUILD=Path('M:/Black-Matrix-AD-private-tests/english-selection-v2')
NAME_STATUS='private-name-entry-runtime-pending'
SELECTION_STATUS='private-english-selection-runtime-pending'


def verify(build=BUILD,status=NAME_STATUS):
    report=json.loads((build/'manifest.json').read_text())
    if report['status']!=status:raise ValueError('Unknown English selection build')
    digest=hashlib.sha256((build/'1ST_READ.BIN').read_bytes()).hexdigest()
    if any(d['executable_sha256']!=digest for d in report['discs']):raise ValueError('Executable changed')
    # Authenticate the complete disc that the launcher actually opens.
    for row in report['files']:
        if not row['path'].startswith('disc1/'):continue
        with (build/row['path']).open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        if h!=row['sha256']:raise ValueError('Disc file changed: '+row['path'])
    return digest


def prepare(build=BUILD,status=NAME_STATUS):
    digest=verify(build,status);out=build/'play'
    cue=build/'disc1/Black-Matrix Advanced (Japan) (Disc 1).cue';exe=build/'1ST_READ.BIN'
    if not out.exists():profile.prepare(out,0,cue,exe,digest)
    else:
        saved=json.loads((out/'profile.json').read_text())
        if saved['cue']!=str(cue) or saved['executable_sha256']!=digest or saved['cable']!=0:
            raise ValueError('Existing test profile differs; preserve it')


def launch(build=BUILD,status=NAME_STATUS):
    prepare(build,status);out=build/'play'
    cue=build/'disc1/Black-Matrix Advanced (Japan) (Disc 1).cue'
    with (out/('name-entry-launch-%d.log'%time.time())).open('xb') as log:
        proc=subprocess.Popen([str(out/'flycast.exe'),str(cue)],cwd=out,
            stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    print('New name-entry test opened. Choose New Game and reach name entry.')
    print('Latin should be selected. Controls: Hira / Kata / Latin / Back / Done.')
    if status==SELECTION_STATUS:print('The master-selection splash should read: Choose your master')
    print('No game inputs sent. Other emulator windows and saves are unchanged. PID:',proc.pid)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--launch',action='store_true')
    p.add_argument('--selection-v2',action='store_true');a=p.parse_args()
    build,status=(SELECTION_BUILD,SELECTION_STATUS) if a.selection_v2 else (BUILD,NAME_STATUS)
    if a.launch:launch(build,status)
    elif a.prepare:prepare(build,status)
    else:print('Verified English selection executable:',verify(build,status))
