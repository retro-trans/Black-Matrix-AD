// Included once by TexCache.cpp. SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "atlas.h"
#include "font_pack.h"
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>

namespace bmhd {
const FontPack& fontPack() {
    // Loaded once per process, with thread-safe C++ static initialization.
    // Restart after replacing the data file; never mutate a live texture cache.
    static const FontPack pack = [] {
        const char* configured = std::getenv("BLACK_MATRIX_HD_DATA");
        const char* path = configured ? configured : "data/black-matrix-hd-font.bin";
        std::ifstream input(std::filesystem::u8path(path), std::ios::binary);
        FontPack loaded = loadFontPack(input);
        if (loaded.glyphs.empty())
            WARN_LOG(RENDERER, "BMHD: external font unavailable (%s). Using original textures.", loaded.error.c_str());
        else
            NOTICE_LOG(RENDERER, "BMHD: loaded %u external glyphs from %s", unsigned(loaded.glyphs.size()), path);
        return loaded;
    }();
    return pack;
}
bool candidate(unsigned pixelFormat, unsigned width, unsigned height,
               bool mipmapped, bool compressed) {
    const char* opt = std::getenv("BLACK_MATRIX_HD_FONT");
    return opt && std::strcmp(opt, "1") == 0 &&
        settings.content.gameId == "T20101M" && pixelFormat == PixelPal4 &&
        !mipmapped && !compressed && width == height &&
        (width == 32 || width == 64 || width == 128 || width == 256) &&
        !fontPack().glyphs.empty();
}
} // namespace bmhd
