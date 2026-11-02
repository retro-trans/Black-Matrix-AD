"""Build genuine per-filesystem Universal Dreamcast Patcher packages, local only.

Supersedes the earlier raw-track xdelta distribution by explicit user request.
Same frozen 0.1.13 translated files, release version 0.9.0. No emulator use.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'build/dcp-v0.9.0'
TOOLCHAIN = BASE/'toolchain'
SHARED = Path('E:/Projects/retro-trans-tools')
TARGET = ROOT/'output/patched-discs-action-badges-2026-11-02'
PRIOR = ROOT/'build/retro-trans-v0.9.0'
VERSION = '0.9.0'
UPSTREAM = '8b352f959bcc56ab39174c9e311b7ab7f0d522a2'
READY = BASE/'ready'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True)+'\n', encoding='utf-8')


def cue(disc, target=False):
    name = f'Black-Matrix Advanced (Japan) (Disc {disc}).cue'
    return TARGET/f'disc{disc}'/name if target else ROOT/name


def plan():
    manifest = json.loads((PRIOR/'ready/BUILD-MANIFEST.json').read_text())
    if manifest['version'] != VERSION or len(manifest['patches']) != 2:
        raise ValueError('Wrong frozen translation identities')
    for disc in (1, 2):
        row = next(r for r in manifest['patches'] if r['edition'] == f'jp-disc{disc}-track3-native')
        for target, key in ((False, 'source_sha256'), (True, 'target_sha256')):
            path = cue(disc, target).with_name(f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin')
            if sha(path) != row[key] or path.stat().st_size != row['target_bytes']:
                raise ValueError('Frozen disc bytes changed')
    return dict(release_version=VERSION, internal_build='0.1.13', format='DCP',
                translation_source_commit=manifest['source_commit'], upstream_commit=UPSTREAM,
                discs=[1, 2], output_formats_to_verify=['GDI', 'CUE/BIN'],
                game_files_must_match_frozen_build=True, audio_must_match_source=True,
                boot_invariant_must_match=True, raw_track_identity_not_promised=True,
                private=True, no_game_binaries_uploaded=True)


def freeze():
    if TOOLCHAIN.exists():
        raise ValueError('Preserve existing frozen toolchain')
    BASE.mkdir(exist_ok=True)
    info = plan()
    package = TOOLCHAIN/'retro_trans'
    package.mkdir(parents=True)
    for name in ('__init__.py', 'dcp.py', 'core.py', 'diagnostics.py'):
        shutil.copy2(SHARED/'retro_trans'/name, package/name)
    engine = Path('resources/native/dcp/win-x64')
    shutil.copytree(SHARED/'retro_trans'/engine, package/engine)
    # Preserve the bridge source locally for exact process-engine provenance.
    shutil.copy2(SHARED/'integrations/dcp/Program.cs', TOOLCHAIN/'Program.cs')
    rows = {p.relative_to(TOOLCHAIN).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p))
            for p in TOOLCHAIN.rglob('*') if p.is_file()}
    save(BASE/'toolchain-proof.json', dict(plan=info, files=rows))
    module = adapter()
    module.engine()  # Independently authenticates every bundled engine file.
    print('Frozen DCP adapter and authenticated UDP 2.1.8 engine on E:.', flush=True)


def adapter():
    sys.path.insert(0, str(TOOLCHAIN))
    from retro_trans import dcp
    if Path(dcp.__file__).resolve() != (TOOLCHAIN/'retro_trans/dcp.py').resolve() or dcp.UPSTREAM != UPSTREAM:
        raise ValueError('Wrong DCP adapter/engine')
    return dcp


_last = ['', 0.0]
def progress(message, fraction=None):
    now = time.monotonic()
    # Keep actual stage transitions visible, throttle noisy percentage messages.
    stem = message.split('...')[0]
    if message.startswith('Extracting '): stem = 'Extracting files'
    if message.startswith('Building patch for '): stem = 'Building file deltas'
    if stem != _last[0] or now-_last[1] > 20:
        print(message, flush=True)
        _last[:] = [stem, now]


def inspect(disc, target):
    dcp = adapter()
    side = 'target' if target else 'source'
    work = BASE/f'disc{disc}/{side}-inspection'
    record = work/'inspection.json'
    if record.exists():
        return json.loads(record.read_text())
    result = dcp.inspect_disc(cue(disc, target), work, progress=progress)
    save(record, result)
    return result


def build_disc(disc):
    dcp = adapter()
    work = BASE/f'disc{disc}'
    work.mkdir(exist_ok=True)
    before, after = inspect(disc, False), inspect(disc, True)
    original = {n:v for n,v in before['files'].items() if not n.lower().startswith('bootsector/')}
    target = {n:v for n,v in after['files'].items() if not n.lower().startswith('bootsector/')}
    if set(original) != set(target):
        raise ValueError('Unexpected added/removed game files')
    source_ip = (work/'source-inspection/files/bootsector/IP.BIN').read_bytes()
    target_ip = (work/'target-inspection/files/bootsector/IP.BIN').read_bytes()
    boot_delta = [i for i,(a,b) in enumerate(zip(source_ip,target_ip)) if a != b]
    if len(source_ip) != 32768 or len(target_ip) != 32768 or boot_delta != [0x3d] or source_ip[0x3d] != 0x30 or target_ip[0x3d] != 0x31:
        raise ValueError('Unexpected source-to-target boot change; expected existing VGA flag only')
    if before['audio_content'] != after['audio_content']:
        raise ValueError('Frozen translated audio differs')
    changed = {n for n in original if original[n] != target[n]}
    if not changed:
        raise ValueError('No translated files')
    package = READY/f'Black-Matrix-AD-Disc{disc}-English-v0.9.0.dcp'
    if package.exists():
        raise ValueError('Preserve final DCP')
    raw = work/'upstream-generated.dcp'
    if raw.exists():
        raise ValueError('Preserve prior builder output')
    result = dcp.run('build', dict(source=str(cue(disc)), target=str(cue(disc, True)),
                                 output=str(raw)), work/'build-engine', progress=progress)
    save(work/'build-result.json', result)
    metadata = dict(retro_trans_dcp=1, game_id='black-matrix-ad-dreamcast',
                    game_name='Black/Matrix AD', version=VERSION, disc=disc,
                    source_version='original', target_version=VERSION,
                    source_tree_sha256=dcp.tree_hash(before['files']),
                    target_tree_sha256=dcp.tree_hash(after['files']),
                    bootsector_invariant_sha256=after['bootsector_invariant_sha256'])
    with zipfile.ZipFile(raw) as source, zipfile.ZipFile(package, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        names = {r.filename.replace('\\', '/') for r in source.infolist() if not r.is_dir()}
        expected = {n+'.xdelta' for n in changed}
        if names != expected | {'bootsector/IP.BIN'}:
            raise ValueError('Unexpected DCP members, missing deltas or whole game files')
        # Standard DCP custom boot header retains the EXISTING VGA flag; it is
        # not a complete disc, archive or loose executable. Authenticate all
        # header bytes against the frozen target before inclusion.
        if source.read('bootsector/IP.BIN') != target_ip:
            raise ValueError('Upstream custom boot header differs')
        for name in sorted(expected | {'bootsector/IP.BIN'}):
            info = zipfile.ZipInfo(name, (1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            payload = source.read(name)
            if name != 'bootsector/IP.BIN' and not payload.startswith(b'\xd6\xc3\xc4'):
                raise ValueError('Not a genuine per-file delta')
            out.writestr(info, payload)
        out.comment = json.dumps(metadata, sort_keys=True, separators=(',', ':')).encode()
    checked = dcp.inspect_patch(package)
    if checked['metadata'] != metadata or checked['members'] != len(changed)+1:
        raise ValueError('DCP package read-back mismatch')
    save(work/'package-proof.json', dict(disc=disc, patch=package.name, bytes=package.stat().st_size,
        sha256=sha(package), changed_files=sorted(changed), metadata=metadata,
        original_file_count=len(original), verbatim_game_files=False,
        standard_custom_boot_header=True, boot_header_bytes=32768,
        boot_changes_from_original=[dict(offset=0x3d, source=0x30, target=0x31, meaning='existing VGA flag')],
        target_boot_header_sha256=hashlib.sha256(target_ip).hexdigest(),
        built_with_unmodified_upstream=True))
    print(f'Disc {disc} genuine DCP prepared; {len(changed)} file deltas.', flush=True)


def verify_disc(disc, format):
    dcp = adapter()
    package = READY/f'Black-Matrix-AD-Disc{disc}-English-v0.9.0.dcp'
    tag = 'gdi' if format == 'GDI' else 'cue-bin'
    destination = BASE/f'disc{disc}/verified-{tag}'
    proof = dcp.apply(cue(disc), package, destination, format=format, progress=progress)
    expected = inspect(disc, True)
    if proof['verified_game_tree_sha256'] != dcp.tree_hash(expected['files']) or not proof['release_metadata_verified'] or not proof['audio_tracks_preserved']:
        raise ValueError('Rebuilt DCP output differs from frozen game data')
    save(BASE/f'disc{disc}/verified-{tag}.json', proof)
    print(f'Disc {disc} {format}: full game tree, boot invariants and audio verified.', flush=True)


def build():
    plan()
    proof = json.loads((BASE/'toolchain-proof.json').read_text())
    for name, row in proof['files'].items():
        if sha(TOOLCHAIN/name) != row['sha256']:
            raise ValueError('Frozen tooling changed')
    READY.mkdir(exist_ok=True)  # Failed pre-package inspection may leave it empty.
    for disc in (1, 2):
        build_disc(disc)
        verify_disc(disc, 'GDI')
        verify_disc(disc, 'CUE/BIN')
    print('Both DCP packages verified in GDI and CUE/BIN. Publication not performed.', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freeze', action='store_true')
    p.add_argument('--build', action='store_true')
    a = p.parse_args()
    if a.freeze: freeze()
    elif a.build: build()
    else: print(json.dumps(plan(), indent=2))
