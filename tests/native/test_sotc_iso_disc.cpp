// Synthetic fixture only: no original game assets in source control.
#include "iso_disc.h"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace {
constexpr size_t kSector = 2048;
void set32(uint8_t* p, uint32_t v) {
    p[0] = v & 255; p[1] = (v >> 8) & 255;
    p[2] = (v >> 16) & 255; p[3] = (v >> 24) & 255;
    p[4] = (v >> 24) & 255; p[5] = (v >> 16) & 255;
    p[6] = (v >> 8) & 255; p[7] = v & 255;
}
std::vector<uint8_t> rec(const std::string& name, uint32_t lba,
                         uint32_t length, bool dir = false) {
    const size_t n = 33 + name.size();
    std::vector<uint8_t> out(n + n % 2);
    out[0] = static_cast<uint8_t>(out.size());
    set32(out.data() + 2, lba);
    set32(out.data() + 10, length);
    out[25] = dir ? 2 : 0;
    out[28] = 1; out[31] = 1;
    out[32] = static_cast<uint8_t>(name.size());
    std::memcpy(out.data() + 33, name.data(), name.size());
    return out;
}
void push(std::vector<uint8_t>& image, size_t& dest,
          const std::vector<uint8_t>& bytes) {
    std::memcpy(image.data() + dest, bytes.data(), bytes.size());
    dest += bytes.size();
}
std::vector<uint8_t> fixture() {
    std::vector<uint8_t> iso(32 * kSector);
    size_t pvd = 16 * kSector;
    iso[pvd] = 1;
    std::memcpy(iso.data() + pvd + 1, "CD001", 5);
    iso[pvd + 6] = 1;
    auto root = rec(std::string(1, '\0'), 20, 2048, true);
    std::memcpy(iso.data() + pvd + 156, root.data(), root.size());
    auto dot = rec(std::string(1, '\0'), 20, 2048, true);
    auto dotdot = rec(std::string(1, '\1'), 20, 2048, true);
    size_t pos = 20 * kSector;
    push(iso, pos, dot);
    push(iso, pos, dotdot);
    push(iso, pos, rec("SCUS_974.72;1", 21, 80));
    push(iso, pos, rec("NICO.DAT;1", 22, 5));
    push(iso, pos, rec("FOLDER", 23, 2048, true));
    pos = 23 * kSector;
    push(iso, pos, rec(std::string(1, '\0'), 23, 2048, true));
    push(iso, pos, rec(std::string(1, '\1'), 20, 2048, true));
    push(iso, pos, rec("DATA.BIN;1", 24, 4));
    std::memcpy(iso.data() + 21 * kSector, "\x7f" "ELF", 4);
    std::memcpy(iso.data() + 22 * kSector, "ABCDE", 5);
    std::memcpy(iso.data() + 24 * kSector, "TEST", 4);
    return iso;
}
void save(const std::filesystem::path& p, const std::vector<uint8_t>& bytes) {
    std::ofstream out(p, std::ios::binary | std::ios::trunc);
    out.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
    assert(out.good());
}
}
int main() {
    const auto file = std::filesystem::temp_directory_path() / "sotc_bridge_synthetic_fixture.iso";
    try {
        auto iso = fixture();
        save(file, iso);
        sotc::IsoDisc reader;
        std::string error;
        assert(reader.open(file.string(), &error));
        assert(reader.indexedFiles() == 4);
        assert(reader.contains("cdrom0:\\scus_974.72;1"));
        assert(reader.contains("folder/data.bin"));
        assert(reader.fileSize("NICO.DAT") == 5);
        assert(!reader.contains("cdrom0:\\../NICO.DAT"));
        assert(!reader.contains("sdmc:/fake"));
        assert(!reader.fileSize("does-not-exist"));
        std::array<char, 8> buf{};
        assert(reader.read("NICO.DAT", 3, buf.data(), 8) == 2);
        assert(std::string(buf.data(), 2) == "DE");
        assert(reader.read("NICO.DAT", 5, buf.data(), 1) == 0);
        assert(reader.read("NICO.DAT", 0, nullptr, 1) == std::nullopt);
        assert(reader.read("folder/data.bin", 0, buf.data(), 4) == 4);
        assert(std::string(buf.data(), 4) == "TEST");
        // Malformed primary descriptor must fail closed.
        iso[16 * kSector + 1] = 'X';
        save(file, iso);
        assert(!reader.open(file.string(), &error));
        // Out-of-bounds file extent must fail, not seek outside the ISO.
        iso = fixture();
        // Locate a directory entry and deliberately corrupt its extent LBA.
        size_t off = 20 * kSector;
        off += rec(std::string(1, '\0'), 20, 2048, true).size();
        off += rec(std::string(1, '\1'), 20, 2048, true).size();
        set32(iso.data() + off + 2, 1000000);
        save(file, iso);
        assert(!reader.open(file.string(), &error));
        std::filesystem::remove(file);
        std::cout << "PASS: ISO streaming, nested directory, EOF, path protection, malformed extents\n";
        return 0;
    } catch (...) { std::filesystem::remove(file); throw; }
}
