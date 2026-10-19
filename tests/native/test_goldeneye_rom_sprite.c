#include "goldeneye_rom_sprite.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    ge_rgba pixel;
    uint8_t *rom = calloc(GE_RARE_LOGO_SEGMENT + 0x2860 + 2, 1);
    size_t len = GE_RARE_LOGO_SEGMENT + 0x2860 + 2;
    assert(rom);
    assert(!ge_rom_rare_pixel(NULL, len, 0, 0, &pixel));
    assert(!ge_rom_rare_pixel(rom, len, 64, 0, &pixel));
    assert(!ge_rom_rare_pixel(rom, len, 0, -1, &pixel));
    assert(!ge_rom_rare_pixel(rom, len, 0, 0, NULL));
    assert(!ge_rom_rare_pixel(rom, 100, 0, 0, &pixel));
    rom[GE_RARE_LOGO_SEGMENT + 0xae0] = 0xff;
    rom[GE_RARE_LOGO_SEGMENT + 0xae1] = 0xff;
    assert(ge_rom_rare_pixel(rom, len, 32, 0, &pixel));
    assert(pixel.r == 255 && pixel.g == 255 && pixel.b == 255 && pixel.a == 255);
    assert(ge_rom_rare_pixel(rom, len, 0, 32, &pixel));
    assert(pixel.a == 0);
    if (argc == 2) {
        FILE *f = fopen(argv[1], "rb");
        assert(f);
        size_t got = fread(rom, 1, len, f);
        fclose(f);
        assert(got == len);
        assert(ge_rom_rare_pixel(rom, got, 0, 1, &pixel));
        assert(pixel.a == 255);
        puts("Original ROM Rare logo pixels decoded: PASS");
    } else puts("Synthetic RGBA5551 tests: PASS");
    free(rom);
    return 0;
}
