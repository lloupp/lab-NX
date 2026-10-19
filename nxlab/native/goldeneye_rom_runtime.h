#ifndef GOLDENEYE_ROM_RUNTIME_H
#define GOLDENEYE_ROM_RUNTIME_H
#include <stdint.h>
#include <stddef.h>
#define GE_ROM_EXPECTED_SIZE (12u * 1024u * 1024u)
#define GE_ROM_BASE_CRC32 0xB6330846u

typedef struct {
    uint8_t *bytes;
    size_t size;
    uint32_t crc32;
    int original_usa;
} ge_rom_image;

typedef enum {
    GE_ROM_OK = 0,
    GE_ROM_ERR_OPEN = -1,
    GE_ROM_ERR_SIZE = -2,
    GE_ROM_ERR_MEMORY = -3,
    GE_ROM_ERR_IO = -4,
    GE_ROM_ERR_HEADER = -5,
    GE_ROM_ERR_BOOTCODE = -6,
    GE_ROM_ERR_CHECKSUM = -7
} ge_rom_result;

/* Does not execute game code; loads + validates real user's GoldenEye ROM. */
ge_rom_result ge_rom_load(const char *path, ge_rom_image *out);
void ge_rom_unload(ge_rom_image *rom);
/* Validate a memory image, including the N64 CIC-6102 integrity header. */
ge_rom_result ge_rom_verify_bytes(const uint8_t *data, size_t size, uint32_t *crc32);
const char *ge_rom_status_name(ge_rom_result code);
#endif
