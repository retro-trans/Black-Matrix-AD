"""Reconstruct original house tiles and round-trip an assembled HD image."""
import json
import hashlib
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image, ImageDraw
import all_title_cards
import pvr_atlas
import ui_upscale
import xxhash

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'build/house-texture-v1'
SOURCE_SHA = 'e9820cbc12fe21afd527709380421fc8bf13dc58c6f1ed5df8e266700a9283d6'
OFFSETS = (0x416840, 0x51D040)
SCALE = 4


def source():
    data = all_title_cards.source(1, 'MAP')
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError('Original MAP archive changed')
    return data


def native_pages(data, offset):
    _, _, _, pages = pvr_atlas.scl_layout(data, offset)
    return [Image.fromarray(ui_upscale.colors(
        np.frombuffer(data,dtype='<u2',count=65536,offset=o+16)[ui_upscale.morton(256)],1)).convert('RGB')
        for o in pages]


def assemble(data, offset, atlases, scale=1):
    cols, rows, ds, pages = pvr_atlas.scl_layout(data, offset)
    if len(atlases) != len(pages) or any(im.size != (256*scale,256*scale) for im in atlases):
        raise ValueError('Atlas count or dimensions differ')
    result = Image.new('RGB',(cols*16*scale,rows*16*scale))
    for i,d in enumerate(ds):
        x,y,page = d>>8&255,d&255,d>>16
        result.paste(atlases[page].crop((x*scale,y*scale,(x+16)*scale,(y+16)*scale)),
                     ((i%cols)*16*scale,(i//cols)*16*scale))
    return result


def split(data, offset, assembled, scale=1):
    cols, rows, ds, _ = pvr_atlas.scl_layout(data, offset)
    if assembled.size != (cols*16*scale,rows*16*scale):
        raise ValueError('Assembled image dimensions differ')
    atlases = [im.resize((256*scale,256*scale),Image.Resampling.NEAREST) for im in native_pages(data,offset)]
    seen = {}
    for i,d in enumerate(ds):
        x,y,page = d>>8&255,d&255,d>>16
        tile = assembled.crop(((i%cols)*16*scale,(i//cols)*16*scale,(i%cols+1)*16*scale,(i//cols+1)*16*scale)).convert('RGB')
        if d in seen and seen[d] != tile.tobytes():
            raise ValueError('Repeated tile has inconsistent HD pixels')
        seen[d] = tile.tobytes()
        atlases[page].paste(tile,(x*scale,y*scale))
    if assemble(data,offset,atlases,scale).tobytes() != assembled.convert('RGB').tobytes():
        raise ValueError('Tile round-trip is not pixel exact')
    return atlases


def decode(data, offset):
    cols, rows, descriptors, pages = pvr_atlas.scl_layout(data, offset)
    atlases = [Image.fromarray(ui_upscale.colors(
        np.frombuffer(data, dtype='<u2', count=65536, offset=o+16)[ui_upscale.morton(256)], 1))
        for o in pages]
    result = Image.new('RGB', (cols*16, rows*16))
    for i, d in enumerate(descriptors):
        x,y,page = d>>8&255,d&255,d>>16
        result.paste(atlases[page].crop((x,y,x+16,y+16)), ((i%cols)*16,(i//cols)*16))
    return result


def inventory():
    data = all_title_cards.source(1, 'MAP')
    offsets = []; p = 0
    while (p := data.find(b'SCL ',p)) >= 0:
        offsets.append(p); p += 4
    OUT.mkdir(exist_ok=True)
    sheet = Image.new('RGB', (1200, ((41+3)//4)*210), '#242424')
    draw = ImageDraw.Draw(sheet)
    for i,o in enumerate(offsets[:41]):
        im = decode(data,o); im.thumbnail((290,180))
        x,y = (i%4)*300,(i//4)*210
        sheet.paste(im,(x,y)); draw.text((x,y+184), f'{i}: MAP {o:#x}', fill='white')
    sheet.save(OUT/'map-inventory.png')
    print(OUT/'map-inventory.png')


def prepare():
    data = source()
    OUT.mkdir(exist_ok=True)
    reports = []
    for offset in OFFSETS:
        cols, rows, ds, pages = pvr_atlas.scl_layout(data, offset)
        original = decode(data, offset)
        tag = f'house-{offset:x}'
        original.save(OUT/(tag+'-native.png'))
        original.resize((original.width, original.height*2), Image.Resampling.NEAREST).save(OUT/(tag+'-display.png'))
        counts = {d:ds.count(d) for d in set(ds)}
        repeat_nonblack = []
        for i,d in enumerate(ds):
            if counts[d]>1:
                tile = original.crop(((i%cols)*16,(i//cols)*16,(i%cols+1)*16,(i//cols+1)*16))
                if tile.getbbox(): repeat_nonblack.append(i)
        page_rows = []
        for o in pages:
            raw = data[o+16:o+16+131072]
            name = '%x.png'%(xxhash.xxh32(raw,seed=7).intdigest() ^ 0x08000000)
            dump = ui_upscale.DUMPS/name
            if dump.exists():
                pixels = Image.fromarray(ui_upscale.colors(np.frombuffer(raw,dtype='<u2')[ui_upscale.morton(256)],1))
                captured = Image.open(dump).convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                equal = captured.size == pixels.size and np.array_equal(np.array(captured),np.array(pixels))
            else: equal = None
            page_rows.append(dict(offset=o,name=name,captured_exact=equal,already_installed=(ui_upscale.TARGET/name).exists()))
        reports.append(dict(offset=offset,source_sha256=hashlib.sha256(data).hexdigest(),
            size=original.size,tiles=len(ds),unique_tiles=len(set(ds)),repeated_nonblack_positions=repeat_nonblack,
            descriptors=ds,pages=page_rows))
    (OUT/'source-manifest.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    for r in reports:print({k:v for k,v in r.items() if k not in ('descriptors','repeated_nonblack_positions')},'repeated_nonblack',len(r['repeated_nonblack_positions']))


def pack(generated):
    """Stage a review pack only; do not write to the installed textures."""
    data = source()
    folder = OUT/'review-pack'
    if folder.exists():
        raise ValueError('Review pack exists; refusing to overwrite')
    original = decode(data,OFFSETS[1])
    with Image.open(generated) as im:
        gen_size = im.size
        if abs(im.width/im.height-original.width/(original.height*2)) > 0.03:
            raise ValueError('Generated panorama aspect changed too far')
        high = im.convert('RGB').resize((original.width*SCALE,original.height*SCALE),Image.Resampling.LANCZOS)
    pixels = np.array(high)
    # Exact black silhouette and repeated blank tiles belong to the source,
    # not to a generative model. Keep them black in both house states.
    black = np.all(np.array(original)==0,axis=2)
    pixels[np.repeat(np.repeat(black,SCALE,0),SCALE,1)] = 0
    high = Image.fromarray(pixels)
    pending = {}; report = []
    for offset in OFFSETS:
        low = decode(data,offset)
        expected = high.copy()
        # Two house variants differ only at the fireplace grate. Preserve the
        # original animated-fire contact region and its state-specific pixels.
        rect = (576,176,656,208)
        patch = low.crop(rect).resize((80*SCALE,32*SCALE),Image.Resampling.NEAREST)
        expected.paste(patch,(rect[0]*SCALE,rect[1]*SCALE))
        pages = split(data,offset,expected,SCALE)
        _,_,ds,offsets = pvr_atlas.scl_layout(data,offset)
        for o,im in zip(offsets,pages):
            raw = data[o+16:o+16+131072]
            name = '%x.png'%(xxhash.xxh32(raw,seed=7).intdigest() ^ 0x08000000)
            capture = ui_upscale.DUMPS/name
            native = Image.fromarray(ui_upscale.colors(np.frombuffer(raw,dtype='<u2')[ui_upscale.morton(256)],1))
            if not capture.exists() or Image.open(capture).convert('RGBA').tobytes() != native.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes():
                raise ValueError('Missing or mismatched captured atlas: '+name)
            if (ui_upscale.TARGET/name).exists():
                raise ValueError('Existing installed texture would be replaced: '+name)
            if name in pending and pending[name].tobytes() != im.tobytes():
                raise ValueError('Shared house-state atlas differs: '+name)
            pending[name] = im
        report.append(dict(offset=offset,tiles=len(ds),atlases=len(pages),round_trip_exact=True))
    folder.mkdir(); (folder/'textures').mkdir()
    texture_rows = []
    for name,im in pending.items():
        dest = folder/'textures'/name
        im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(dest)
        texture_rows.append(dict(texture=name,original_file_sha256=None,output_file_sha256=ui_upscale.digest(dest.read_bytes())))
    # Decode exported PNGs again to prove naming/orientation, not just in-memory
    # assembly. Display with the game's 2:1 vertical pixel aspect correction.
    for offset in OFFSETS:
        _,_,_,offsets = pvr_atlas.scl_layout(data,offset)
        ims = []
        for o in offsets:
            name = '%x.png'%(xxhash.xxh32(data[o+16:o+16+131072],seed=7).intdigest() ^ 0x08000000)
            ims.append(Image.open(folder/'textures'/name).convert('RGB').transpose(Image.Transpose.FLIP_TOP_BOTTOM))
        assembled = assemble(data,offset,ims,SCALE)
        assembled.save(folder/f'house-{offset:x}-assembled.png')
        assembled.resize((3520,1792),Image.Resampling.LANCZOS).save(folder/f'house-{offset:x}-preview.png')
    manifest = dict(status='staged-preview-not-installed',scale=SCALE,generated_size=gen_size,
        source_sha256=SOURCE_SHA,variants=report,textures=texture_rows,
        preserved='original black silhouette; native fireplace grate region in both states; unused atlas slots; all non-background assets',
        in_game_verification=False,artwork_alignment='requires visual review; generative restoration is not pixel-identical')
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


def verify_pack(texture_dir=None):
    """Check the actual PNGs, capture keys and reconstructed approved masters."""
    folder = OUT/'review-pack'
    texture_dir = Path(texture_dir) if texture_dir is not None else folder/'textures'
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    data = source()
    expected = {r['texture']:r['output_file_sha256'] for r in manifest['textures']}
    if len(expected) != 9 or manifest['source_sha256'] != SOURCE_SHA:
        raise ValueError('Unexpected house pack manifest')
    for name,sha in expected.items():
        if Path(name).name != name or ui_upscale.digest((texture_dir/name).read_bytes()) != sha:
            raise ValueError('House texture checksum mismatch: '+name)
        with Image.open(texture_dir/name) as im:
            if im.size != (1024,1024) or im.mode != 'RGBA':
                raise ValueError('Unexpected HD atlas format')
    used = set(); checks = []
    for offset in OFFSETS:
        _,_,ds,offsets = pvr_atlas.scl_layout(data,offset)
        pages = []
        for o,native in zip(offsets,native_pages(data,offset)):
            raw = data[o+16:o+16+131072]
            name = '%x.png'%(xxhash.xxh32(raw,seed=7).intdigest() ^ 0x08000000)
            used.add(name)
            with Image.open(ui_upscale.DUMPS/name) as capture:
                if capture.convert('RGB').transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes() != native.tobytes():
                    raise ValueError('Original capture no longer matches texture key')
            with Image.open(texture_dir/name) as im:
                pages.append(im.convert('RGB').transpose(Image.Transpose.FLIP_TOP_BOTTOM))
        actual = assemble(data,offset,pages,SCALE)
        with Image.open(folder/f'house-{offset:x}-assembled.png') as approved:
            if actual.size != approved.size or actual.tobytes() != approved.convert('RGB').tobytes():
                raise ValueError('Exported atlas reassembly differs from approved master')
        checks.append(dict(offset=offset,tiles=len(ds),pixel_exact=True))
    if used != set(expected):
        raise ValueError('Missing or extra house textures')
    return dict(textures=len(expected),variants=checks,texture_dimensions=[1024,1024],
                in_game_verified=False)


def install():
    folder = OUT/'review-pack'
    verify_pack()
    protected = {p.name:ui_upscale.digest(p.read_bytes()) for p in ui_upscale.TARGET.glob('*.png')}
    action = ui_upscale.apply(folder)
    checks = verify_pack(ui_upscale.TARGET)
    if any(ui_upscale.digest((ui_upscale.TARGET/name).read_bytes()) != sha for name,sha in protected.items()):
        raise ValueError('Pre-existing texture changed')
    report = dict(status='installed-verified-house-textures',**action,verification=checks,
                  existing_textures_preserved=len(protected),
                  note='HD replacement textures only; native mode, discs, saves and emulator settings unchanged. Restart Flycast to load new textures.')
    (OUT/'installation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    if '--install' in sys.argv: install()
    elif '--verify' in sys.argv: print(json.dumps(verify_pack(),indent=2))
    elif '--pack' in sys.argv: pack(Path(sys.argv[sys.argv.index('--pack')+1]))
    elif '--prepare' in sys.argv: prepare()
    else: inventory()
