"""Build native-only disc copies with a compact sword; never alter HD inputs.

The existing HD replacement is looked up by the native texture hash. Keeping
the r35 discs untouched avoids invalidating that lookup and all HD overlays.
Only the native launcher uses these sibling copies. Emulator images only:
like tools/inject.py, this does not rebuild raw-sector EDC/ECC for hardware.
"""
import hashlib
import json
import shutil
import struct
from pathlib import Path

from PIL import Image, ImageDraw
import vertical_attack_icon as icon
import inject

ROOT = icon.ROOT
SOURCE = ROOT/'build/reusable-atlas-noto-ui-r35'
OUT = ROOT/'build/reusable-atlas-noto-ui-r35-native-sword-v1'
SIZE, Y = 10, 1  # Independent of future HD art/layout adjustments.
SOURCE_HASHES = {
    'SYSTEM.DAT': '1b05a3e5cf8784f90a744d9bbf663c57c46c3b83077d3b808c157df5ae7ccf79',
    'SYSTEM.disc2.DAT': '7333756ee1da5dbc9f1854873b55a21dbf86f6987e8439f932cdd08222991121',
}


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def compact_image():
    high = Image.new('RGBA', (64, 64))
    high.paste(icon.artwork().resize((SIZE*4, SIZE*4), Image.Resampling.LANCZOS),
               ((64-SIZE*4)//2, Y*4))
    return high.resize((16, 16), Image.Resampling.LANCZOS)


def compact_badge():
    words = []
    for r, g, b, a in compact_image().getdata():
        r, g, b = (c*a//255 for c in (r, g, b))
        words.append(0x8000 | (r*31//255)<<10 | (g*31//255)<<5 | b*31//255 if a >= 64 else 0)
    return struct.pack('<256H', *words)


def patch_system(source):
    icon.validate_geometry(source)
    old = b''.join(source[o:o+2] for o in icon.sites())
    target = compact_badge()
    if old not in (icon.native_badge(), target):
        raise ValueError('unknown native sword pixels')
    result = bytearray(source)
    for i, offset in enumerate(icon.sites()):
        result[offset:offset+2] = target[i*2:i*2+2]
    return bytes(result)


def raw_sites(lba):
    return [(lba-inject.HIGH_DENSITY_LBA+o//2048)*2352+16+o%2048 for o in icon.sites()]


def verify_track(source, target, allowed):
    """Prove every raw byte outside the 256 sprite words is unchanged."""
    if source.stat().st_size != target.stat().st_size:
        raise ValueError('track size changed')
    changed = 0
    with source.open('rb') as a, target.open('rb') as b:
        pos = 0
        while old := a.read(4*1024*1024):
            new = b.read(len(old))
            if old != new:
                repaired = bytearray(new)
                for off in allowed:
                    if pos <= off < pos+len(old):
                        i = off-pos
                        changed += sum(x != y for x, y in zip(old[i:i+2], new[i:i+2]))
                        repaired[i:i+2] = old[i:i+2]
                if repaired != old:
                    raise ValueError('unexpected change outside native sword')
            pos += len(old)
    return changed


def snapshot():
    paths = list(SOURCE.rglob('*'))
    paths += list((ROOT/'build/stock-atlas-run/data/textures/T20101M').rglob('*'))
    paths += [icon.ART, ROOT/'tools/hd_ui/vertical_attack_icon.py']
    return {str(p.relative_to(ROOT)): digest(p) for p in paths if p.is_file()}


def preview():
    # Quantized native bytes, not a smooth HD proxy.
    sheet = Image.new('RGB', (384,224), '#161616')
    draw = ImageDraw.Draw(sheet)
    for index, (label, data) in enumerate((('Previous native', icon.native_badge()),
                                          ('Fixed native', compact_badge()))):
        im = Image.new('RGBA', (16,16))
        im.putdata([((w>>10&31)*255//31,(w>>5&31)*255//31,(w&31)*255//31,
                     255 if w&0x8000 else 0) for w in struct.unpack('<256H', data)])
        x = index*192
        draw.text((x+12,8),label,fill='white')
        im = im.resize((128,128),Image.Resampling.NEAREST)
        sheet.paste(im,(x+32,32),im)
        draw.line((x+8,120,x+184,120),fill='#9b682b')
        draw.text((x+12,180),'Line: next row begins',fill='#dddddd')
    sheet.save(OUT/'comparison.png')


def build():
    if OUT.exists():
        raise ValueError('native output already exists; refusing to overwrite')
    protected = snapshot()
    systems = {}
    for name, expected in SOURCE_HASHES.items():
        if digest(SOURCE/name) != expected:
            raise ValueError('unrecognized r35 source: '+name)
        systems[name] = patch_system((SOURCE/name).read_bytes())
    OUT.mkdir()
    discs = []
    for number, dirname, system in ((1,'disc','SYSTEM.DAT'),(2,'disc2','SYSTEM.disc2.DAT')):
        source_dir, target_dir = SOURCE/dirname, OUT/dirname
        shutil.copytree(source_dir,target_dir)  # New files, never hard links.
        filename = f'Black-Matrix Advanced (Japan) (Disc {number}) (Track 3).bin'
        source_track, target_track = source_dir/filename, target_dir/filename
        with source_track.open('rb') as f:
            lba,size = inject.find(f,'SYSTEM.DAT')
            if inject._extent(f,lba,size) != (SOURCE/system).read_bytes():
                raise ValueError('source disc/archive mismatch')
        offsets = raw_sites(lba)
        with target_track.open('r+b') as f:
            for archive_offset, raw_offset in zip(icon.sites(), offsets):
                f.seek(raw_offset)
                f.write(systems[system][archive_offset:archive_offset+2])
        with target_track.open('rb') as f:
            if inject._extent(f,lba,size) != systems[system]:
                raise ValueError('native disc readback mismatch')
        changed = verify_track(source_track,target_track,offsets)
        (OUT/system).write_bytes(systems[system])
        discs.append(dict(disc=number,changed_raw_bytes=changed,only_sword_words_changed=True,
                          system_sha256=digest(OUT/system),track_sha256=digest(target_track)))
    after = snapshot()
    if protected != after:
        raise ValueError('HD source or texture files changed during native build')
    preview()
    report = dict(status='verified-native-only',size=SIZE,y=Y,sprite=icon.SPRITE,
                  hd_files_unchanged=True,protected_files=protected,discs=discs,
                  live_game_tested=False,scope='Native launcher only; HD source, textures, executable and saves untouched')
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='protected_files'},indent=2))


if __name__ == '__main__':
    build()
