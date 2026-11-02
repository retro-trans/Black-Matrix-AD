"""Prepare the explicitly authorized private 0.9.0 patch-only release.

No game build, emulator operation, network write or original-image modification.
The optional source snapshot uses an isolated index, preserving the user's index.
GitHub publication is a separate reviewed operation, not an effect of this tool.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/hd_ui'), str(ROOT/'tools')]
import action_badges_english as badge

VERSION = '0.9.0'
BASE = ROOT/'build/retro-trans-v0.9.0'
TOOLCHAIN = BASE/'toolchain'
READY = BASE/'ready'
EXTRAS = BASE/'extras'
DOCS = ROOT/'docs/releases/v0.9.0'
STATE = BASE/'release-state-local.json'
REPO = 'retro-trans/Black-Matrix-AD'
BRANCH = 'refs/heads/codex/release-v0.9.0'
TARGETS = {1: '4eb243d79a6052e4b0a643b06c23e088acb00382ccf617538a5f087b5968c268',
           2: 'fc652c477c7a61227a332267cfe2d4153068953cf0f3710717702f759222130e'}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True)+'\n', encoding='utf-8')


def git(*args, env=None, data=None):
    return subprocess.run(['git', '-C', str(ROOT), *args], input=data,
                          capture_output=True, check=True, env=env).stdout.decode('utf-8').strip()


def inputs():
    manifest = json.loads((badge.OUT/'manifest.json').read_text())
    if manifest['build_version'] != '0.1.13' or manifest['status'] != badge.STATUS:
        raise ValueError('Wrong frozen cumulative input')
    result = []
    for item in manifest['files']:
        target = badge.OUT/item['path']
        original = ROOT/target.name
        if original.is_symlink() or target.is_symlink():
            raise ValueError('Symlink input is not supported')
        original_sha, target_sha = sha(original), sha(target)
        if target_sha != item['sha256'] or target.stat().st_size != item['bytes']:
            raise ValueError('Frozen target changed: '+target.name)
        disc = 1 if 'disc1/' in item['path'] else 2
        changed = original_sha != target_sha
        if changed != ('(Track 3).bin' in target.name):
            raise ValueError('Unexpected changed track/CUE: '+target.name)
        if changed and target_sha != TARGETS[disc]:
            raise ValueError('Unapproved target bytes')
        result.append(dict(disc=disc, name=target.name, changed=changed,
                           source_sha256=original_sha, source_bytes=original.stat().st_size,
                           target_sha256=target_sha, target_bytes=target.stat().st_size))
    if len(result) != 8:
        raise ValueError('Expected complete two-disc, three-track+CUE sets')
    return result


def sources():
    # Include the actually imported cumulative tool chain, not unrelated dirty
    # scripts/translations. No extracted archives, old fonts or game images.
    paths = {Path(m.__file__).resolve() for m in tuple(sys.modules.values())
             if getattr(m, '__file__', None) and Path(m.__file__).resolve().is_relative_to(ROOT/'tools')}
    paths.add(Path(__file__).resolve())
    paths.update(ROOT/p for p in (
        'README.md', 'docs/releases/v0.9.0/RELEASE.md',
        'docs/ACTION_BADGES_CHANGELOG.md', 'docs/RETRO_TRANS_RELEASES.md',
        'tests/test_action_badges_english.py', 'tests/test_join_footer_font.py',
        'tests/test_equip_fallback_font.py', 'tests/test_private_release.py', 'tests/sh4_runner.py'))
    paths.update(badge.ASSETS/p for p in ('generated-lettering.png', 'labels.en.json', 'prompt.txt'))
    secrets = re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-proj-[A-Za-z0-9_-]{30,}')
    rows = []
    for path in sorted(paths):
        if path.is_symlink() or path.suffix not in ('.py', '.md', '.json', '.txt', '.png'):
            raise ValueError('Unapproved source path: '+str(path))
        raw = path.read_bytes()
        if len(raw) > 2*1024*1024:
            raise ValueError('Unexpected large source asset')
        if path.suffix != '.png' and secrets.search(raw.decode('utf-8-sig')):
            raise ValueError('Possible credential in '+str(path.relative_to(ROOT)))
        rows.append(dict(path=path.relative_to(ROOT).as_posix(), bytes=len(raw), sha256=sha(path)))
    return rows


def plan():
    rows = inputs()
    badge.prepare()  # Reauthenticate the actual packed artwork and original guards.
    return dict(release_version=VERSION, internal_build_version='0.1.13',
                repository=REPO, visibility='private', prerelease=True,
                targets=rows, source_files=sources(),
                source_snapshot_scope='Selected imported cumulative patch tools and reviewed English asset; unrelated dirty edits excluded.',
                historical_inputs='Earlier local cumulative translated inputs remain identified by hashes, not shipped. Snapshot alone is not a complete historical rebuild recipe.',
                toolchain=dict(repository='retro-trans/retro-trans-tools', tag='v0.2.1',
                               archive_sha256=sha(BASE/'toolchain-v0.2.1.zip')),
                gameplay_verified=False, hardware_verified=False,
                no_game_images_bios_saves_ram_or_install_zips=True,
                public_catalog_changed=False)


def snapshot():
    if STATE.exists():
        raise ValueError('Preserve existing release state')
    current = plan()
    # These safe provenance records contain only relative paths/hashes, never
    # complete local manifests with personal profile or installation paths.
    provenance = DOCS/'PROVENANCE.json'
    if provenance.exists():
        raise ValueError('Preserve existing provenance')
    save(provenance, current)
    selected = [r['path'] for r in current['source_files']] + [provenance.relative_to(ROOT).as_posix()]
    parent = git('rev-parse', 'HEAD')
    if git('ls-remote', 'origin', 'refs/heads/main').split()[0] != parent:
        raise ValueError('Remote main diverged; review before release')
    if subprocess.run(['git', '-C', str(ROOT), 'show-ref', '--verify', '--quiet', BRANCH]).returncode == 0:
        raise ValueError('Preserve existing release branch')
    index = BASE/'source-snapshot.index'
    if index.exists():
        raise ValueError('Preserve existing isolated index')
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    git('read-tree', parent, env=env)
    git('add', '--', *selected, env=env)
    tree = git('write-tree', env=env)
    # Verify staged entries are the exact working bytes, without changing the
    # user's working tree, current branch or index.
    for path in selected:
        if git('rev-parse', tree+':'+path) != git('hash-object', '--path='+path, path):
            raise ValueError('Staged source mismatch '+path)
    diff = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', parent, tree).splitlines())
    if not diff <= set(selected):
        raise ValueError('Unexpected staged path')
    commit = git('commit-tree', tree, '-p', parent,
                 data=b'Prepare private Black/Matrix AD English v0.9.0 release sources\n')
    git('update-ref', BRANCH, commit, '0'*40)
    save(STATE, dict(source_commit=commit, parent=parent, branch=BRANCH, plan=current))
    config = dict(game_id='black-matrix-ad-dreamcast', game_name='Black/Matrix AD',
                  platform='Dreamcast', version=VERSION, source_commit=commit, patches=[])
    for disc in (1, 2):
        target = badge.b.track(badge.OUT, disc)
        config['patches'].append(dict(
            patch=f'Black-Matrix-AD-Disc{disc}-Native-v{VERSION}-from-original.xdelta',
            edition=f'jp-disc{disc}-track3-native', language='en', source_version='original',
            source_format='bin', target_format='bin', source=str(ROOT/target.name), target=str(target)))
    save(BASE/'release-local.json', config)
    print('Selected-source snapshot commit:', commit, flush=True)
    print('Snapshot excludes unrelated dirty files and all local game binaries.', flush=True)


def build():
    state = json.loads(STATE.read_text())
    if plan() != state['plan']:
        raise ValueError('Release inputs/source changed after snapshot')
    sys.path.insert(0, str(TOOLCHAIN))
    from retro_trans.release import build_release, validate_directory
    if Path(sys.modules['retro_trans.release'].__file__).resolve() != (TOOLCHAIN/'retro_trans/release.py').resolve():
        raise ValueError('Unpinned release builder')
    last = ['', 0.0]
    def progress(message, fraction):
        now = time.monotonic()
        if message != last[0] or now-last[1] > 20:
            print(message, '' if fraction is None else f'{fraction:.0%}', flush=True)
            last[:] = [message, now]
    manifest = build_release(BASE/'release-local.json', READY, progress=progress, cache=BASE/'engine-cache')
    validate_directory(READY)
    EXTRAS.mkdir()
    text = (DOCS/'RELEASE.md').read_text(encoding='utf-8')
    text += '\n### Exact source and target identities\n\n'
    for row in manifest['patches']:
        text += (f"{row['edition']}\nSource: {row['source_bytes']} bytes, SHA-256 {row['source_sha256']}\n"
                 f"Target: {row['target_bytes']} bytes, SHA-256 {row['target_sha256']}\n\n")
    text += '\n### Unchanged companion files\n\n'
    for row in state['plan']['targets']:
        if not row['changed']:
            text += f"{row['name']}\n{row['source_bytes']} bytes, SHA-256 {row['source_sha256']}\n\n"
    (EXTRAS/'README-v0.9.0.txt').write_text(text, encoding='utf-8')
    (EXTRAS/'CHANGELOG-v0.9.0.txt').write_text((DOCS/'RELEASE.md').read_text(encoding='utf-8'), encoding='utf-8')
    provenance = dict(state['plan'], source_commit=state['source_commit'],
                      roundtrips_verified=True, protocol_manifest_sha256=sha(READY/'BUILD-MANIFEST.json'))
    save(EXTRAS/'PROVENANCE-v0.9.0.json', provenance)
    (EXTRAS/'SHA256SUMS-extras-v0.9.0.txt').write_text(
        ''.join(sha(p)+'  '+p.name+'\n' for p in sorted(EXTRAS.iterdir())), encoding='utf-8')
    assets = [p for folder in (READY, EXTRAS) for p in folder.iterdir()]
    allowed = {r['patch'] for r in manifest['patches']} | {
        'BUILD-MANIFEST.json', 'VALIDATION.json', 'SHA256SUMS.txt', 'README-v0.9.0.txt',
        'CHANGELOG-v0.9.0.txt', 'PROVENANCE-v0.9.0.json', 'SHA256SUMS-extras-v0.9.0.txt'}
    if {p.name for p in assets} != allowed or any(p.is_symlink() or not p.is_file() for p in assets):
        raise ValueError('Release asset allowlist mismatch')
    save(BASE/'approved-upload-assets-local.json', [dict(path=str(p), name=p.name,
        bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(assets)])
    print('Verified patch-only release ready; nothing has been uploaded.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--build', action='store_true')
    args = parser.parse_args()
    if args.snapshot:
        snapshot()
    elif args.build:
        build()
    else:
        result = plan()
        print(json.dumps(dict(result, source_files_count=len(result['source_files']),
                              source_files_bytes=sum(r['bytes'] for r in result['source_files']),
                              source_files='See dry-run source inventory'), indent=2))
