"""Translate the shared red insert-Disc-1 bitmap in new private disc copies."""
import argparse
import hashlib
import json
import shutil
import struct

from PIL import Image
import numpy as np
import domina_first as domina
import pvr_atlas
import mode1_sector

ROOT = domina.ROOT
SOURCE = domina.OUT
OUT = ROOT/'output/patched-discs-disc-swap-english-2026-11-02'
REVIEW = ROOT/'build/disc-swap-english-inspection-2026-11-02'
ASSET = ROOT/'assets/ui/disc-swap/insert-disc-1-english-v1.png'
STATUS = 'private-disc-swap-english-runtime-pending'
READER = domina.zero.READER
OFFSETS = {1: 0x423840, 2: 0x3d7040}
LEAF_SHA = 'a5adece256601b702d763924fa07d0d6185bfe7e2ee68f6b5b7b82aaacf66530'
EXE_SHA = 'd57123443313dbf5bcc4138d86d3a070c2addbf9185b0152aebf810991af8fe1'
TEXTS = ('Please insert Disc 1.', 'Press OPEN to open the disc lid,', 'then replace the disc.')
ASSET_SHA = '265c674845d45b056265e9bcec662c5f7099321ee510362142fbdb1381603b75'
SYSTEM_HASHES = {1: '7ad637acac86f8aa80cafbf3fc3f970a37ad07a868f7cd6fbf3d45dbeb16c382',
                 2: '7ff3bb5636997448f09ac1d0824b32b20a4cd3d7e5a044228d4318cff4ad04ca'}
TRACK_HASHES = {1: 'a1c2411b2b00a3dcd05413271459a180f8af94ef71455a43850a419b10aada9b',
                2: '2b744e3068e3d54191dee2798d5d8d1866fbec535b37a59f60761bda48fb7ccf'}
RENDERER = ROOT/'build/skies-rayblade-font-v3/renderer-settings.json'
RENDERER_SHA = '8c9fd375ddce4e62266b200081069b1e40c80fc89113f33b0c8c8633b61af59a'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def track(folder, disc):
    return folder/f'disc{disc}/Black-Matrix Advanced (Japan) (Disc {disc}) (Track 3).bin'


def source_system(disc):
    return READER.read_file(track(SOURCE, disc), 'SYSTEM.DAT')


def extract():
    REVIEW.mkdir(exist_ok=False)
    images = []
    for disc in (1, 2):
        system, _ = source_system(disc)
        o = OFFSETS[disc]
        cols, rows, ds, pages = pvr_atlas.scl_layout(system, o)
        end = pages[-1]+16+131072
        if (cols, rows, len(pages)) != (40, 15, 3) or sha(system[o:end]) != LEAF_SHA:
            raise ValueError('Unknown red disc-swap image')
        image = pvr_atlas.decode_scl(system, o)
        images.append(image.tobytes())
        image.resize((640, 480), Image.Resampling.NEAREST).save(REVIEW/f'original-disc{disc}.png')
        print('Disc', disc, hex(o), hex(end), LEAF_SHA, flush=True)
    if images[0] != images[1]:
        raise ValueError('Disc swap images differ')


def native_image():
    if sha(ASSET.read_bytes()) != ASSET_SHA:
        raise ValueError('Reviewed English asset changed')
    with Image.open(ASSET) as image:
        if image.width*3 != image.height*4:
            raise ValueError('Expected full 4:3 artwork without cropping')
        return image.convert('RGB').resize((640, 240), Image.Resampling.LANCZOS)


def quantized(image):
    a = np.asarray(image, dtype=np.uint32)
    w = ((a[:, :, 0]*31+127)//255)<<11 | ((a[:, :, 1]*63+127)//255)<<5 | ((a[:, :, 2]*31+127)//255)
    return np.stack(((w>>11&31)*255//31, (w>>5&63)*255//63, (w&31)*255//31), axis=-1).astype('u1')


def patch(system, disc):
    if disc not in OFFSETS or sha(system) != SYSTEM_HASHES[disc]:
        raise ValueError('Unknown per-disc SYSTEM source')
    o = OFFSETS[disc]
    cols, rows, _, pages = pvr_atlas.scl_layout(system, o)
    end = pages[-1]+16+131072
    if (cols, rows, len(pages)) != (40, 15, 3) or sha(system[o:end]) != LEAF_SHA:
        raise ValueError('Unknown native disc-swap allocation')
    # Assert that no other SCL refers to any of these three texture payloads.
    users = []
    pos = 0
    while (pos := system.find(b'SCL ', pos)) >= 0:
        try:
            if set(pages).intersection(pvr_atlas.scl_layout(system, pos)[3]):
                users.append(pos)
        except (ValueError, IndexError, struct.error):
            pass
        pos += 4
    if users != [o]:
        raise ValueError('Native atlases have other consumers')
    image = native_image()
    after = bytearray(system)
    tiles = pvr_atlas.encode_scl(after, o, image)
    allowed = np.zeros(len(system), dtype=bool)
    allowed[o+32:o+32+600*4] = True
    for page in pages:
        allowed[page+16:page+16+131072] = True
    delta = np.flatnonzero(np.frombuffer(system, 'u1') != np.frombuffer(after, 'u1')).tolist()
    if not delta or np.any(~allowed[delta]):
        raise ValueError('Writes outside native map/pixel allocation')
    decoded = pvr_atlas.decode_scl(after, o)
    if decoded.tobytes() != quantized(image).tobytes():
        raise ValueError('Native English artwork readback differs')
    report = dict(disc=disc, offset=hex(o), end=hex(end), source_leaf_sha256=LEAF_SHA,
                  source_system_sha256=sha(system), system_sha256=sha(after),
                  asset=str(ASSET.relative_to(ROOT)), asset_sha256=ASSET_SHA,
                  tiles=tiles, changed_system_bytes=len(delta), texts=list(TEXTS),
                  native_rgb_sha256=sha(decoded.tobytes()), source_background_pixel_exact=False,
                  method='built-in ImageGen text localization; full reviewed image downsampled and RGB565 packed',
                  other_archive_bytes_and_all_headers_unchanged=True)
    return bytes(after), delta, report, decoded


def renderer_settings():
    if sha(RENDERER.read_bytes()) != RENDERER_SHA:
        raise ValueError('Frozen renderer snapshot changed')
    settings = json.loads(RENDERER.read_text())['settings'].copy()
    if settings.get('rend.Resolution') != '1440' or settings.get('rend.TextureFiltering') != '0':
        raise ValueError('Expected the previous 1440p, game-default filtering profile')
    settings.update({'Dreamcast.Cable': '0', 'Dreamcast.AutoLoadState': 'no',
                     'Dreamcast.AutoSaveState': 'no', 'rend.CustomTextures': 'no', 'rend.DumpTextures': 'no'})
    return settings


def build(*,out=OUT,source=SOURCE,status=STATUS,source_status=domina.STATUS,
          exe_sha=EXE_SHA,track_hashes=TRACK_HASHES,patcher=patch,
          preview_name='insert-disc-1-preview.png',texts=TEXTS,
          launcher='English Disc Swap',readme=None,archive='SYSTEM.DAT',version=None,
          patches=None):
    OUT,SOURCE,STATUS,EXE_SHA,TRACK_HASHES,TEXTS = out,source,status,exe_sha,track_hashes,texts
    if OUT.exists():
        raise ValueError('Preserve earlier disc-swap build')
    if shutil.disk_usage(OUT.anchor).free < 3*1024**3:
        raise ValueError('Insufficient free space on E:')
    prior = json.loads((SOURCE/'manifest.json').read_text())
    if prior['status'] != source_status or prior['executable_sha256'] != EXE_SHA:
        raise ValueError('Expected the authenticated source pair')
    domina.zero.combined.verify_files(SOURCE, prior['files'])
    domina.zero.combined.cue_checks(SOURCE)
    for disc in (1, 2):
        row = next(r for r in prior['files'] if r['path'] == track(SOURCE, disc).relative_to(SOURCE).as_posix())
        if row['sha256'] != TRACK_HASHES[disc]:
            raise ValueError('Wrong per-disc track identity')
    settings = renderer_settings()
    patchers = {archive:patcher} if patches is None else dict(patches)
    if not patchers or any(name not in ('SYSTEM.DAT','CHAR.DAT','PARAMETA.DAT') for name in patchers):
        raise ValueError('Expected explicitly named artwork archives')
    OUT.mkdir()
    files, reports = [], []
    executable = (SOURCE/'1ST_READ.BIN').read_bytes()
    if sha(executable) != EXE_SHA:
        raise ValueError('Domina-first executable changed')
    for disc in (1, 2):
        source = track(SOURCE, disc)
        target = track(OUT, disc)
        target.parent.mkdir()
        changes,touched,replacements,archive_reports = {},set(),{},{}
        decoded = None
        for name,apply in patchers.items():
            before,lba = READER.read_file(source,name)
            after,delta,detail,preview_image = apply(before,disc)
            if len(after) != len(before):raise ValueError('Archive allocation changed')
            pending,sectors = domina.zero.names.budget.legacy.sectors.sector_changes(source,lba,after,delta)
            if any(k in changes and changes[k] != value for k,value in pending.items()):
                raise ValueError('Overlapping archive sector edits')
            changes.update(pending);touched.update(sectors)
            replacements[name],archive_reports[name] = after,detail
            if preview_image is not None:
                if decoded is not None:raise ValueError('Supply only one combined preview')
                decoded = preview_image
        touched = sorted(touched)
        report = next(iter(archive_reports.values())) if len(patchers)==1 else dict(disc=disc,archives=archive_reports)
        digest = READER.copy_track(source, target, TRACK_HASHES[disc], changes)
        with source.open('rb') as f:
            directory = list(READER.inject.iso_files(f))
            boot = READER.inject._extent(f, 45000, 32768)
        with target.open('rb') as f:
            if list(READER.inject.iso_files(f)) != directory or READER.inject._extent(f, 45000, 32768) != boot:
                raise ValueError('Boot/directory changed')
            for sector in touched:
                f.seek(sector*2352)
                raw = f.read(2352)
                if mode1_sector.regenerate(raw) != raw:
                    raise ValueError('Invalid sector parity')
        for name, _, _ in directory:
            old, _ = READER.read_file(source, name)
            actual, _ = READER.read_file(target, name)
            if actual != replacements.get(name,old):
                raise ValueError('Unexpected ISO payload change: '+name)
            if name == '1ST_READ.BIN' and actual != executable:
                raise ValueError('Domina-first/Zero unlock/code differs')
        files.append(dict(path=target.relative_to(OUT).as_posix(), bytes=target.stat().st_size, sha256=digest))
        for row in prior['files']:
            if not row['path'].startswith(f'disc{disc}/') or row['path'].endswith('(Track 3).bin'):
                continue
            with (SOURCE/row['path']).open('rb') as src, (OUT/row['path']).open('xb') as dst:
                shutil.copyfileobj(src, dst, 4*1024*1024)
            files.append(dict(row))
        report.update(executable_sha256=EXE_SHA, source_track_sha256=TRACK_HASHES[disc],
                      track_sha256=digest, parity_sectors=touched)
        reports.append(report)
        if disc == 1 and decoded is not None:
            decoded.resize((640, 480), Image.Resampling.NEAREST).save(OUT/preview_name)
        print('Disc', disc, 'declared',','.join(patchers),'artwork changes verified; all other files exact.', flush=True)
    domina.zero.combined.verify_files(OUT, files)
    domina.zero.combined.cue_checks(OUT)
    domina.zero.combined.verify_files(SOURCE, prior['files'])
    (OUT/'1ST_READ.BIN').write_bytes(executable)
    for preview in SOURCE.glob('*-preview.png'):
        if not (OUT/preview.name).exists():shutil.copy2(preview,OUT/preview.name)
    (OUT/'Black Matrix AD.m3u').write_text(''.join(
        f'disc{d}/Black-Matrix Advanced (Japan) (Disc {d}).cue\n' for d in (1, 2)))
    result = dict(status=STATUS, files=files, discs=reports, source=str(SOURCE), source_files=prior['files'],
                  executable_sha256=EXE_SHA, texts=list(TEXTS),
                  initially_highlighted_character='Domina', native_unlock_value=2,
                  modified_archive=next(iter(patchers)) if len(patchers)==1 else None,
                  modified_archives=list(patchers),
                  only_target_scl_descriptors_pixels_and_sector_parity_changed=(list(patchers)==['SYSTEM.DAT']),
                  only_target_archive_artwork_and_sector_parity_changed=True,
                  all_game_code_fonts_movies_scripts_and_other_artwork_unchanged=True,
                  previous_builds_unchanged=True, private_local_only=True,
                  saves_and_profile_configuration_unchanged=True,
                  renderer_launch_only_settings=settings, renderer_snapshot_sha256=RENDERER_SHA,
                  gameplay_verified=False, physical_hardware_verified=False)
    if version is not None:
        result['build_version'] = version
    (OUT/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(readme if readme is not None else (
        'PRIVATE complete English disc pair: red insert-Disc-1 screen translated on BOTH discs.\n'
        'Please insert Disc 1. / Press OPEN to open the disc lid, then replace the disc.\n'
        'The reviewed ImageGen screen is downsampled and RGB565-packed into the existing allocation.\n'
        'Background is not pixel-identical to the original; no other artwork or files changed.\n'
        'Domina first, Zero unlocked, working movie timing, VGA and all font fixes retained exactly.\n'
        f'Use Play - Disc 1 - {launcher}.cmd or the matching Disc 2 launcher in the project folder.\n'
        'Close Flycast first. Existing vga-v2/play VMUs reused directly; no save copies or blank profiles.\n'
        'New launchers apply the prior full 1440p renderer snapshot as launch-only -config options.\n'
        'Existing configuration files, saves, previous builds and original discs remain unchanged.\n'
        'This translates the pictured red prompt only, not every other disc warning.\n'
        'Full binary readbacks passed. Fresh in-game appearance/disc swap and hardware still unverified.\n'
        'Keep all complete discs private/local; do not upload game binaries.\n'))
    print('New private pair verified:', OUT, flush=True)


def launch(disc):
    domina.zero.launch(disc, build=OUT, status=STATUS, settings=renderer_settings())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--launch', type=int, choices=(1, 2))
    args = parser.parse_args()
    if args.extract:
        extract()
    if args.preview:
        system, _ = source_system(1)
        _, _, report, image = patch(system, 1)
        image.resize((640, 480), Image.Resampling.NEAREST).save(REVIEW/'english-native-preview.png')
        print(json.dumps(report, indent=2))
    if args.build:
        build()
    if args.launch:
        launch(args.launch)
