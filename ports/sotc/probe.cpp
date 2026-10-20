#include "iso_disc.h"
#include <array>
#include <cstdio>
#include <cstring>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: sotc-iso-probe <private-USA-disc.iso>\n";
        return 2;
    }
    sotc::IsoDisc disc;
    std::string error;
    if (!disc.open(argv[1], &error)) {
        std::cerr << "ISO open failed: " << error << "\n";
        return 1;
    }
    const char* required[] = {"SCUS_974.72", "KERNEL.XFF", "MANAGER.XFF", "GAMECORE.XFF", "NICO.DAT"};
    for (auto name : required) {
        const auto bytes = disc.fileSize(name);
        if (!bytes || !*bytes) {
            std::cerr << "Missing game component: " << name << "\n";
            return 1;
        }
        std::cout << name << ": " << *bytes << " bytes\n";
    }
    std::array<unsigned char, 52> head{};
    if (disc.read("cdrom0:\\SCUS_974.72;1", 0, head.data(), head.size()) != head.size() ||
        std::memcmp(head.data(), "\x7f" "ELF", 4) || head[4] != 1 || head[5] != 1 ||
        head[18] != 8 || head[19] != 0) {
        std::cerr << "Incorrect 32-bit MIPS boot ELF\n";
        return 1;
    }
    // Reads the FINAL byte of the 2.67 GB original data file without allocating it.
    const uint64_t nico_size = *disc.fileSize("NICO.DAT");
    unsigned char tail = 0;
    if (disc.read("NICO.DAT", nico_size - 1, &tail, 1) != 1 ||
        disc.read("NICO.DAT", nico_size, &tail, 1) != 0) {
        std::cerr << "Large-file seek or end-of-file failed\n";
        return 1;
    }
    std::cout << "PASS: original ISO streams beyond 2 GiB; "
              << disc.indexedFiles() << " entries indexed; no game bytes emitted\n";
    return 0;
}
