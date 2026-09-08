"""Install the HD texture-upload prototype into an isolated Flycast source copy.

Exact anchors fail closed on incompatible Flycast versions. Never targets the
user's original emulator tree. Font data is generated separately from compiling.
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Flycast anchor not unique: ' + old[:70])
    return text.replace(old, new, 1)


def external_pack_call(text):
    old = 'width, height, bmhd::Glyphs, unsigned(std::size(bmhd::Glyphs)), hdPixels);'
    new = 'width, height, bmhd::fontPack().glyphs.data(), unsigned(bmhd::fontPack().glyphs.size()), hdPixels);'
    if old in text:
        return once(text, old, new)
    if new in text and 'bmhd::Glyphs' not in text:
        return text
    raise ValueError('unrecognized HD hook; refusing upgrade')


def patch(source, upgrade=False):
    source = source.resolve()
    if not source.is_relative_to((ROOT / 'build').resolve()):
        raise ValueError('only an isolated source copy under this repository build/ is allowed')
    cpp = source / 'core/rend/TexCache.cpp'
    hdr = source / 'core/rend/TexCache.h'
    c, h = cpp.read_text(encoding='utf-8'), hdr.read_text(encoding='utf-8')
    dest = source / 'core/rend/blackmatrix-hd'
    if upgrade:
        if '#include "blackmatrix-hd/flycast_bridge_impl.h"' not in c or 'bmhd::candidate' not in h:
            raise ValueError('expected existing isolated HD prototype')
        c = external_pack_call(c)
        for name in ['atlas.h', 'font_pack.h', 'flycast_bridge.h', 'flycast_bridge_impl.h']:
            shutil.copy2(HERE / name, dest / name)
        cpp.write_text(c, encoding='utf-8')
        print('Upgraded isolated HD hook to external font packs:', source)
        return
    if 'bmhd::' in c or 'bmhd::' in h:
        raise ValueError('already patched; start with a fresh source copy')
    c = once(c, '#include "TexCache.h"',
             '#include "TexCache.h"\n#include "blackmatrix-hd/flycast_bridge_impl.h"')
    c = once(c, '\tgpuPalette = false;\n\ttex_type = tex->type;',
             '\tgpuPalette = false;\n\ttex_type = tex->type;\n'
             '\tconst bool hdCandidate = bmhd::candidate(tcw.PixelFmt, width, height, IsMipmapped(), tcw.VQ_Comp);')
    c = once(c, 'if (!textureUpscaling\n', 'if (!hdCandidate && !textureUpscaling\n')
    c = once(c, 'bool textureUpscaling = config::TextureUpscale > 1',
             'bool textureUpscaling = !hdCandidate && config::TextureUpscale > 1')
    c = once(c, '\t//lock the texture to detect changes in it', '''
	std::vector<uint32_t> hdPixels;
	if (hdCandidate && tex_type == TextureType::_8888 && !mipmapped && temp_tex_buffer) {
		unsigned matched = bmhd::replace(static_cast<const uint32_t*>(temp_tex_buffer),
			width, height, bmhd::fontPack().glyphs.data(), unsigned(bmhd::fontPack().glyphs.size()), hdPixels);
		if (matched) {
			temp_tex_buffer = hdPixels.data();
			upscaled_w = width * bmhd::Scale;
			upscaled_h = height * bmhd::Scale;
			NOTICE_LOG(RENDERER, "BMHD: replaced %u glyphs in %ux%u atlas", matched, width, height);
		}
	}
	//lock the texture to detect changes in it''')
    h = once(h, '#pragma once', '#pragma once\n#include "blackmatrix-hd/flycast_bridge.h"')
    h = once(h, 'return (tcw.PixelFmt == PixelPal4 || tcw.PixelFmt == PixelPal8)\n\t\t\t\t&& config::TextureUpscale',
             'return !bmhd::candidate(tcw.PixelFmt, 8u << tsp.TexU, 8u << tsp.TexV, tcw.MipMapped, tcw.VQ_Comp)\n'
             '\t\t\t\t&& (tcw.PixelFmt == PixelPal4 || tcw.PixelFmt == PixelPal8)\n\t\t\t\t&& config::TextureUpscale')
    dest.mkdir(exist_ok=True)
    for name in ['atlas.h', 'font_pack.h', 'flycast_bridge.h', 'flycast_bridge_impl.h']:
        shutil.copy2(HERE / name, dest / name)
    cpp.write_text(c, encoding='utf-8')
    hdr.write_text(h, encoding='utf-8')
    print('Installed opt-in T20101M HD glyph upload hook in', source)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--upgrade', action='store_true')
    args = parser.parse_args()
    patch(args.source, args.upgrade)
