"""Freeze v0.9.1 DCPs from authenticated VGA candidates; no publication.

Only version metadata changes during promotion. Game-file delta payloads must
remain byte-identical to the tested packages. Whole game images stay local.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

VERSION = '0.9.1'
TEST_VERSION = '0.9.1-vga-test1'
EXPECTED = {
    ('full', 1): '416d415f442b15f9b90c4020ce97ad46d1377609652cdc1461289c5cb206d451',
    ('full', 2): '66f40f3094470fdc4d7a858c5a3dc7c6a58a041fc5f589fc00f686ebe79b26e7',
    ('upgrade', 1): '60f9c572e574ded91ce1d149f73b2ca67e1c50301623f45a93137c8b0539b3b2',
    ('upgrade', 2): 'd5e4d2c36853572d5540d4908404eb7f99c786b93d1a1be8b38ef808af10f920',
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, ensure_ascii=True)
        f.write('\n')


def name(kind, disc, version=VERSION):
    suffix = f'English-v{version}' if kind == 'full' else f'Upgrade-v0.9.0-to-v{version}'
    return f'Black-Matrix-AD-Disc{disc}-{suffix}.dcp'


def promote(source, target, expected, kind, disc):
    if sha(source) != expected:
        raise ValueError('Candidate package differs from authenticated test')
    with zipfile.ZipFile(source) as inp:
        if inp.testzip() is not None:
            raise ValueError('Candidate archive CRC failed')
        old = json.loads(inp.comment)
        if (old['version'] != TEST_VERSION or old['target_version'] != TEST_VERSION
                or old['disc'] != disc or old['game_id'] != 'black-matrix-ad-dreamcast'
                or old['source_version'] != ('original' if kind == 'full' else '0.9.0')):
            raise ValueError('Unexpected candidate identity')
        names = inp.namelist()
        if len(names) != len(set(names)) or set(names) != {i.filename for i in inp.infolist() if not i.is_dir()}:
            raise ValueError('Duplicate or directory member')
        if kind == 'upgrade' and set(names) != {'1ST_READ.BIN.xdelta', 'bootsector/IP.BIN'}:
            raise ValueError('Upgrade contains unexpected files')
        for n in names:
            if n.startswith('/') or '\\' in n or '..' in n.split('/'):
                raise ValueError('Unsafe member')
            if n == 'bootsector/IP.BIN':
                if len(inp.read(n)) != 32768:
                    raise ValueError('Unexpected boot header')
            elif not n.endswith('.xdelta') or not inp.read(n).startswith(bytes.fromhex('d6c3c4')):
                raise ValueError('Not a per-game-file DCP')
        metadata = copy.deepcopy(old)
        metadata.update(version=VERSION, target_version=VERSION)
        with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as out:
            for n in sorted(names):
                out.writestr(copy.copy(inp.getinfo(n)), inp.read(n))
            out.comment = json.dumps(metadata, sort_keys=True, separators=(',', ':')).encode()
        with zipfile.ZipFile(target) as out:
            if json.loads(out.comment) != metadata or out.testzip() is not None or set(out.namelist()) != set(names):
                raise ValueError('Promoted archive differs')
            if any(out.read(n) != inp.read(n) for n in names):
                raise ValueError('Promoted game payload differs')
    return dict(kind=kind, disc=disc, package=target.name, bytes=target.stat().st_size,
                sha256=sha(target), metadata=metadata, tested_candidate_sha256=expected,
                delta_payloads_unchanged=True)


def stage(root):
    out = root / 'work/output/0.9.1'
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for kind in ('full', 'upgrade'):
        folder = out / ('ready' if kind == 'full' else 'upgrades')
        folder.mkdir(exist_ok=True)
        source_folder = root / 'work/output' / TEST_VERSION / ('patches' if kind == 'full' else 'upgrade-from-v0.9.0')
        for disc in (1, 2):
            rows.append(promote(source_folder / name(kind, disc, TEST_VERSION),
                                folder / name(kind, disc), EXPECTED[kind, disc], kind, disc))
    if any(rows[d-1]['metadata']['target_tree_sha256'] != rows[d+1]['metadata']['target_tree_sha256'] for d in (1, 2)):
        raise ValueError('Full and upgrade targets differ')
    save(out / 'PACKAGE-PLAN.json', dict(version=VERSION, packages=rows))
    print(json.dumps(rows, indent=2), flush=True)


def verify(root, disc, kind, output_format):
    sys.path.insert(0, str(root / 'tools'))
    import prepare_dcp_release as frozen
    dcp = frozen.adapter()
    out = root / 'work/output/0.9.1'
    row = next(r for r in json.loads((out / 'PACKAGE-PLAN.json').read_text())['packages']
               if r['disc'] == disc and r['kind'] == kind)
    package = out / ('ready' if kind == 'full' else 'upgrades') / row['package']
    if sha(package) != row['sha256'] or dcp.inspect_patch(package)['metadata'] != row['metadata']:
        raise ValueError('Staged package changed')
    source = (root / f'Black-Matrix Advanced (Japan) (Disc {disc}).cue' if kind == 'full'
              else root / f'build/dcp-v0.9.0/disc{disc}/verified-gdi/disc.gdi')
    work = root / f'build/vga-release-0.9.1/disc{disc}-{kind}-{output_format.replace("/", "-").lower()}'
    work.mkdir(parents=True, exist_ok=True)
    proof = dcp.apply(source, package, work / 'verified', format=output_format, progress=frozen.progress)
    if (not proof['success'] or not proof['audio_tracks_preserved'] or not proof['release_metadata_verified']
            or proof['verified_game_tree_sha256'] != row['metadata']['target_tree_sha256']
            or proof['bootsector_invariant_sha256'] != row['metadata']['bootsector_invariant_sha256']
            or proof['files_added'] or proof['files_overwritten']
            or (kind == 'upgrade' and proof['files_patched'] != 1)):
        raise ValueError('Stable DCP round-trip failed')
    # Keep local absolute paths out of public validation records.
    proof.pop('output', None)
    proof.pop('extracted_source', None)
    save(work / 'verification.json', dict(disc=disc, kind=kind, package=row['package'],
         sha256=row['sha256'], source_format=source.suffix[1:].upper(), proof=proof))
    print(f'PASS: Disc {disc} {kind} -> {output_format}', flush=True)


def finish(root, source_commit, notes):
    if len(source_commit) != 40 or any(c not in '0123456789abcdef' for c in source_commit):
        raise ValueError('A reviewed public source commit is required')
    out = root / 'work/output/0.9.1'
    ready = out / 'ready'
    rows = json.loads((out / 'PACKAGE-PLAN.json').read_text())['packages']
    checks = []
    for row in rows:
        package = out / ('ready' if row['kind'] == 'full' else 'upgrades') / row['package']
        if sha(package) != row['sha256']:
            raise ValueError('Staged package changed')
        for fmt in ('gdi', 'cue-bin'):
            receipt = root / f'build/vga-release-0.9.1/disc{row["disc"]}-{row["kind"]}-{fmt}/verification.json'
            check = json.loads(receipt.read_text())
            check['proof'].pop('extracted_source', None)
            if check['sha256'] != row['sha256'] or check['proof']['verified_game_tree_sha256'] != row['metadata']['target_tree_sha256']:
                raise ValueError('Wrong stable package receipt')
            checks.append(check)
    original = json.loads((root / 'build/public-history-2026-11-02/sanitized-worktree/docs/releases/v0.9.0/DCP-AUTOMATIC.json').read_text())
    automatic = copy.deepcopy(original)
    automatic.update(version=VERSION, source_commit=source_commit, allow_prerelease=False)
    automatic['patches'] = []
    for row in rows[:2]:
        p = copy.deepcopy(next(p for p in original['patches'] if p['metadata']['disc'] == row['disc']))
        p.update(patch=row['package'], bytes=row['bytes'], sha256=row['sha256'], metadata=row['metadata'])
        automatic['patches'].append(p)
    save(ready / 'DCP-AUTOMATIC.json', automatic)
    manifest = dict(version=VERSION, format='DCP', source_commit=source_commit, packages=rows,
                    upstream_video_patch=dict(author='Rolly (SEGA-SKY)',
                        url='https://segasky.itch.io/black-matrix-ad-vga-patch-for-sega-dreamcast'),
                    project_lead='pow', game_images_distributed=False)
    save(ready / 'DCP-MANIFEST-v0.9.1.json', manifest)
    prior = json.loads((root / 'work/output/0.9.1-vga-test1/VALIDATION.json').read_text())
    prior['redream_visual_check'].pop('selected_library_directory', None)
    prior.pop('public_release_changed', None)
    validation = dict(version=VERSION, status='passed', checks=checks,
        candidate_video_checks=prior, game_payloads_identical_to_tested_candidate=True,
        player_report=dict(date='2026-11-04', reporter='pow', result='VGA and redream work',
                           hardware_or_adapter_details_provided=False),
        full_playthrough_verified=False, pal_hardware_verified=False)
    save(ready / 'DCP-VALIDATION-v0.9.1.json', validation)
    text = Path(notes).read_text(encoding='utf-8')
    if 'v0.9.1' not in text or 'Rolly' not in text or 'vga-test1' in text:
        raise ValueError('Unexpected player notes')
    with (ready / 'README-DCP-v0.9.1.txt').open('x', encoding='utf-8', newline='\n') as f:
        f.write(text)
    upgrades = [out / 'upgrades' / r['package'] for r in rows if r['kind'] == 'upgrade']
    bundle = ready / 'Black-Matrix-AD-v0.9.0-to-v0.9.1-Upgrade-DCP.zip'
    with zipfile.ZipFile(bundle, 'x', zipfile.ZIP_DEFLATED) as z:
        for p in upgrades:
            z.write(p, p.name)
        z.writestr('README.txt', text)
        z.writestr('SHA256SUMS.txt', ''.join(sha(p) + '  ' + p.name + '\n' for p in upgrades))
    with zipfile.ZipFile(bundle) as z:
        if set(z.namelist()) != {p.name for p in upgrades} | {'README.txt', 'SHA256SUMS.txt'} or z.testzip() is not None:
            raise ValueError('Upgrade ZIP allowlist failed')
        if any(hashlib.sha256(z.read(p.name)).hexdigest() != sha(p) for p in upgrades):
            raise ValueError('Bundled upgrade differs')
    paths = sorted(ready.iterdir())
    allowed = {name('full', d) for d in (1, 2)} | {
        'DCP-AUTOMATIC.json', 'DCP-MANIFEST-v0.9.1.json', 'DCP-VALIDATION-v0.9.1.json',
        'README-DCP-v0.9.1.txt', bundle.name}
    if {p.name for p in paths} != allowed:
        raise ValueError('Unexpected publication file')
    with (ready / 'SHA256SUMS-v0.9.1.txt').open('x', encoding='utf-8', newline='\n') as f:
        f.write(''.join(sha(p) + '  ' + p.name + '\n' for p in paths))
    print(json.dumps(dict(version=VERSION, checks=len(checks), assets=[p.name for p in ready.iterdir()]), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--stage', action='store_true')
    p.add_argument('--disc', type=int, choices=(1, 2))
    p.add_argument('--kind', choices=('full', 'upgrade'))
    p.add_argument('--format', choices=('GDI', 'CUE/BIN'))
    p.add_argument('--finish', action='store_true')
    p.add_argument('--source-commit')
    p.add_argument('--notes', type=Path)
    a = p.parse_args()
    if a.stage:
        stage(a.workspace)
    if a.disc:
        if not a.kind or not a.format:
            p.error('--disc requires --kind and --format')
        verify(a.workspace, a.disc, a.kind, a.format)
    if a.finish:
        if not a.source_commit or not a.notes:
            p.error('--finish requires --source-commit and --notes')
        finish(a.workspace, a.source_commit, a.notes)
