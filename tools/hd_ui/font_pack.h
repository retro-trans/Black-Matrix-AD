// External HD font format and bounded, fail-closed loader.
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "atlas.h"
#include <cstring>
#include <istream>
#include <string>

namespace bmhd {
constexpr unsigned PackHeaderSize = 60;
constexpr unsigned PackRecordSize = CellH*4 + CellW*CellH*Scale*Scale;
constexpr unsigned MaxPackGlyphs = 256;
struct FontPack {
    std::vector<Glyph> glyphs;
    std::string error;
};
inline uint32_t readLE32(const uint8_t* p) {
    return uint32_t(p[0]) | uint32_t(p[1])<<8 | uint32_t(p[2])<<16 | uint32_t(p[3])<<24;
}
inline uint32_t packCRC(const uint8_t* p, size_t size) {
    uint32_t crc = 0xffffffffu;
    for (size_t i=0; i<size; ++i) {
        crc ^= p[i];
        for (unsigned j=0; j<8; ++j)
            crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320u : 0u);
    }
    return ~crc;
}
inline FontPack loadFontPack(std::istream& input) {
    std::array<uint8_t, PackHeaderSize> header{};
    if (!input.read(reinterpret_cast<char*>(header.data()), header.size()))
        return {{}, "missing or truncated header"};
    if (std::memcmp(header.data(), "BMHDFNT\0", 8) || readLE32(header.data()+8) != 1)
        return {{}, "unsupported font format/version"};
    const unsigned count = readLE32(header.data()+16);
    if (readLE32(header.data()+12) != Scale || !count || count > MaxPackGlyphs ||
        readLE32(header.data()+20) != PackRecordSize)
        return {{}, "invalid scale, glyph count or record size"};
    std::vector<uint8_t> bytes(count*PackRecordSize);
    if (!input.read(reinterpret_cast<char*>(bytes.data()), bytes.size()))
        return {{}, "truncated glyph data"};
    if (input.peek() != std::char_traits<char>::eof())
        return {{}, "unexpected trailing data"};
    if (packCRC(bytes.data(), bytes.size()) != readLE32(header.data()+56))
        return {{}, "glyph checksum mismatch"};
    FontPack pack;
    pack.glyphs.resize(count);
    for (unsigned i=0; i<count; ++i) {
        const uint8_t* p = bytes.data()+i*PackRecordSize;
        uint32_t ink = 0;
        for (unsigned y=0; y<CellH; ++y) {
            uint32_t row = readLE32(p+y*4);
            if (row & 0xff000000u) return {{}, "ink outside 24-pixel glyph bounds"};
            pack.glyphs[i].rows[y] = row;
            ink |= row;
        }
        if (!ink) return {{}, "empty glyph mask"};
        for (unsigned j=0; j<i; ++j)
            if (pack.glyphs[j].rows == pack.glyphs[i].rows)
                return {{}, "duplicate glyph mask"};
        std::memcpy(pack.glyphs[i].alpha.data(), p+CellH*4, pack.glyphs[i].alpha.size());
    }
    return pack;
}
} // namespace bmhd
