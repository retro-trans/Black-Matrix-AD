// Emulator-only HD glyph replacement. No emulated RAM/VRAM writes.
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <array>
#include <cstdint>
#include <vector>

namespace bmhd {
constexpr unsigned Scale = 4;
constexpr unsigned CellW = 32, CellH = 16;
struct Glyph {
    std::array<uint32_t, CellH> rows;
    std::array<uint8_t, CellW * CellH * Scale * Scale> alpha;
};

// Interpolate coverage in premultiplied space, returning straight-alpha pixels.
// Opaque black backgrounds stay opaque for additive-blended text; transparent
// backgrounds keep the ink RGB to avoid dark fringes under alpha blending.
inline uint32_t coveragePixel(uint32_t background, uint32_t ink, unsigned c) {
    const unsigned ia = ink >> 24, ba = background >> 24;
    const unsigned weight = ia*c + ba*(255-c);
    uint32_t result = ((weight+127)/255) << 24;
    for (unsigned shift = 0; shift < 24; shift += 8) {
        unsigned channel = (ink >> shift) & 255;
        if (weight)
            channel = (channel*ia*c + ((background >> shift)&255)*ba*(255-c)
                       + weight/2) / weight;
        result |= channel << shift;
    }
    return result;
}

// Exact bitmap recognition, not OCR. Unknown cells keep every original pixel.
// Pixel words may be RGBA or BGRA: alpha is the high byte in both Flycast paths.
inline unsigned replace(const uint32_t* source, unsigned width, unsigned height,
                        const Glyph* glyphs, unsigned count,
                        std::vector<uint32_t>& output) {
    if (!source || !glyphs || !count || width != height ||
        (width != 32 && width != 64 && width != 128 && width != 256)) return 0;
    struct Match { unsigned x, y, glyph; uint32_t color, background; };
    std::vector<Match> matches;
    for (unsigned y0 = 0; y0 < height; y0 += CellH) {
        for (unsigned x0 = 0; x0 < width; x0 += CellW) {
            std::array<uint32_t, CellH> rows{};
            // The unused rightmost column is background in every source glyph.
            const uint32_t background = source[y0*width+x0+CellW-1];
            uint32_t color = 0;
            bool uniform = true, ink = false;
            for (unsigned y = 0; y < CellH; ++y)
                for (unsigned x = 0; x < CellW; ++x) {
                    uint32_t pixel = source[(y0+y)*width+x0+x];
                    const bool sameBackground = pixel == background ||
                        (!(pixel >> 24) && !(background >> 24));
                    if (!sameBackground) {
                        rows[y] |= uint32_t(1) << x;
                        if (ink && pixel != color) uniform = false;
                        color = pixel;
                        ink = true;
                    }
                }
            if (!ink || !uniform) continue;
            for (unsigned i = 0; i < count; ++i)
                if (rows == glyphs[i].rows) {
                    matches.push_back({x0, y0, i, color, background});
                    break;
                }
        }
    }
    if (matches.empty()) return 0; // Leave output and original upload untouched.
    output.resize(width * height * Scale * Scale);
    for (unsigned y = 0; y < height * Scale; ++y)
        for (unsigned x = 0; x < width * Scale; ++x)
            output[y*width*Scale+x] = source[(y/Scale)*width+x/Scale];
    for (const auto& match : matches)
        for (unsigned y = 0; y < CellH*Scale; ++y)
            for (unsigned x = 0; x < CellW*Scale; ++x) {
                unsigned a = glyphs[match.glyph].alpha[y*CellW*Scale+x];
                output[(match.y*Scale+y)*width*Scale+match.x*Scale+x] =
                    coveragePixel(match.background, match.color, a);
            }
    return unsigned(matches.size());
}
} // namespace bmhd
