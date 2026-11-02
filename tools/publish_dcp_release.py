"""Stage/publish the explicitly requested DCP replacement for private v0.9.0.

New DCP assets are uploaded and read-back verified before old assets are removed.
The original translation tag, patch bytes and all complete local images survive.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import prepare_dcp_release as prep

REPO = 'retro-trans/Black-Matrix-AD'
TAG = 'v0.9.0'
BASE = prep.BASE
BRANCH = 'refs/heads/codex/dcp-v0.9.0'
STATE = BASE/'packaging-state-local.json'
UPLOADS = BASE/'approved-dcp-assets-local.json'
PUBLICATION = BASE/'publication-local.json'
SELECTED = ('README.md', 'docs/RETRO_TRANS_RELEASES.md',
    'docs/releases/v0.9.0/RELEASE.md', 'docs/releases/v0.9.0/DCP.md',
    'tools/prepare_dcp_release.py', 'tools/publish_dcp_release.py', 'tests/test_dcp_release.py')


def run(*args, data=None, env=None):
    return subprocess.run(list(args), input=data, env=env, check=True,
                          capture_output=True).stdout.decode('utf-8').strip()


def git(*args, **kwargs):
    return run('git', '-C', str(ROOT), *args, **kwargs)


def api(path, method='GET', payload=None):
    command = ['gh', 'api', path, '--method', method]
    data = None
    if payload is not None:
        command += ['--input', '-']
        data = json.dumps(payload).encode()
    value = run(*command, data=data)
    return json.loads(value) if value else None


def gh_identity():
    if api('user')['login'] != 'binhlt0402' or not api(f'repos/{REPO}')['private']:
        raise ValueError('Wrong account or repository visibility')


def ready_records():
    rows = []
    for disc in (1, 2):
        work = BASE/f'disc{disc}'
        package = json.loads((work/'package-proof.json').read_text())
        path = prep.READY/package['patch']
        if prep.sha(path) != package['sha256'] or path.stat().st_size != package['bytes']:
            raise ValueError('DCP bytes changed')
        routes = []
        for name in ('gdi', 'cue-bin'):
            proof = json.loads((work/f'verified-{name}.json').read_text())
            if not proof['release_metadata_verified'] or not proof['audio_tracks_preserved'] or proof['verified_game_tree_sha256'] != package['metadata']['target_tree_sha256'] or proof['bootsector_invariant_sha256'] != package['metadata']['bootsector_invariant_sha256']:
                raise ValueError('Missing complete DCP route verification')
            routes.append({k:proof[k] for k in ('format', 'verified_game_tree_sha256',
                'bootsector_invariant_sha256', 'audio_tracks_preserved', 'audio_verification',
                'audio_tracks', 'audio_content', 'release_metadata_verified', 'output_files')})
        source = json.loads((work/'source-inspection/inspection.json').read_text())
        target = json.loads((work/'target-inspection/inspection.json').read_text())
        rows.append(dict(package=package, routes=routes,
            source_files={k:v for k,v in source['files'].items() if not k.startswith('bootsector/')},
            target_files={k:v for k,v in target['files'].items() if not k.startswith('bootsector/')}))
    return rows


def stage():
    if STATE.exists() or UPLOADS.exists():
        raise ValueError('Preserve prior DCP publication preparation')
    rows = ready_records()
    gh_identity()
    # Fetch objects only; do not checkout/reset or touch user's dirty index.
    git('fetch', 'origin', 'main')
    parent = git('ls-remote', 'origin', 'refs/heads/main').split()[0]
    if git('rev-parse', 'origin/main') != parent:
        raise ValueError('Remote main changed during fetch')
    index = BASE/'packaging.index'
    if index.exists():
        raise ValueError('Preserve isolated packaging index')
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    git('read-tree', parent, env=env)
    git('add', '--', *SELECTED, env=env)
    tree = git('write-tree', env=env)
    diff = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', parent, tree).splitlines())
    if not diff <= set(SELECTED):
        raise ValueError('Unrelated source staged')
    for path in SELECTED:
        if git('rev-parse', tree+':'+path) != git('hash-object', '--path='+path, path):
            raise ValueError('Staged file differs')
    commit = git('commit-tree', tree, '-p', parent,
                 data=b'Use verified Dreamcast DCP packages for private v0.9.0\n')
    git('update-ref', BRANCH, commit, '0'*40)
    original = json.loads((prep.PRIOR/'ready/BUILD-MANIFEST.json').read_text())
    manifest = dict(schema='black-matrix-ad-dcp-release-v1', format='DCP', version='0.9.0',
        game_id='black-matrix-ad-dreamcast', game_name='Black/Matrix AD', platform='Dreamcast',
        language='en', private=True, translation_source_commit=original['source_commit'],
        packaging_source_commit=commit, upstream_commit=prep.UPSTREAM,
        raw_track_identity_not_promised=True, translated_game_content_changed=False,
        boot_header_preserves_existing_vga_flag=True, patches=[])
    for row in rows:
        p = row['package']
        manifest['patches'].append(dict(patch=p['patch'], bytes=p['bytes'], sha256=p['sha256'],
            disc=p['disc'], metadata=p['metadata'], changed_files=p['changed_files'],
            source_files=row['source_files'], target_files=row['target_files']))
    prep.save(prep.READY/'DCP-MANIFEST-v0.9.0.json', manifest)
    prep.save(prep.READY/'DCP-VALIDATION-v0.9.0.json', dict(version='0.9.0',
        manifest_sha256=prep.sha(prep.READY/'DCP-MANIFEST-v0.9.0.json'),
        raw_track_identity_not_promised=True, gameplay_verified=False, hardware_verified=False,
        discs=[dict(disc=r['package']['disc'], routes=r['routes']) for r in rows]))
    notes = (ROOT/'docs/releases/v0.9.0/RELEASE.md').read_text(encoding='utf-8')
    (prep.READY/'README-DCP-v0.9.0.txt').write_text(notes, encoding='utf-8')
    proof = json.loads((BASE/'toolchain-proof.json').read_text())
    prep.save(prep.READY/'PROVENANCE-DCP-v0.9.0.json', dict(version='0.9.0',
        translation_source_commit=original['source_commit'], packaging_source_commit=commit,
        upstream_commit=prep.UPSTREAM, internal_build='0.1.13',
        selected_sources={p:prep.sha(ROOT/p) for p in SELECTED},
        adapter_and_engine_fingerprints=proof['files'],
        source_track_identities=[{k:r[k] for k in ('edition','source_sha256','source_bytes','target_sha256','target_bytes')} for r in original['patches']],
        original_files_preserved=True, game_images_and_engine_binaries_uploaded=False))
    sums = prep.READY/'SHA256SUMS-DCP-v0.9.0.txt'
    sums.write_text(''.join(prep.sha(p)+'  '+p.name+'\n' for p in sorted(prep.READY.iterdir())), encoding='utf-8')
    files = [dict(path=str(p), name=p.name, bytes=p.stat().st_size, sha256=prep.sha(p))
             for p in sorted(prep.READY.iterdir())]
    expected = {f'Black-Matrix-AD-Disc{d}-English-v0.9.0.dcp' for d in (1,2)} | {
        'DCP-MANIFEST-v0.9.0.json', 'DCP-VALIDATION-v0.9.0.json', 'README-DCP-v0.9.0.txt',
        'PROVENANCE-DCP-v0.9.0.json', 'SHA256SUMS-DCP-v0.9.0.txt'}
    if {r['name'] for r in files} != expected:
        raise ValueError('DCP asset allowlist differs')
    prep.save(UPLOADS, files)
    prep.save(STATE, dict(parent=parent, packaging_commit=commit,
        translation_commit=original['source_commit'], selected_sources={p:prep.sha(ROOT/p) for p in SELECTED}))
    print('Verified seven DCP/document assets staged; packaging commit', commit, flush=True)


def publish():
    if PUBLICATION.exists():
        raise ValueError('DCP publication already completed')
    gh_identity()
    state = json.loads(STATE.read_text())
    assets = json.loads(UPLOADS.read_text())
    ready_records()
    for p,digest in state['selected_sources'].items():
        if prep.sha(ROOT/p) != digest:
            raise ValueError('Packaging source changed')
    for row in assets:
        path = Path(row['path'])
        if path.resolve().parent != prep.READY.resolve() or path.suffix not in ('.dcp','.json','.txt') or path.name != row['name'] or prep.sha(path) != row['sha256'] or path.stat().st_size != row['bytes']:
            raise ValueError('Upload bytes/path differ')
    before = api(f'repos/{REPO}/releases/tags/{TAG}')
    old = json.loads((prep.PRIOR/'github-publication-local.json').read_text())
    expected_old = {r['name']:r for r in old['assets']}
    live_old = {r['name']:r for r in before['assets']}
    if set(live_old) != set(expected_old):
        raise ValueError('Release assets changed; review before replacing format')
    for name, row in expected_old.items():
        actual = live_old[name]
        backup = prep.PRIOR/'uploaded-verification'/name
        if actual['size'] != row['bytes'] or actual.get('digest') != 'sha256:'+row['sha256'] or prep.sha(backup) != row['sha256']:
            raise ValueError('Old asset changed or exact recovery backup missing')
    prep.save(BASE/'release-before-local.json', before)
    commit = state['packaging_commit']
    if git('ls-remote','origin','refs/heads/main').split()[0] != state['parent']:
        raise ValueError('Remote main changed')
    if api(f'repos/{REPO}/git/ref/tags/{TAG}')['object']['sha'] != state['translation_commit']:
        raise ValueError('Immutable translation tag changed')
    print('Pushing DCP packaging sources to private staging branch.', flush=True)
    git('-c','credential.helper=','-c','credential.helper=!gh auth git-credential',
        'push','origin',commit+':'+BRANCH)
    print('Uploading two DCP packages and five documentation/verification assets.', flush=True)
    run('gh','release','upload',TAG,*[r['path'] for r in assets],'--repo',REPO)
    updated = api(f'repos/{REPO}/releases/tags/{TAG}')
    live = {r['name']:r for r in updated['assets']}
    if set(live) != set(expected_old) | {r['name'] for r in assets}:
        raise ValueError('Unexpected uploaded inventory')
    downloads = BASE/'uploaded-verification'
    downloads.mkdir()
    for row in assets:
        remote = live[row['name']]
        if remote['size'] != row['bytes'] or remote.get('digest') != 'sha256:'+row['sha256']:
            raise ValueError('DCP upload metadata differs')
        path = downloads/row['name']
        with path.open('xb') as stream:
            subprocess.run(['gh','api',f'repos/{REPO}/releases/assets/{remote["id"]}',
                '-H','Accept: application/octet-stream'],stdout=stream,stderr=subprocess.PIPE,check=True)
        if path.stat().st_size != row['bytes'] or prep.sha(path) != row['sha256']:
            raise ValueError('DCP uploaded bytes differ')
        print('Uploaded bytes verified:',row['name'],flush=True)
    # Only after ALL new bytes verify do we switch docs and withdraw the exact
    # old nine assets. Recovery copies stay in the earlier local directory.
    gh_identity()
    if git('ls-remote','origin','refs/heads/main').split()[0] != state['parent']:
        raise ValueError('Remote main changed during upload')
    git('-c','credential.helper=','-c','credential.helper=!gh auth git-credential',
        'push','origin',commit+':refs/heads/main')
    body = (ROOT/'docs/releases/v0.9.0/RELEASE.md').read_text(encoding='utf-8')
    api(f'repos/{REPO}/releases/{before["id"]}', 'PATCH', dict(body=body))
    for name,row in live_old.items():
        api(f'repos/{REPO}/releases/assets/{row["id"]}', 'DELETE')
        print('Withdrew superseded asset (local exact backup retained):',name,flush=True)
    final = api(f'repos/{REPO}/releases/tags/{TAG}')
    if {r['name'] for r in final['assets']} != {r['name'] for r in assets} or final['body'] != body:
        raise ValueError('Final DCP release differs')
    if api(f'repos/{REPO}/git/ref/tags/{TAG}')['object']['sha'] != state['translation_commit']:
        raise ValueError('Translation tag changed unexpectedly')
    gh_identity()
    prep.save(PUBLICATION, dict(version='0.9.0', format='DCP', private=True,
        release_url=final['html_url'], packaging_commit=commit,
        translation_commit=state['translation_commit'], existing_tag_unchanged=True,
        all_uploaded_bytes_read_back_verified=True,
        removed_superseded_assets=list(expected_old),
        recovery_directory='build/retro-trans-v0.9.0/uploaded-verification',
        assets=[{k:r[k] for k in ('name','bytes','sha256')} for r in assets]))
    print('Private v0.9.0 now distributes DCP only:',final['html_url'],flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', action='store_true')
    p.add_argument('--publish', action='store_true')
    a = p.parse_args()
    if a.stage: stage()
    elif a.publish: publish()
    else:
        rows = ready_records()
        print(json.dumps([dict(disc=r['package']['disc'], package=r['package']['patch'],
            bytes=r['package']['bytes'], sha256=r['package']['sha256'],
            verified_formats=[p['format'] for p in r['routes']]) for r in rows],indent=2))
