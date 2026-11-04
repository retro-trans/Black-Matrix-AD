"""Local VGA integration experiment; never publishes or edits issued discs.

Rolly's downloaded executable is an input, not a replacement for the English
executable. Only authenticated original-to-VGA byte changes are transplanted.
"""
import argparse
import hashlib
import http.cookiejar
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools/hd_ui'), str(ROOT / 'tools')]
import inject
import mode1_sector
import skies_vga_compat as previous

VERSION = '0.9.1-vga-test1'
OUT = ROOT / 'work/output' / VERSION
PACKAGE = ROOT / 'incoming/rolly-dc-black-matrix-ad-vga-patch-v1.0.zip'
PACKAGE_SHA = '0eaa3059bc5f57640e93c3cb1a8c32566ebc62514dce9ee1de92b8d5cf008a33'
ORIGINAL_SHA = '45d782657d5c73cd2d052fc1c777bf85cd62f9b5cf494b9a6114e365a572b529'
VGA_SHA = '5952f8a2a3a881c6b34e2f0eb1bc5ff01239ddb87371048a5f25f5ec3ad2d920'
URL = 'https://segasky.itch.io/black-matrix-ad-vga-patch-for-sega-dreamcast'
ISSUED = ROOT / 'output/patched-discs-action-badges-2026-11-02'
MANIFEST = ROOT / 'build/dcp-v0.9.0/ready/DCP-MANIFEST-v0.9.0.json'
ISSUED_TRACK_SHA = {
    1: '4eb243d79a6052e4b0a643b06c23e088acb00382ccf617538a5f087b5968c268',
    2: 'fc652c477c7a61227a332267cfe2d4153068953cf0f3710717702f759222130e',
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch():
    """Use itch.io's free-download flow; no account, payment or upload."""
    if PACKAGE.exists():
        if digest(PACKAGE) != PACKAGE_SHA:
            raise ValueError('Existing input differs; preserve it for inspection')
        return
    client = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(url):
        with client.open(url, timeout=30) as response:
            return response.read(3_000_001)

    def post(url, page, referer):
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        request = urllib.request.Request(url,
            data=urllib.parse.urlencode({'csrf_token': token}).encode(),
            headers={'Referer': referer, 'X-Requested-With': 'XMLHttpRequest'})
        with client.open(request, timeout=30) as response:
            return json.load(response)

    page = get(URL + '/purchase').decode()
    location = post(URL + '/download_url', page, URL + '/purchase')['url']
    page = get(location).decode()
    upload = re.search(r'data-upload_id="(\d+)"', page).group(1)
    location = post(URL + '/file/' + upload, page, location)['url']
    data = get(location)
    if hashlib.sha256(data).hexdigest() != PACKAGE_SHA:
        raise ValueError('Upstream package identity changed; do not trust new bytes')
    PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    with PACKAGE.open('xb') as f:
        f.write(data)


def inputs():
    if digest(PACKAGE) != PACKAGE_SHA:
        raise ValueError('Unknown third-party archive')
    original = (ROOT / 'extracted/1ST_READ.BIN').read_bytes()
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA:
        raise ValueError('Unknown original executable')
    with zipfile.ZipFile(PACKAGE) as archive:
        candidates = []
        for disc in (1, 2):
            names = [n for n in archive.namelist()
                     if n.endswith(f'black-matrix-ad-gdrom{disc}/1ST_READ.BIN')]
            if len(names) != 1 or archive.getinfo(names[0]).file_size != len(original):
                raise ValueError('Unexpected downloaded executable')
            candidate = archive.read(names[0])
            if hashlib.sha256(candidate).hexdigest() != VGA_SHA:
                raise ValueError('Unknown VGA executable')
            candidates.append(candidate)
    if candidates[0] != candidates[1]:
        raise ValueError('Disc-specific integration required')
    return original, candidates[0]


def patch(exe, original, candidate, keep_startup=False):
    if not (len(exe) == len(original) == len(candidate) == 947300):
        raise ValueError('Unexpected executable size')
    if (hashlib.sha256(original).hexdigest() != ORIGINAL_SHA or
            hashlib.sha256(candidate).hexdigest() != VGA_SHA):
        raise ValueError('Unauthenticated original or VGA executable')
    changes = [i for i, (a, b) in enumerate(zip(original, candidate)) if a != b]
    if len(changes) != 510:
        raise ValueError('Unknown video correction delta')
    if any(exe[i] != original[i] for i in changes):
        raise ValueError('Video patch overlaps translated/gameplay changes')
    if struct.unpack_from('<I', exe, previous.CALL_POINTER)[0] != previous.HELPER:
        raise ValueError('Unknown issued startup helper')
    start = previous.HELPER - 0x8c010000
    if exe[start:start + len(previous.cable_helper())] != previous.cable_helper():
        raise ValueError('Issued cable helper differs')
    result = bytearray(exe)
    for i in changes:
        result[i] = candidate[i]
    # Let Rolly's low-level cable handling receive the original mode. Keeping
    # the earlier mode-0x11 override is a separate diagnostic control only.
    if not keep_startup:
        struct.pack_into('<I', result, previous.CALL_POINTER, previous.WRAPPER)
    allowed = set(changes) | set(range(previous.CALL_POINTER, previous.CALL_POINTER + 4))
    delta = [i for i, (a, b) in enumerate(zip(exe, result)) if a != b]
    if not set(delta) <= allowed:
        raise ValueError('Unrelated executable edit')
    return bytes(result), delta


def inspect():
    from sh4dis import disassemble
    original, candidate = inputs()
    for offset, length in ((0xa3a58, 16), (0xadd60, 32), (0xc9860, 0x154)):
        print('\nVGA patch', hex(offset))
        print('\n'.join(disassemble(candidate, offset, length)))
    for disc in (1, 2):
        exe = (ROOT / f'build/dcp-v0.9.0/disc{disc}/target-inspection/files/1ST_READ.BIN').read_bytes()
        result, delta = patch(exe, original, candidate)
        print(json.dumps(dict(disc=disc, changed_bytes=len(delta),
            result_sha256=hashlib.sha256(result).hexdigest())))


def build(discs, keep_startup=False):
    original, candidate = inputs()
    issued = json.loads(MANIFEST.read_text())
    variant = 'keep-startup-control' if keep_startup else 'integrated'
    destination = OUT / variant
    destination.mkdir(parents=True, exist_ok=True)
    for disc in discs:
        folder = destination / f'disc{disc}'
        if folder.exists():
            raise ValueError('Preserve previous output: ' + str(folder))
        source = ISSUED / f'disc{disc}'
        track = source / f'Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'
        with track.open('rb') as f:
            directory = list(inject.iso_files(f))
            lba, size = inject.find(f, '1ST_READ.BIN')
            exe = inject._extent(f, lba, size)
            boot = inject._extent(f, 45000, 32768)
        expected = next(p for p in issued['patches'] if p['disc'] == disc)
        if hashlib.sha256(exe).hexdigest() != expected['target_files']['1ST_READ.BIN']['sha256']:
            raise ValueError('Not the issued translation executable')
        before_sha = digest(track)
        if before_sha != ISSUED_TRACK_SHA[disc]:
            raise ValueError('Not the frozen issued track')
        after, delta = patch(exe, original, candidate, keep_startup)
        by_sector = {}
        for off in delta:
            sector = lba - 45000 + off // 2048
            by_sector.setdefault(sector, []).append((16 + off % 2048, after[off]))
        folder.mkdir()
        target = folder / track.name
        print(f'Building {variant} Disc {disc}: {len(delta)} EXE bytes, '
              f'{len(by_sector)} raw sectors.', flush=True)
        with track.open('rb') as inp, target.open('xb') as out:
            sector = 0
            while raw := inp.read(2352 * 4096):
                block = bytearray(raw)
                for n in sorted(by_sector):
                    if sector <= n < sector + len(raw) // 2352:
                        pos = (n - sector) * 2352
                        data = bytearray(block[pos:pos + 2352])
                        for offset, value in by_sector[n]:
                            data[offset] = value
                        data = mode1_sector.regenerate(data)
                        if mode1_sector.regenerate(data) != data:
                            raise ValueError('EDC/ECC verification failed')
                        block[pos:pos + 2352] = data
                out.write(block)
                sector += len(raw) // 2352
        # Read back every game file. Unmodified sectors are copied verbatim;
        # modified sectors have independent parity/readback checks above.
        with track.open('rb') as inp, target.open('rb') as out:
            if list(inject.iso_files(out)) != directory or inject._extent(out, 45000, 32768) != boot:
                raise ValueError('Directory or boot header changed')
            files = []
            for name, file_lba, length in directory:
                old = inject._extent(inp, file_lba, length)
                actual = inject._extent(out, file_lba, length)
                if actual != (after if name == '1ST_READ.BIN' else old):
                    raise ValueError('Unexpected payload change: ' + name)
                files.append(dict(name=name, bytes=length,
                    sha256=hashlib.sha256(actual).hexdigest()))
            for sector in by_sector:
                out.seek(sector * 2352)
                data = out.read(2352)
                if mode1_sector.regenerate(data) != data:
                    raise ValueError('On-disk sector parity differs')
        companions = []
        for p in source.iterdir():
            if p.is_file() and p != track:
                shutil.copy2(p, folder / p.name)
                if digest(p) != digest(folder / p.name):
                    raise ValueError('Companion differs')
                companions.append(dict(name=p.name, sha256=digest(p)))
        if digest(track) != before_sha:
            raise ValueError('Issued source changed')
        report = dict(version=VERSION, variant=variant, disc=disc,
            status='payload-and-modified-sector-verified-runtime-pending',
            upstream_author='Rolly (SEGA-SKY)', upstream_url=URL,
            upstream_zip_sha256=PACKAGE_SHA, original_exe_sha256=ORIGINAL_SHA,
            upstream_exe_sha256=VGA_SHA, source_track_sha256=before_sha,
            target_track_sha256=digest(target), executable_sha256=hashlib.sha256(after).hexdigest(),
            changed_executable_bytes=len(delta), changed_raw_sectors=sorted(by_sector),
            original_startup_restored=not keep_startup, issued_source_unchanged=True,
            all_other_game_files_and_boot_exact=True, files=files, companions=companions,
            saves_untouched=True, hardware_verified=False, redream_verified=False,
            published=False, local_complete_images_only=True)
        with (folder / 'verification.json').open('x', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f'Disc {disc} verified: {target}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--disc', type=int, choices=(1, 2), action='append')
    parser.add_argument('--keep-startup-control', action='store_true')
    args = parser.parse_args()
    if args.fetch:
        fetch()
    if args.inspect:
        inspect()
    if args.build:
        build(args.disc or [1, 2], args.keep_startup_control)
