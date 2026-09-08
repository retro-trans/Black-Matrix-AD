// Replay a locally captured texture through the EXACT runtime matcher.
// Input: width/height as two little-endian uint32 values, then RGBA pixels.
// Output: the same header+pixel format at 4x resolution. Generated files only.
#include "atlas.h"
#include "font_pack.h"
#include <fstream>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 3 && argc != 4) return 2;
    std::ifstream packFile(argc == 4 ? argv[3] : "build/hd-ui/black-matrix-hd-font.bin", std::ios::binary);
    auto pack = bmhd::loadFontPack(packFile);
    if (pack.glyphs.empty()) { std::cerr << pack.error << '\n'; return 7; }
    std::ifstream in(argv[1], std::ios::binary);
    uint32_t w = 0, h = 0;
    in.read(reinterpret_cast<char*>(&w), 4);
    in.read(reinterpret_cast<char*>(&h), 4);
    if (!in || w != h || (w != 32 && w != 64 && w != 128 && w != 256)) return 3;
    std::vector<uint32_t> source(w*h), result;
    in.read(reinterpret_cast<char*>(source.data()), source.size()*4);
    if (!in) return 4;
    unsigned matches = bmhd::replace(source.data(), w, h, pack.glyphs.data(),
                                    unsigned(pack.glyphs.size()), result);
    if (!matches) { std::cerr << "No glyphs matched\n"; return 5; }
    std::ofstream out(argv[2], std::ios::binary);
    w *= bmhd::Scale; h *= bmhd::Scale;
    out.write(reinterpret_cast<char*>(&w), 4);
    out.write(reinterpret_cast<char*>(&h), 4);
    out.write(reinterpret_cast<char*>(result.data()), result.size()*4);
    if (!out) return 6;
    std::cout << "Replaced " << matches << " captured glyphs -> " << w << 'x' << h << '\n';
}
