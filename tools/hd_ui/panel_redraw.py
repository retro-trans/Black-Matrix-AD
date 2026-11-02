"""Prepare (never install) a vector-native shared-frame redraw pilot.

Only SYSTEM's first fifteen 32x16 sprites are redrawn. All other atlas pixels
retain the native nearest-neighbor image, or the exact existing 4x HD baseline.
No smoothing/reconstruction filter is applied to the source artwork.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw
import ui_upscale

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'assets/ui/panel-frame.svg'
RECT = (0, 0, 96, 80)
TEXTURE = 'fc87d908.png'
SOURCE_SHA = '1b05a3e5cf8784f90a744d9bbf663c57c46c3b83077d3b808c157df5ae7ccf79'


def copper_finish(flat, scale):
    """Shade the freshly drawn geometry, never sample/filter the old texture.

    All material waves repeat on the 32x16 sprite grid. The near-black panel
    and contour coverage remain unchanged. Broad tarnish, fine warm grain and
    restrained directional edge lighting replace v1's uniform copper fills.
    """
    rgba = np.array(flat)
    rgb = rgba[:, :, :3].astype(np.float64)
    y, x = np.indices(rgb.shape[:2], dtype=np.float64)
    x = (x + .5) / scale
    y = (y + .5) / scale
    u, v = 2*np.pi*x/32, 2*np.pi*y/16
    tarnish = (.23*np.sin(u+.4)*np.cos(v-.8)
               + .12*np.sin(2*u-v+1.1) + .065*np.cos(3*u+2*v))
    grain = (.026*np.sin(23*u+7*v) + .018*np.cos(11*u-19*v)
             + .012*np.sin(37*u+29*v))
    metal = np.clip((rgb[:, :, 0]-8)/60, 0, 1)
    # One output pixel at 4x is a quarter of a source pixel: a fine rim,
    # not an expanded outline or a softened corner.
    step = max(1, round(scale/4))
    padded = np.pad(metal, step, mode='edge')
    left = padded[step:-step, :-2*step]
    above = padded[:-2*step, step:-step]
    right = padded[step:-step, 2*step:]
    below = padded[2*step:, step:-step]
    rim = .27*np.maximum(metal-left, 0) + .18*np.maximum(metal-above, 0)
    recess = .18*np.maximum(metal-right, 0) + .14*np.maximum(metal-below, 0)
    lighting = np.clip(.88+tarnish+grain+rim-recess, .38, 1.48)
    copper = (rgb[:, :, 0] > 8) & (rgb[:, :, 0] > rgb[:, :, 1]*1.4)
    # Work relative to the black substrate to retain antialiased coverage.
    shaded = 8+(rgb-8)*lighting[:, :, None]
    shaded[:, :, 1] += np.maximum(lighting-1, 0)*9
    shaded[:, :, 2] += np.maximum(lighting-1, 0)*8
    rgba[:, :, :3][copper] = np.rint(np.clip(shaded, 0, 255)).astype('uint8')[copper]
    return Image.fromarray(rgba)


def artwork(scale=4, art=ART, finish=True):
    """Render our bounded SVG shape subset, using area coverage at edges.

    BOX supersampling covers fresh vector contours only, not native pixels;
    it cannot produce the ringing/halos of a sharpening reconstruction filter.
    Rectangle bounds are half-open, matching the game's sprite coordinates.
    """
    if scale not in (1, 2, 4, 8):
        raise ValueError('unsupported redraw scale')
    root = art if isinstance(art, ET.Element) else ET.fromstring(Path(art).read_text(encoding='utf-8'))
    if root.attrib != dict(width='96', height='80', viewBox='0 0 96 80'):
        raise ValueError('frame viewport changed')
    factor = scale * 8
    result = Image.new('RGBA', (96*factor, 80*factor))
    draw = ImageDraw.Draw(result)

    def paint(element, inherited):
        kind = element.tag.rsplit('}', 1)[-1]
        if kind == 'title':
            return
        attrs = dict(inherited, **element.attrib)
        if kind in ('svg', 'g'):
            for child in element:
                paint(child, attrs)
            return
        fill = attrs.get('fill')
        if kind == 'rect':
            x, y, w, h = (float(attrs[k]) for k in ('x', 'y', 'width', 'height'))
            if not (0 <= x < x+w <= 96 and 0 <= y < y+h <= 80):
                raise ValueError('rectangle outside frame')
            draw.rectangle((round(x*factor), round(y*factor),
                            round((x+w)*factor)-1, round((y+h)*factor)-1), fill=fill)
        elif kind == 'line':
            values = [float(attrs[k])*factor for k in ('x1', 'y1', 'x2', 'y2')]
            draw.line(values, fill=attrs['stroke'],
                      width=round(float(attrs['stroke-width'])*factor))
        elif kind == 'polygon':
            points = [tuple(map(float, p.split(','))) for p in attrs['points'].split()]
            if any(len(p) != 2 or not (0 <= p[0] <= 96 and 0 <= p[1] <= 80) for p in points):
                raise ValueError('polygon outside frame')
            draw.polygon([(x*factor, y*factor) for x, y in points], fill=fill)
        else:
            raise ValueError('unsupported frame SVG element: '+kind)
    paint(root, {})
    flat = result.resize((96*scale, 80*scale), Image.Resampling.BOX)
    return copper_finish(flat, scale) if finish else flat


def compose(native, baseline=None):
    if native.size != (256, 256):
        raise ValueError('unexpected source atlas')
    if baseline is not None and baseline.size != (1024, 1024):
        raise ValueError('unexpected HD baseline')
    original = (baseline.convert('RGBA') if baseline is not None else
                native.convert('RGBA').resize((1024, 1024), Image.Resampling.NEAREST))
    candidate = original.copy()
    candidate.paste(artwork(), (0, 0))
    changed = np.any(np.array(candidate) != np.array(original), axis=2)
    allowed = np.zeros((1024, 1024), dtype=bool)
    allowed[:320, :384] = True
    if np.any(changed & ~allowed):
        raise ValueError('redraw leaked outside the fifteen frame sprites')
    return candidate, original, int(changed.sum())


def prepare(out, source=ui_upscale.DEFAULT_BUILD/'SYSTEM.DAT'):
    out = Path(out).resolve()
    if not out.is_relative_to((ROOT/'build').resolve()) or out == (ROOT/'build').resolve():
        raise ValueError('use a dedicated directory under build')
    if (out/'manifest.json').exists():
        raise ValueError('pilot already prepared; choose a new output directory')
    data = Path(source).read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError('source SYSTEM differs from verified r35')
    name, native, meta = next(ui_upscale.pages(data, 'SYSTEM'))
    if name != TEXTURE or meta['offset'] != 0xf50:
        raise ValueError('source texture mapping changed')
    target = ui_upscale.TARGET/name
    baseline = None
    if target.exists():
        baseline = Image.open(target).convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    candidate, original, count = compose(native, baseline)
    out.mkdir(parents=True, exist_ok=True)
    (out/'textures').mkdir(exist_ok=True)
    candidate.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(out/'textures'/name)
    candidate.save(out/'atlas-upright.png')
    original.save(out/'baseline-upright.png')
    artwork(8).save(out/'frame-redraw.png')
    # Contact sheet compares identical source sprite rectangles, not a mock game screen.
    comparison = Image.new('RGB', (1560, 700), '#181818')
    draw = ImageDraw.Draw(comparison)
    for x, title, panel in ((12, 'Original (nearest pixels)', native.crop(RECT).resize((768,640), Image.Resampling.NEAREST)),
                            (792, 'Redraw with copper shading', artwork(8))):
        draw.text((x, 12), title, fill='white')
        comparison.paste(panel, (x, 40))
    comparison.save(out/'comparison.png')
    finish_comparison = Image.new('RGB', (1560, 700), '#181818')
    draw = ImageDraw.Draw(finish_comparison)
    for x, title, panel in ((12, 'Previous flat redraw', artwork(8, finish=False)),
                            (792, 'Refined copper finish', artwork(8))):
        draw.text((x, 12), title, fill='white')
        finish_comparison.paste(panel, (x, 40))
    finish_comparison.save(out/'finish-comparison.png')
    report = dict(status='pilot-not-installed', texture=name, source_sha256=SOURCE_SHA,
                  artwork=str(ART.relative_to(ROOT)), artwork_sha256=hashlib.sha256(ART.read_bytes()).hexdigest(),
                  renderer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  finish='periodic copper tarnish, fine grain and directional rim shading; unchanged vector geometry',
                  sprites=list(range(15)), native_rectangle=RECT, changed_hd_pixels=count,
                  unchanged_outside_rectangle=True, scale=4,
                  baseline_file_sha256=hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None,
                  output_file_sha256=hashlib.sha256((out/'textures'/name).read_bytes()).hexdigest(),
                  limitations=['First fifteen shared panel sprites only; not the whole UI.',
                               'Copper finish is newly drawn, not a pixel-exact recreation of the original mottling.',
                               'No in-game seam or visual approval yet; do not auto-install.',
                               'Fonts, icons, portraits and all other atlas regions are unchanged.'])
    (out/'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT/'build/ui-redraw-panels-v2')
    args = p.parse_args()
    print(json.dumps(prepare(args.out), indent=2))
