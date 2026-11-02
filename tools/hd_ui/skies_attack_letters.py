"""Carry the previously approved attack initials into the private VGA font test.

Only five SYSTEM badge rectangles change. Font, executable/video hook, weapon
icons, descriptors, scripts and saves remain exact. Raw sector parity is fixed.
"""
import argparse
import json
import shutil
import struct
import numpy as np
from PIL import Image, ImageDraw
import skies_vga_compat as previous
import attack_type_letters as letters
import native_translation_parity as native
import pvr_atlas

ROOT = previous.ROOT
prior = previous.prior
SOURCE = previous.CABLE_OUT
SOURCE_SHA = 'd1643e0e318e4cf738a9accd14f91deefe5a70e683e8c15670de1ae2bb6e28dd'
SYSTEM_SHA = '56669218ec4316c361803c036bdf69df32161a7dda5cd46acf97042900d34be1'
OUT = ROOT / 'build/skies-vga-compat-v3-attack-letters'
STATUS = 'verified-skies-vga-attack-letters'


def patch(system):
    if prior.sha(system) != SYSTEM_SHA:
        raise ValueError('Unknown v2 SYSTEM archive')
    original = (ROOT / 'extracted/SYSTEM.DAT').read_bytes()
    result = bytearray(system)
    allowed = set()
    for index, letter, _ in letters.TYPES:
        rect = letters.RECTS[index]
        pos = 0x21000 + 48 + index * 16
        if system[pos:pos+16] != original[pos:pos+16] or struct.unpack_from('<8H', system, pos) != (16,16,*rect,0,0):
            raise ValueError('Unexpected attack badge geometry')
        for off, value in native.encode(system, letters.TEXTURE, rect, letters.artwork(letter)):
            result[off:off+2] = value
            allowed.update((off, off+1))
    delta = np.flatnonzero(np.frombuffer(system, dtype='u1') != np.frombuffer(result, dtype='u1')).tolist()
    if not delta or not set(delta) <= allowed:
        raise ValueError('Out-of-badge changes')
    return bytes(result), delta, allowed


def sector_changes(source, lba, after, delta):
    """Only changed data sectors and their EDC/P/Q; source already verified."""
    grouped = {}
    for offset in delta:
        sector = lba - 45000 + offset // 2048
        grouped.setdefault(sector, []).append(offset)
    changes = {}
    with source.open('rb') as stream:
        for sector, offsets in grouped.items():
            stream.seek(sector * 2352)
            raw = stream.read(2352)
            if previous.mode1_sector.regenerate(raw) != raw:
                raise ValueError('Source sector has invalid parity')
            candidate = bytearray(raw)
            for off in offsets:
                candidate[16 + off % 2048] = after[off]
            fixed = previous.mode1_sector.regenerate(candidate)
            if fixed[:16] != raw[:16] or fixed[16:2064] != candidate[16:2064]:
                raise ValueError('Sector regeneration changed headers or payload')
            changes.update({sector*2352+i: b for i, (a,b) in enumerate(zip(raw, fixed)) if a != b})
    return changes, sorted(grouped)


def preview(before, after):
    image = Image.new('RGBA', (760,220), '#100e0a')
    draw = ImageDraw.Draw(image)
    draw.text((10,5), 'Approved attack initials: before / after (offline, display aspect 1:2)', fill='white')
    for col, (index, letter, meaning) in enumerate(letters.TYPES):
        x = 10 + col*150
        draw.text((x,25), letter+' - '+meaning, fill='#f0a842')
        for row, data in enumerate((before, after)):
            tile = pvr_atlas.decode(data, letters.TEXTURE).crop(letters.RECTS[index])
            tile = tile.resize((64,128), Image.Resampling.NEAREST)
            image.alpha_composite(tile, (x+row*70,55))
        draw.text((x,190), 'Before       After', fill='white')
    image.save(OUT / 'attack-letters-preview.png')


def run(build=False):
    source = SOURCE / 'disc2' / prior.TRACK
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    if manifest['track_sha256'] != SOURCE_SHA or prior.digest(source) != SOURCE_SHA:
        raise ValueError('VGA source differs')
    system, lba = prior.read_file(source, 'SYSTEM.DAT')
    after, delta, _ = patch(system)
    report = dict(status=STATUS if build else 'planned-skies-vga-attack-letters', disc=2,
        source=str(SOURCE.relative_to(ROOT)), source_sha256=SOURCE_SHA,
        types=letters.TYPES, changed_system_bytes=len(delta), system_sha256=prior.sha(after),
        executable_sha256=manifest['executable_sha256'], executable_and_vga_boot_unchanged=True,
        font_geometry_and_renderer_unchanged=True, weapon_icons_and_descriptors_unchanged=True,
        saves_unchanged=True, in_game_visual_verified=False, physical_hardware_verified=False,
        timing_proof_reused_from=str(SOURCE.relative_to(ROOT) / 'manifest.json'))
    if not build:
        print(json.dumps(report, indent=2)); return
    if OUT.exists():
        raise ValueError('Preserve previous badge build')
    changes, sectors = sector_changes(source, lba, after, delta)
    OUT.mkdir(); folder = OUT / 'disc2'; folder.mkdir()
    preview(system, after)
    target = folder / source.name
    report['track_sha256'] = prior.copy_track(source, target, SOURCE_SHA, changes)
    report.update(changed_raw_bytes=len(changes), parity_repaired_sectors=sectors)
    with source.open('rb') as stream:
        directory = list(prior.inject.iso_files(stream))
        boot = prior.inject._extent(stream,45000,32768)
    with target.open('rb') as stream:
        if list(prior.inject.iso_files(stream)) != directory or prior.inject._extent(stream,45000,32768) != boot:
            raise ValueError('Boot or directory changed')
        for sector in sectors:
            stream.seek(sector*2352); raw=stream.read(2352)
            if previous.mode1_sector.regenerate(raw) != raw:
                raise ValueError('Output parity invalid')
    report['files'] = []
    for name, _, _ in directory:
        before, _ = prior.read_file(source, name)
        output, _ = prior.read_file(target, name)
        if output != (after if name == 'SYSTEM.DAT' else before):
            raise ValueError('Unrelated payload changed: '+name)
        report['files'].append(dict(name=name, sha256=prior.sha(output)))
    report['companions'] = []
    for path in source.parent.iterdir():
        if path.is_file() and path != source:
            shutil.copy2(path, folder/path.name)
            if prior.digest(path) != prior.digest(folder/path.name):
                raise ValueError('Companion changed')
            report['companions'].append(dict(file=path.name, sha256=prior.digest(path)))
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--build',action='store_true')
    run(parser.parse_args().build)
