#include "goldeneye_rom_sprite.h"
/* GoldenEye US rarewarelogo.bin, four 32x32 RGBA5551 mipmapped tiles.
   Layout verified against upstream assets/rarewarelogo.c and user's ROM. */
int ge_rom_rare_pixel(const uint8_t *rom, size_t length, int x, int y, ge_rgba *out) {
    static const size_t tile_offsets[4] = {0x20, 0x0AE0, 0x15A0, 0x2060};
    size_t pos;
    unsigned tile, word;
    if (!rom || !out || x < 0 || y < 0 || x >= 64 || y >= 64) return 0;
    tile = (unsigned)(y / 32) * 2u + (unsigned)(x / 32);
    pos = GE_RARE_LOGO_SEGMENT + tile_offsets[tile] +
        (((unsigned)y % 32u) * 32u + (unsigned)x % 32u) * 2u;
    if (pos + 2 > length) return 0;
    word = ((unsigned)rom[pos] << 8) | rom[pos + 1];
    out->r = (uint8_t)(((word >> 11) & 31u) * 255u / 31u);
    out->g = (uint8_t)(((word >> 6) & 31u) * 255u / 31u);
    out->b = (uint8_t)(((word >> 1) & 31u) * 255u / 31u);
    out->a = (uint8_t)((word & 1u) ? 255u : 0u);
    return 1;
}
