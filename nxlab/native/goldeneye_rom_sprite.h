#ifndef GOLDENEYE_ROM_SPRITE_H
#define GOLDENEYE_ROM_SPRITE_H
#include <stdint.h>
#include <stddef.h>
/* Actual GoldenEye USA Rareware logo tiles at known ROM offsets.
   No commercial pixel data is embedded. 64x64 composite is not a game frame. */
#define GE_RARE_LOGO_SEGMENT 0x29E560u
#define GE_RARE_LOGO_SIDE 64u
typedef struct { uint8_t r, g, b, a; } ge_rgba;
int ge_rom_rare_pixel(const uint8_t *rom, size_t length, int x, int y, ge_rgba *out);
#endif
