// Run with the compiler command in docs/emulator-hd-ui.md.
#include "../tools/hd_ui/atlas.h"
#include "../tools/hd_ui/font_pack.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <sstream>

int main() {
    std::ifstream packFile("build/hd-ui/black-matrix-hd-font.bin", std::ios::binary);
    std::string bytes((std::istreambuf_iterator<char>(packFile)), {});
    std::istringstream good(bytes);
    auto pack = bmhd::loadFontPack(good);
    assert(!pack.glyphs.empty() && pack.error.empty());
    const auto* Glyphs = pack.glyphs.data();
    const unsigned GlyphCount = unsigned(pack.glyphs.size());
    for (size_t cut : {size_t(0), size_t(59), size_t(60), bytes.size()-1}) {
        std::istringstream truncated(bytes.substr(0, cut));
        auto bad = bmhd::loadFontPack(truncated);
        assert(bad.glyphs.empty() && !bad.error.empty());
    }
    for (size_t byte : {size_t(0), size_t(8), size_t(12), size_t(16), size_t(17), size_t(20), size_t(56), bytes.size()-1}) {
        auto changed = bytes;
        changed[byte] ^= char(0xff);
        std::istringstream corrupt(changed);
        assert(bmhd::loadFontPack(corrupt).glyphs.empty());
    }
    std::istringstream trailing(bytes + "x");
    assert(bmhd::loadFontPack(trailing).glyphs.empty());
    std::vector<uint32_t> original(32*32), output;
    constexpr uint32_t Ink = 0x80a1b2c3; // Semi-transparent, asymmetric channels.
    for (const auto& glyph : pack.glyphs) {
        std::fill(original.begin(), original.end(), 0u);
        for (unsigned y = 0; y < 16; ++y)
            for (unsigned x = 0; x < 32; ++x)
                if (glyph.rows[y] & (uint32_t(1) << x)) original[y*32+x] = Ink;
        // An unknown cell must stay exactly nearest-neighbor, including alpha.
        for (unsigned y = 16; y < 32; ++y)
            for (unsigned x = 0; x < 32; ++x)
                original[y*32+x] = (x+y)%2 ? 0xff102030 : 0x55445566;
        auto copy = original;
        assert(bmhd::replace(original.data(), 32, 32, Glyphs, GlyphCount, output) == 1);
        assert(original == copy);
        assert(output.size() == 128*128);
        for (unsigned y = 0; y < 64; ++y)
            for (unsigned x = 0; x < 128; ++x) {
                uint32_t px = output[y*128+x];
                assert((px & 0xffffff) == (Ink & 0xffffff));
                assert((px >> 24) == (glyph.alpha[y*128+x]*128u+127)/255);
            }
        for (unsigned y = 64; y < 128; ++y)
            for (unsigned x = 0; x < 128; ++x)
                assert(output[y*128+x] == original[(y/4)*32+x/4]);
    }
    auto oldOutput = output;
    assert(bmhd::replace(nullptr, 32, 32, Glyphs, 1, output) == 0);
    assert(bmhd::replace(original.data(), 31, 32, Glyphs, 1, output) == 0);
    std::fill(original.begin(), original.end(), 0u);
    assert(bmhd::replace(original.data(), 32, 32, Glyphs, 1, output) == 0);
    assert(output == oldOutput);
    // Additively blended text can have an opaque black background. Alpha alone
    // does not identify its ink. This used to leave the entire text bitmap old.
    const auto& opaqueGlyph = Glyphs[0];
    std::fill(original.begin(), original.end(), 0xff000000u);
    for (unsigned y = 0; y < 16; ++y)
        for (unsigned x = 0; x < 32; ++x)
            if (opaqueGlyph.rows[y] & (uint32_t(1) << x)) original[y*32+x] = 0xffffffffu;
    if (bmhd::replace(original.data(), 32, 32, Glyphs, 1, output) != 1) {
        std::cerr << "FAIL: opaque-background glyph was not replaced\n";
        return 1;
    }
    for (unsigned y = 0; y < 64; ++y)
        for (unsigned x = 0; x < 128; ++x) {
            unsigned coverage = opaqueGlyph.alpha[y*128+x];
            assert(output[y*128+x] == (0xff000000u | coverage*0x010101u));
        }
    // An otherwise matching cell with multiple ink colors must not be replaced.
    const auto& glyph = Glyphs[0];
    unsigned n = 0;
    for (unsigned y = 0; y < 16; ++y)
        for (unsigned x = 0; x < 32; ++x)
            if (glyph.rows[y] & (uint32_t(1) << x))
                original[y*32+x] = (++n % 2) ? Ink : Ink+1;
    assert(bmhd::replace(original.data(), 32, 32, Glyphs, 1, output) == 0);
    std::cout << "HD atlas: all " << GlyphCount
              << " glyphs, alpha/color, unknown cells and no-op guards passed\n";
    for (unsigned size : {32u, 64u, 128u, 256u}) {
        std::vector<uint32_t> atlas(size*size, 0);
        for (unsigned y0 = 0; y0 < size; y0 += 16)
            for (unsigned x0 = 0; x0 < size; x0 += 32)
                for (unsigned y = 0; y < 16; ++y)
                    for (unsigned x = 0; x < 32; ++x)
                        if (glyph.rows[y] & (uint32_t(1) << x))
                            atlas[(y0+y)*size+x0+x] = Ink;
        assert(bmhd::replace(atlas.data(), size, size, Glyphs, 1, output)
               == size*size/(32*16));
        assert(output.size() == size*size*16);
    }
    std::cout << "All supported atlas sizes, including 256x256 help, passed\n";
    std::cout << "External pack validation: malformed, truncated, oversized/corrupt and trailing data rejected\n";
}
