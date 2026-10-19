#include "goldeneye_rom_runtime.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t read_be32(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | bytes[3];
}

static uint32_t crc32_ieee(const uint8_t *data, size_t length) {
    uint32_t crc = ~0u;
    size_t i;
    for (i = 0; i < length; ++i) {
        unsigned b;
        crc ^= data[i];
        for (b = 0; b < 8; ++b)
            crc = (crc >> 1) ^ ((0u - (crc & 1u)) & 0xedb88320u);
    }
    return ~crc;
}

static void n64_crc6102(const uint8_t *data, uint32_t *c1, uint32_t *c2) {
    uint32_t t1 = 0xf8ca4ddcu, t2 = t1, t3 = t1, t4 = t1, t5 = t1, t6 = t1;
    size_t i;
    for (i = 0x1000; i < 0x101000; i += 4) {
        uint32_t d = read_be32(data + i);
        uint32_t r = (d << (d & 31u)) | (d >> ((32u - (d & 31u)) & 31u));
        uint32_t old_t6 = t6;
        t6 += d;
        if (t6 < old_t6) ++t4;
        t3 ^= d;
        t5 += r;
        if (t2 > d) t2 ^= r;
        else t2 ^= t6 ^ d;
        t1 += t5 ^ d;
    }
    *c1 = t6 ^ t4 ^ t3;
    *c2 = t5 ^ t2 ^ t1;
}

ge_rom_result ge_rom_verify_bytes(const uint8_t *data, size_t size, uint32_t *crc32) {
    uint32_t crc1, crc2;
    if (!data || size != GE_ROM_EXPECTED_SIZE) return GE_ROM_ERR_SIZE;
    if (read_be32(data) != 0x80371240u ||
        memcmp(data + 0x20, "GOLDENEYE", 9) != 0 ||
        memcmp(data + 0x3c, "GE", 2) != 0 || data[0x3e] != 'E')
        return GE_ROM_ERR_HEADER;
    if (crc32_ieee(data + 0x40, 0xfc0) != 0x90bb6cb5u)
        return GE_ROM_ERR_BOOTCODE;
    n64_crc6102(data, &crc1, &crc2);
    if (read_be32(data + 0x10) != crc1 || read_be32(data + 0x14) != crc2)
        return GE_ROM_ERR_CHECKSUM;
    if (crc32) *crc32 = crc32_ieee(data, size);
    return GE_ROM_OK;
}

ge_rom_result ge_rom_load(const char *path, ge_rom_image *out) {
    FILE *f;
    long size;
    uint8_t *memory;
    uint32_t crc;
    ge_rom_result result;
    if (!path || !out || !*path) return GE_ROM_ERR_OPEN;
    memset(out, 0, sizeof(*out));
    f = fopen(path, "rb");
    if (!f) return GE_ROM_ERR_OPEN;
    if (fseek(f, 0, SEEK_END) || (size = ftell(f)) != (long)GE_ROM_EXPECTED_SIZE ||
        fseek(f, 0, SEEK_SET)) {
        fclose(f);
        return GE_ROM_ERR_SIZE;
    }
    memory = (uint8_t *)malloc(GE_ROM_EXPECTED_SIZE);
    if (!memory) { fclose(f); return GE_ROM_ERR_MEMORY; }
    if (fread(memory, 1, GE_ROM_EXPECTED_SIZE, f) != GE_ROM_EXPECTED_SIZE || fgetc(f) != EOF) {
        fclose(f);
        free(memory);
        return GE_ROM_ERR_IO;
    }
    fclose(f);
    result = ge_rom_verify_bytes(memory, GE_ROM_EXPECTED_SIZE, &crc);
    if (result != GE_ROM_OK) { free(memory); return result; }
    out->bytes = memory;
    out->size = GE_ROM_EXPECTED_SIZE;
    out->crc32 = crc;
    out->original_usa = crc == GE_ROM_BASE_CRC32;
    return GE_ROM_OK;
}

void ge_rom_unload(ge_rom_image *rom) {
    if (!rom) return;
    free(rom->bytes);
    memset(rom, 0, sizeof(*rom));
}

const char *ge_rom_status_name(ge_rom_result code) {
    switch (code) {
    case GE_ROM_OK: return "ok";
    case GE_ROM_ERR_OPEN: return "open_failed";
    case GE_ROM_ERR_SIZE: return "invalid_size";
    case GE_ROM_ERR_MEMORY: return "out_of_memory";
    case GE_ROM_ERR_IO: return "read_failed";
    case GE_ROM_ERR_HEADER: return "invalid_goldeneye_header";
    case GE_ROM_ERR_BOOTCODE: return "unexpected_cic";
    case GE_ROM_ERR_CHECKSUM: return "invalid_n64_checksum";
    default: return "unknown";
    }
}
