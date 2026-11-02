"""Private combined-disc variant: enable the native real Zero unlock at init.

No secret-code bypass branches, forced route, save writes, new code allocation,
movie edits or artwork changes. Original/earlier discs remain read-only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

import combine_imagegen_prologue as combined
import name_entry_english as names
import mode1_sector

ROOT = combined.ROOT
SOURCE = combined.OUT
OUT = ROOT / 'output/patched-discs-zero-unlocked-2026-11-02'
STATUS = 'private-zero-unlocked-runtime-pending'
BASE = 0x8c010000
INIT = 0x8c05b9e0
FLAG = 0x8c1d4d08
SELECTED = FLAG + 4
INIT_BYTES = bytes.fromhex('35d300e435d2422336d335d1422236d24221422336d335d1422236d2422142230b004222')
LITERAL_BYTES = bytes.fromhex('e84c1d8cec4c1d8cf04c1d8cf44c1d8cf84c1d8c004d1d8c084d1d8c0c4d1d8c')
EDITS = ((0x8c05b9fa, 0xd236, 0x1341),   # clear selection via @(4,R3)
         (0x8c05b9fe, 0x2342, 0xe202),   # R2=2, the native TRUE unlock
         (0x8c05ba02, 0x2242, 0x2322))   # return delay slot: flag=R2
# Reuse the established profile containing the user's original VMUs. Do not
# generate another blank test profile or import/overwrite cards in a live game.
PLAY = ROOT / 'build/skies-vga-compat-v2/play'
TRACK_HASHES = {
    1: 'da28c0e15f912392231131e2b71b07323ce18f834293dea34248e791c5037d83',
    2: 'cd69dffd70685892d85d098eda88d8adef0454d3d199bc3953e550c26a91bee8',
}
READER = combined.READER


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch(exe):
    if sha(exe) != combined.EXE_SHA:
        raise ValueError('Unknown combined executable; preserve it')
    if exe[INIT-BASE:INIT-BASE+len(INIT_BYTES)] != INIT_BYTES:
        raise ValueError('Native selection initializer differs')
    if exe[0x8c05bab8-BASE:0x8c05bad8-BASE] != LITERAL_BYTES:
        raise ValueError('Native selection globals differ')
    result = bytearray(exe)
    for address, before, after in EDITS:
        off = address - BASE
        if struct.unpack_from('<H', exe, off)[0] != before:
            raise ValueError('Unexpected instruction at '+hex(address))
        struct.pack_into('<H', result, off, after)
    delta = [i for i, (a, b) in enumerate(zip(exe, result)) if a != b]
    allowed = {address-BASE+i for address, _, _ in EDITS for i in (0, 1)}
    if set(delta) != allowed or len(result) != len(exe):
        raise ValueError('Unexpected executable delta')
    return bytes(result), delta


def build(out=OUT, patcher=patch, status=STATUS, edits=EDITS,
          first_choice='Zero', launcher='Zero Unlocked', source=SOURCE,
          source_status=combined.STATUS, source_track_hashes=TRACK_HASHES,
          extra_report=None, readme_notes=''):
    # New variants get new paths; default invocation preserves the original
    # Zero-highlighted build and its reproducible patch bytes.
    OUT = out
    STATUS = status
    SOURCE = source
    TRACK_HASHES = source_track_hashes
    if OUT.exists():
        raise ValueError('Preserve existing disc build')
    if shutil.disk_usage(OUT.anchor).free < 3*1024**3:
        raise ValueError('Insufficient free space on E:')
    previous = json.loads((SOURCE/'manifest.json').read_text())
    if previous['status'] != source_status:
        raise ValueError('Unknown source pair')
    expected = {row['path']: row for row in previous['files']}
    if len(expected) != 8:
        raise ValueError('Expected two complete three-track discs')
    for disc, digest in TRACK_HASHES.items():
        key = f'disc{disc}/Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
        if expected[key]['sha256'] != digest:
            raise ValueError('Unexpected source disc identity')
    combined.verify_files(SOURCE, previous['files'])
    combined.cue_checks(SOURCE)
    original = (SOURCE/'1ST_READ.BIN').read_bytes()
    after, delta = patcher(original)
    OUT.mkdir()
    files, reports = [], []
    for disc in (1, 2):
        folder = SOURCE/f'disc{disc}'
        dest = OUT/f'disc{disc}'
        dest.mkdir()
        track = folder/f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
        target = dest/track.name
        exe, lba = READER.read_file(track, '1ST_READ.BIN')
        if exe != original:
            raise ValueError('Disc-specific executable differs')
        changes, touched = names.budget.legacy.sectors.sector_changes(track, lba, after, delta)
        digest = READER.copy_track(track, target, TRACK_HASHES[disc], changes)
        with track.open('rb') as f:
            directory = list(READER.inject.iso_files(f))
            boot = READER.inject._extent(f, 45000, 32768)
        with target.open('rb') as f:
            if list(READER.inject.iso_files(f)) != directory or READER.inject._extent(f, 45000, 32768) != boot:
                raise ValueError('Boot/directory changed')
            for sector in touched:
                f.seek(sector*2352)
                raw = f.read(2352)
                if mode1_sector.regenerate(raw) != raw:
                    raise ValueError('Invalid raw-sector parity')
        # Full per-file verification, including all movies, artwork and scripts.
        for name, _, _ in directory:
            old, _ = READER.read_file(track, name)
            actual, _ = READER.read_file(target, name)
            if actual != (after if name == '1ST_READ.BIN' else old):
                raise ValueError('Unexpected ISO payload change: '+name)
        files.append(dict(path=target.relative_to(OUT).as_posix(), bytes=target.stat().st_size, sha256=digest))
        for row in previous['files']:
            if not row['path'].startswith(f'disc{disc}/') or row['path'].endswith('(Track 3).bin'):
                continue
            dst = OUT/row['path']
            with (SOURCE/row['path']).open('rb') as src, dst.open('xb') as out:
                shutil.copyfileobj(src, out, 4*1024*1024)
            files.append(dict(row))
        reports.append(dict(disc=disc, executable_sha256=sha(after), source_track_sha256=TRACK_HASHES[disc],
                            track_sha256=digest, parity_sectors=touched))
        print('Disc', disc, 'verified:', len(delta), 'EXE bytes and sector parity changed.', flush=True)
    combined.verify_files(OUT, files)
    combined.cue_checks(OUT)
    combined.verify_files(SOURCE, previous['files'])
    (OUT/'1ST_READ.BIN').write_bytes(after)
    for preview in SOURCE.glob('*-preview.png'):
        shutil.copy2(preview, OUT/preview.name)
    (OUT/'Black Matrix AD.m3u').write_text(''.join(
        f'disc{d}/Black-Matrix Advanced (Japan) (Disc {d}).cue\n' for d in (1, 2)))
    report = dict(status=STATUS, files=files, discs=reports, source=str(SOURCE), source_files=previous['files'],
                  source_executable_sha256=sha(original), executable_sha256=sha(after),
                  edits=[dict(address=hex(a), before=hex(b), after=hex(c)) for a, b, c in edits],
                  changed_executable_bytes=delta, native_unlock_flag=hex(FLAG), native_unlock_value=2,
                  initially_highlighted_character=first_choice,
                  artwork=previous.get('artwork', {}), prologue_sha256=combined.MOVIE_SHA,
                  only_executable_and_associated_sector_parity_changed=True,
                  all_movie_artwork_font_script_and_other_payloads_unchanged=True,
                  original_and_previous_discs_unchanged=True, saves_and_emulator_profiles_unchanged=True,
                  private_local_only=True, gameplay_verified=False, physical_hardware_verified=False)
    if extra_report:
        if set(extra_report).intersection(report):
            raise ValueError('Extra metadata must not override verification fields')
        report.update(extra_report)
    (OUT/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(
        readme_notes+
        'PRIVATE local English disc pair: Zero unlocked from the first New Game.\n'
        'No secret input required. Uses native unlock value 2; all six characters remain selectable.\n'
        f'The menu initially highlights {first_choice}; you can choose anyone. No choice is auto-confirmed.\n'
        'Movie timing repair, selected Choose your master artwork, VGA buffer and font/name fixes retained.\n'
        f'Only {len(delta)} executable bytes and associated raw-sector parity differ from the source pair.\n'
        f'Use Play - Disc 1 - {launcher}.cmd (or Disc 2) in the project folder.\n'
        'Close Flycast first. These launchers reuse build/skies-vga-compat-v2/play and its old VMUs.\n'
        'Old saves remain on their existing VMUs (latest September 30 save: Port A, Slot 2).\n'
        'No cards copied/overwritten, no blank profile made. Existing saves are not converted to the Zero route.\n'
        'Code-level tests and full disc readbacks verified. Fresh gameplay and hardware tests pending.\n'
        'Originals and previous builds untouched. Do not upload complete game binaries.\n')
    print('New private pair (Zero unlocked; first choice '+first_choice+'):', OUT, flush=True)


def launch(disc, build=OUT, status=STATUS, settings=None):
    OUT = build
    STATUS = status
    report = json.loads((OUT/'manifest.json').read_text())
    if report['status'] != STATUS or sha((OUT/'1ST_READ.BIN').read_bytes()) != report['executable_sha256']:
        raise ValueError('Unknown or changed Zero build')
    combined.verify_files(OUT, [r for r in report['files'] if r['path'].startswith(f'disc{disc}/')])
    # Refuse concurrent emulator sessions instead of risking a VMU write clash.
    check = subprocess.run(['powershell', '-NoProfile', '-Command',
                            'if (Get-Process flycast -ErrorAction SilentlyContinue) { exit 1 }'],
                           creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    if check.returncode:
        raise ValueError('Please close existing Flycast windows first. No game was interrupted.')
    emulator = PLAY/'flycast.exe'
    if not emulator.is_file() or not (PLAY/'emu.cfg').is_file():
        raise ValueError('Existing old-save profile missing; no new profile created')
    cue = OUT/f'disc{disc}/Black-Matrix Advanced (Japan) (Disc {disc}).cue'
    arguments = [str(emulator)]
    if settings is not None:
        if any(',' in k+str(v) or '=' in k for k, v in settings.items()):
            raise ValueError('Invalid launch-only settings')
        arguments += ['-config', ','.join('config:'+k+'='+str(v) for k, v in settings.items())]
    arguments.append(str(cue))
    subprocess.Popen(arguments, cwd=PLAY, creationflags=subprocess.CREATE_NO_WINDOW)
    print('Zero-unlocked Disc', disc, 'opened using the existing original-save profile.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--launch', type=int, choices=(1, 2))
    args = parser.parse_args()
    if args.build:
        build()
    if args.launch:
        launch(args.launch)
