"""Install or restore the approved copper panels in the isolated profile only.

This is one shared texture, not a full-UI upscale or a Status-only code patch.
No disc, settings, save or running-emulator changes are made.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
import panel_redraw
import ui_upscale

PACK = panel_redraw.ROOT/'build/ui-redraw-panels-v2'
APPROVED_SHA = '90e903882eefa7c15c714150e046c055f297293fd783236c8d9ca2bfa4bd0213'


def validate(pack=PACK):
    pack = Path(pack)
    report = json.loads((pack/'manifest.json').read_text(encoding='utf-8'))
    if (report['texture'] != panel_redraw.TEXTURE
            or report['output_file_sha256'] != APPROVED_SHA
            or report['baseline_file_sha256'] is not None):
        raise ValueError('not the approved copper pack / empty prior replacement slot')
    payload = (pack/'textures'/panel_redraw.TEXTURE).read_bytes()
    if hashlib.sha256(payload).hexdigest() != APPROVED_SHA:
        raise ValueError('approved texture payload changed')
    source = (ui_upscale.DEFAULT_BUILD/'SYSTEM.DAT').read_bytes()
    if hashlib.sha256(source).hexdigest() != panel_redraw.SOURCE_SHA:
        raise ValueError('source build changed; revalidate before installing')
    name, native, meta = next(ui_upscale.pages(source, 'SYSTEM'))
    if name != panel_redraw.TEXTURE or meta['offset'] != 0xf50:
        raise ValueError('texture mapping changed')
    with Image.open(pack/'textures'/name) as image:
        if image.size != (1024,1024):
            raise ValueError('invalid replacement dimensions')
        high = np.array(image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM))
    low = np.array(native.resize((1024,1024), Image.Resampling.NEAREST))
    changed = np.any(high != low, axis=2)
    allowed = np.zeros((1024,1024), dtype=bool)
    allowed[:320,:384] = True
    if np.any(changed & ~allowed):
        raise ValueError('changes outside approved panel sprites')
    capture = ui_upscale.DUMPS/name
    if capture.exists():
        with Image.open(capture) as image:
            if image.convert('RGBA').tobytes() != native.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes():
                raise ValueError('captured native texture disagrees')
    return payload


def apply(payload, restore=False, target_dir=ui_upscale.TARGET):
    if hashlib.sha256(payload).hexdigest() != APPROVED_SHA:
        raise ValueError('unapproved payload')
    target_dir = Path(target_dir).resolve()
    target = target_dir/panel_redraw.TEXTURE
    if target.is_symlink() or target.resolve().parent != target_dir:
        raise ValueError('target redirects outside profile')
    present = target.read_bytes() if target.exists() else None
    if present is not None and present != payload:
        raise ValueError('existing user texture differs; will not overwrite it')
    changed = False
    if restore and present is not None:
        # Only this exact approved addition; the original slot was absent.
        # The generated PNG remains recoverable in PACK/textures.
        target.unlink()
        changed = True
    elif not restore and present is None:
        target_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        if target.read_bytes() != payload:
            raise ValueError('installed texture readback failed')
        changed = True
    return dict(action='restore' if restore else 'install', changed=changed,
                target=str(target), shared_panels=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('install','restore','verify'))
    args = parser.parse_args()
    payload = validate()
    result = ({'approved_payload_valid': True} if args.command == 'verify'
              else apply(payload, restore=args.command == 'restore'))
    print(json.dumps(result, indent=2))
