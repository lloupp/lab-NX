/* GoldenEye real ROM preload + physical Switch HID bridge.
 * This is infrastructure, NOT a GoldenEye game engine or playable port.
 * Compiles to an actual homebrew NRO using devkitA64/libnx. */
#include <switch.h>
#include <stdio.h>
#include <string.h>
#include "goldeneye_rom_runtime.h"
#include "goldeneye_switch_libnx.h"

#define GE_ROM_PATH "sdmc:/switch/lab-nx/goldeneye/baserom.u.z64"
#define GE_TRANSLATED_ROM_PATH "sdmc:/switch/lab-nx/goldeneye/ge007.ptbr.z64"

int main(int argc, char **argv) {
    ge_rom_image rom = {0};
    ge_input_state state = {0};
    ge_input_config config = ge_default_input_config();
    ge_pad_sample sample = {0};
    ge_input_actions gamepad = {0};
    ge_rom_result result;
    unsigned frame = 0;
    (void)argc; (void)argv;
    consoleInit(NULL);
    ge_switch_pad_init();
    result = ge_rom_load(GE_TRANSLATED_ROM_PATH, &rom);
    if (result != GE_ROM_OK)
        result = ge_rom_load(GE_ROM_PATH, &rom);
    printf("lab-NX: GoldenEye ROM/INPUT stage\n");
    printf("NAO e uma compilacao do jogo.\n\n");
    if (result == GE_ROM_OK) {
        printf("ROM US valida: %lu bytes\n", (unsigned long)rom.size);
        printf("CRC32: %08lX (%s)\n", (unsigned long)rom.crc32,
               rom.original_usa ? "original" : "modificada/patch");
        printf("Buffer da ROM alocado em RAM.\n");
    } else {
        printf("Falha ROM: %s\n", ge_rom_status_name(result));
        printf("Copie sua ROM .z64 para:\n%s\n", GE_ROM_PATH);
    }
    printf("\nControle: LX/LY movimento, RX/RY mira\n");
    printf("ZL mira, ZR dispara, + encerra este teste\n\n");
    consoleUpdate(NULL);
    while (appletMainLoop()) {
        if (ge_switch_pad_poll(&sample) != 0) break;
        if (ge_map_input(&state, &config, &sample, &gamepad) != 0) break;
        if (gamepad.pause_pressed) break;
        if (++frame % 15 == 0) {
            printf("\rLX:%+.2f LY:%+.2f RX:%+.2f RY:%+.2f aim:%d fire:%d   ",
                   (double)gamepad.move_x, (double)gamepad.move_y,
                   (double)gamepad.look_x, (double)gamepad.look_y,
                   gamepad.aim_held, gamepad.fire_held);
            consoleUpdate(NULL);
        }
    }
    ge_rom_unload(&rom);
    consoleExit(NULL);
    return 0;
}
