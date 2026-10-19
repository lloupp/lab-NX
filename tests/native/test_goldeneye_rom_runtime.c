#include "goldeneye_rom_runtime.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    ge_rom_image rom = {0};
    uint32_t checksum = 0;
    assert(ge_rom_verify_bytes(NULL, 0, &checksum) == GE_ROM_ERR_SIZE);
    if (argc != 2) {
        puts("synthetic C checks PASS; pass private unmodified .z64 to verify actual ROM");
        return 0;
    }
    assert(ge_rom_load(argv[1], &rom) == GE_ROM_OK);
    assert(rom.bytes && rom.size == GE_ROM_EXPECTED_SIZE && rom.original_usa);
    assert(rom.crc32 == GE_ROM_BASE_CRC32);
    rom.bytes[0x80] ^= 1u;
    assert(ge_rom_verify_bytes(rom.bytes, rom.size, &checksum) == GE_ROM_ERR_BOOTCODE);
    rom.bytes[0x80] ^= 1u;
    rom.bytes[0x1010] ^= 1u;
    assert(ge_rom_verify_bytes(rom.bytes, rom.size, &checksum) == GE_ROM_ERR_CHECKSUM);
    rom.bytes[0x1010] ^= 1u;
    assert(ge_rom_verify_bytes(rom.bytes, rom.size, &checksum) == GE_ROM_OK);
    ge_rom_unload(&rom);
    assert(rom.bytes == NULL && rom.size == 0);
    puts("GoldenEye real original ROM LOAD + header + checksum PASS");
    return 0;
}
