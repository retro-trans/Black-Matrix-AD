"""Five readable attack-type initials; isolated native copies and guarded HD aliases."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import side_attack_label as pipeline
import noto_font
from build_s_rank_layout_fix import copy_verified

base = pipeline.base
ROOT, TEXTURE = base.ROOT, base.TEXTURE
OUT = ROOT/'build/attack-type-letters-v1'
PACK = OUT/'pack'
STATUS = 'verified-attack-type-letters'
TYPES = ((6, 'V', 'Vertical Slash'), (7, 'H', 'Horizontal Slash'),
         (8, 'T', 'Thrust'), (11, 'R', 'Range'), (9, 'B', 'Blunt'))
RECTS = {6:(0,16,16,32), 7:(16,16,32,32), 8:(32,16,48,32),
         9:(48,16,64,32), 11:(80,16,96,32)}
# Native 5x7 capitals: double horizontal pixels compensate the game's 240-line
# framebuffer's vertical display stretch. These are badge art, NOT font edits.
GLYPHS = {
    'V': ('10001','10001','10001','10001','10001','01010','00100'),
    'H': ('10001','10001','10001','11111','10001','10001','10001'),
    'T': ('11111','00100','00100','00100','00100','00100','00100'),
    'R': ('11110','10001','10001','11110','10100','10010','10001'),
    'B': ('11110','10001','10001','11110','10001','10001','11110'),
}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def sources():
    report = read_json(ROOT/'build/choice-text-inset-v2/build-verification.json')
    if report['status'] != 'verified-choice-text-inset':
        raise ValueError('Unverified source builds')
    names = list(report['sources'].values())
    native = [n for n in names if '-native-' in n]
    hd = [n for n in names if n not in native]
    if len(native) != 4 or len(hd) != 4:
        raise ValueError('Unexpected mode inventory')
    return native, hd


def artwork(letter, hd=False):
    if letter not in GLYPHS:
        raise ValueError('Unknown attack initial')
    size = 64 if hd else 16
    mask = Image.new('L', (size, size))
    if hd:
        font = ImageFont.truetype(str(noto_font.default_font()), 80)
        box = font.getbbox(letter)
        glyph = Image.new('L', (box[2]-box[0], box[3]-box[1]))
        ImageDraw.Draw(glyph).text((-box[0], -box[1]), letter, font=font, fill=255)
        width = round(56*glyph.width/glyph.height)
        width = min(40, width)
        glyph = glyph.resize((width, 28), Image.Resampling.LANCZOS)
        mask.paste(glyph, ((64-width)//2, 16))
    else:
        draw = ImageDraw.Draw(mask)
        for y, row in enumerate(GLYPHS[letter]):
            for x, bit in enumerate(row):
                if bit == '1':
                    draw.rectangle((3+x*2, 4+y, 4+x*2, 4+y), fill=255)
    result = Image.new('RGBA', mask.size, (240,168,66,0))
    result.putalpha(mask)
    return result


def patch(before):
    # Authenticate all five old tiles against the previously installed native
    # pictogram build, not a permissive pixel overwrite of unknown user changes.
    reference = base.read(ROOT/'build/s-rank-checklist-native-v4-side-icon-v2', 1)[0]
    original = (ROOT/'extracted/SYSTEM.DAT').read_bytes()
    old, _ = base.layers.page(before, TEXTURE)
    known, _ = base.layers.page(reference, TEXTURE)
    after = bytearray(before)
    allowed = set()
    for index, letter, _ in TYPES:
        rect = RECTS[index]
        pos = 0x21000+48+index*16
        if before[pos:pos+16] != original[pos:pos+16]:
            raise ValueError('Attack sprite geometry changed')
        if old.crop(rect).tobytes() != known.crop(rect).tobytes():
            raise ValueError('Unknown attack badge pixels')
        for offset, value in base.native.encode(before, TEXTURE, rect, artwork(letter)):
            after[offset:offset+2] = value
            allowed.update((offset, offset+1))
    delta = {int(i):int(after[i]) for i in np.flatnonzero(
        np.frombuffer(before, dtype='u1') != np.frombuffer(after, dtype='u1'))}
    if not delta or not set(delta).issubset(allowed):
        raise ValueError('Out-of-badge changes')
    return bytes(after), delta


def prepare():
    if OUT.exists():
        raise ValueError('Preserve existing preparation')
    native, hd = sources()
    aliases = {r['texture'] for r in read_json(ROOT/'build/side-attack-icon-v2/pack/manifest.json')['textures']}
    # These captured menu revisions have different neighboring text. Update
    # their own atlas in place, never substitute another revision's full sheet.
    aliases.update(r['texture'] for r in read_json(ROOT/'build/horizontal-battle-followup-v1/matches.json'))
    rows = []
    for name in (*native, *hd):
        for disc in (1,2):
            before, _, lba = base.read(ROOT/'build'/name, disc)
            _, key = base.layers.page(before, TEXTURE)
            aliases.add(key)
            if name in native:
                after, delta = patch(before)
                _, new_key = base.layers.page(after, TEXTURE)
                rows.append(dict(source=name, disc=disc, lba=lba, old_key=key, new_key=new_key,
                    before_sha256=base.ui.digest(before), after_sha256=base.ui.digest(after), changed_bytes=len(delta)))
    pending = {}
    for key in sorted(aliases):
        with Image.open(base.ui.TARGET/key) as image:
            high = image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        result, _ = base.interface.compose(high, [(RECTS[i],artwork(c,True),label) for i,c,label in TYPES])
        pending[key] = result.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    for row in rows:
        image, key = pending[row['old_key']], row['new_key']
        if key in pending and pending[key].tobytes() != image.tobytes():
            raise ValueError('Alias collision')
        if key not in pending and (base.ui.TARGET/key).exists():
            raise ValueError('New alias already exists')
        pending[key] = image
    (PACK/'textures').mkdir(parents=True)
    (PACK/'originals').mkdir()
    textures = []
    for key, image in pending.items():
        path = base.ui.TARGET/key
        previous = path.read_bytes() if path.exists() else None
        if previous is not None:
            (PACK/'originals'/key).write_bytes(previous)
        image.save(PACK/'textures'/key)
        textures.append(dict(texture=key, original_file_sha256=base.ui.digest(previous) if previous else None,
                             output_file_sha256=base.ui.digest((PACK/'textures'/key).read_bytes())))
    write_json(PACK/'manifest.json', dict(textures=textures))
    write_json(OUT/'preparation.json', dict(sources=rows, types=TYPES))
    preview()
    print('Prepared five attack initials and', len(textures), 'HD aliases.', flush=True)


def preview():
    native, _ = sources()
    before = base.read(ROOT/'build'/native[0],1)[0]
    after, _ = patch(before)
    old, _ = base.layers.page(before,TEXTURE)
    new, _ = base.layers.page(after,TEXTURE)
    sheet = Image.new('RGB',(840,420),'#120e08')
    draw = ImageDraw.Draw(sheet)
    draw.text((20,12),'Attack types - before / native letters / HD letters',fill='white')
    for col,(index,letter,label) in enumerate(TYPES):
        x = 12+col*166
        draw.text((x,38),label,fill='#f0a842')
        for row,tile in enumerate((old.crop(RECTS[index]),new.crop(RECTS[index]),artwork(letter,True))):
            # Show the game's 1:2 source-to-screen pixel aspect, not square tiles.
            tile = tile.resize((64,128),Image.Resampling.NEAREST if row<2 else Image.Resampling.LANCZOS)
            sheet.paste(tile,(x+20,55+row*115),tile)
    draw.text((20,400),'Offline comparison; actual badge tiles, enlarged with vertical display stretch.',fill='white')
    sheet.save(OUT/'preview.png')


def build():
    # Reuse the authenticated whole-track copy and exact SYSTEM readback pipeline.
    native, hd = sources()
    pipeline.OUT, pipeline.PACK = OUT, PACK
    pipeline.NATIVE, pipeline.HD = native, hd
    pipeline.DEST_SUFFIX = '-attack-letters-v1'
    pipeline.patch = patch
    pipeline.build()
    report = read_json(OUT/'build-verification.json')
    report.update(status=STATUS, types=TYPES,
        scope='Only SYSTEM attack-type sprites 6,7,8,9,11. Executables, gameplay, other pixels and saves unchanged.')
    for dest in report['sources'].values():
        path = ROOT/'build'/dest/'manifest.json'
        manifest = read_json(path)
        manifest['status'] = STATUS
        write_json(path,manifest)
    write_json(OUT/'build-verification.json',report)


def install():
    report = read_json(OUT/'build-verification.json')
    if report['status'] != STATUS or len(report['variants']) != 8:
        raise ValueError('Incomplete native builds')
    for dest in report['sources'].values():
        manifest = read_json(ROOT/'build'/dest/'manifest.json')
        if manifest['status'] != STATUS or manifest['variants'] != [r for r in report['variants'] if r['destination']==dest]:
            raise ValueError('Manifest mismatch')
    def inventory():
        return {p.name:(p.stat().st_size,p.stat().st_mtime_ns) for p in base.ui.TARGET.glob('*.png')}
    before = inventory()
    changed = {r['texture'] for r in read_json(PACK/'manifest.json')['textures']}
    result = base.interface.apply(PACK)
    after = inventory()
    if set(after) != set(before)|changed or any(after.get(n)!=v for n,v in before.items() if n not in changed):
        raise ValueError('Unrelated HD textures changed')
    result.update(status='installed-attack-type-letters', live_game_verified=False,
        unrelated_file_metadata_preserved=len(set(before)-changed))
    write_json(OUT/'installation.json',result)
    print('Installed:',result,flush=True)


def verify():
    native, hd = sources()
    mapping = read_json(OUT/'build-verification.json')['sources']
    expected = {str(ROOT/'build'/mapping.get(n,n)/('disc2' if d==2 else 'disc')/
        f'Black-Matrix Advanced (Japan) (Disc {d}).cue').lower() for n in native+hd for d in (1,2)}
    results = []
    for n in (False,True):
        for a in (False,True):
            for r in (False,True):
                for d in (False,True):
                    flags = ['-NotoRegular','-DryRun']+[f for yes,f in ((n,'-NoHDTextures'),(a,'-AnalogMovement'),(r,'-SRankChecklist'),(d,'-Disc2Cards')) if yes]
                    run = subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                        str(ROOT/'tools/hd_ui/run_stock_atlas.ps1'),*flags],capture_output=True,text=True,check=True,timeout=60)
                    results.append(dict(flags=flags,result=json.loads(run.stdout)))
    if {r['result']['Cue'].lower() for r in results} != expected:
        raise ValueError('Unexpected launcher selection')
    write_json(OUT/'launcher-verification.json',dict(variants=results,live_emulator_launched=False))
    print('All 16 launcher selections verified.',flush=True)


if __name__ == '__main__':
    {'prepare':prepare,'build':build,'install':install,'verify':verify,'preview':preview}[sys.argv[1]]()
