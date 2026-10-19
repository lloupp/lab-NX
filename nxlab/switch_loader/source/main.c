/* Real GoldenEye ROM asset display on libnx framebuffer.
 * NOT a reconstructed GoldenEye frame, gameplay, Fast3D nor deko3d.
 * Original logo pixels are decoded at runtime from the user's local ROM.
 * No copyrighted game image is built into this NRO.
 */
#include <switch.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include "goldeneye_rom_runtime.h"
#include "goldeneye_rom_sprite.h"
#include "goldeneye_switch_libnx.h"

#define GE_ROM_PATH "sdmc:/switch/lab-nx/goldeneye/baserom.u.z64"
#define GE_PTBR_PATH "sdmc:/switch/lab-nx/goldeneye/ge007.ptbr.z64"
#define GE_TRACE_PATH "sdmc:/switch/lab-nx/goldeneye/eden_boot_trace.txt"
#define SCREEN_W 1280u
#define SCREEN_H 720u

/* Guest-side breadcrumbs: verify that ARM64 main() executes in Eden.
 * This writes only diagnostic strings to the user's SD, no commercial data.
 * A missing breadcrumb indicates that the guest stopped before this point
 * OR that sdmc is not mounted, and must not be treated as proof of execution.
 */
static void trace_boot(const char *stage) {
    FILE *fp;
    mkdir("sdmc:/switch", 0777);
    mkdir("sdmc:/switch/lab-nx", 0777);
    mkdir("sdmc:/switch/lab-nx/goldeneye", 0777);
    fp = fopen(GE_TRACE_PATH, "a");
    if (!fp) return;
    fprintf(fp, "%s\n", stage);
    fclose(fp);
}

static void draw_rom_logo(Framebuffer *fb, const ge_rom_image *rom,
                          int offset_x, int offset_y, unsigned scale) {
    u32 stride_bytes;
    u32 *pixels = (u32 *)framebufferBegin(fb, &stride_bytes);
    unsigned stride = stride_bytes / sizeof(u32);
    for (unsigned y = 0; y < SCREEN_H; ++y)
        for (unsigned x = 0; x < SCREEN_W; ++x)
            pixels[y * stride + x] = RGBA8_MAXALPHA(0, 0, 0);

    int ox = (int)((SCREEN_W - 64u * scale) / 2u) + offset_x;
    int oy = (int)((SCREEN_H - 64u * scale) / 2u) + offset_y;
    for (int y = 0; y < 64; ++y) {
        for (int x = 0; x < 64; ++x) {
            ge_rgba c;
            if (!ge_rom_rare_pixel(rom->bytes, rom->size, x, y, &c) || !c.a)
                continue;
            u32 pixel = RGBA8_MAXALPHA(c.r, c.g, c.b);
            int base_x = ox + x * (int)scale;
            int base_y = oy + y * (int)scale;
            for (unsigned dy = 0; dy < scale; ++dy) {
                int dest_y = base_y + (int)dy;
                if (dest_y < 0 || dest_y >= (int)SCREEN_H) continue;
                for (unsigned dx = 0; dx < scale; ++dx) {
                    int dest_x = base_x + (int)dx;
                    if (dest_x >= 0 && dest_x < (int)SCREEN_W)
                        pixels[(unsigned)dest_y * stride + (unsigned)dest_x] = pixel;
                }
            }
        }
    }
    framebufferEnd(fb);
}

/* ROM-free color bars verify libnx framebuffer submission on Eden.
 * TEST PATTERN, NOT a GoldenEye texture nor any game frame.
 */
static void draw_missing_rom_diagnostic(Framebuffer *fb) {
    u32 stride_bytes;
    u32 *pixels = (u32 *)framebufferBegin(fb, &stride_bytes);
    unsigned stride = stride_bytes / sizeof(u32);
    if (!pixels) return;
    for (unsigned y = 0; y < SCREEN_H; ++y) {
        for (unsigned x = 0; x < SCREEN_W; ++x) {
            u8 r = x < SCREEN_W / 3u ? 190u : 20u;
            u8 g = x >= SCREEN_W / 3u && x < SCREEN_W * 2u / 3u ? 190u : 20u;
            u8 b = x >= SCREEN_W * 2u / 3u ? 190u : 20u;
            /* horizontal status line makes the pattern easy to validate */
            if (y >= SCREEN_H / 2u - 5u && y < SCREEN_H / 2u + 5u) {
                r = 240u; g = 240u; b = 240u;
            }
            pixels[y * stride + x] = RGBA8_MAXALPHA(r, g, b);
        }
    }
    framebufferEnd(fb);
}

int main(int argc, char **argv) {
    ge_rom_image rom = {0};
    ge_input_state state = {0};
    ge_input_config config = ge_default_input_config();
    ge_pad_sample sample = {0};
    ge_input_actions actions = {0};
    ge_rom_result result;
    (void)argc; (void)argv;
    /* Eden direct-NRO launches may not have a pre-mounted SDMC device. */
    fsdevMountSdmc();
    trace_boot("main-entered");
    consoleInit(NULL);
    trace_boot("console-init-ok");
    ge_switch_pad_init();
    trace_boot("hid-init-ok");
    result = ge_rom_load(GE_PTBR_PATH, &rom);
    if (result != GE_ROM_OK)
        result = ge_rom_load(GE_ROM_PATH, &rom);
    if (result != GE_ROM_OK) {
        trace_boot("rom-load-failed");
        printf("ROM ausente/invalida: %s.\n", ge_rom_status_name(result));
        printf("Imagem seguinte e apenas PADRAO DIAGNOSTICO.\n");
        consoleUpdate(NULL);
        consoleExit(NULL);
        Framebuffer diagnostic_fb;
        framebufferCreate(&diagnostic_fb, nwindowGetDefault(),
                          SCREEN_W, SCREEN_H, PIXEL_FORMAT_RGBA_8888, 2);
        framebufferMakeLinear(&diagnostic_fb);
        trace_boot("error-framebuffer-init-attempted");
        int submitted = 0;
        while (appletMainLoop()) {
            if (ge_switch_pad_poll(&sample) != 0) break;
            if (sample.buttons & GE_BTN_PLUS) break;
            draw_missing_rom_diagnostic(&diagnostic_fb);
            if (!submitted++) trace_boot("error-diagnostic-frame-submitted");
        }
        framebufferClose(&diagnostic_fb);
        return 1;
    }
    trace_boot("rom-load-success");
    printf("ROM validada. Desenhando sprite original Rareware.\n");
    printf("Isto NAO e gameplay nem um frame do motor do jogo.\n");
    consoleUpdate(NULL);
    consoleExit(NULL);
    trace_boot("console-exit");
    NWindow *window = nwindowGetDefault();
    Framebuffer fb;
    framebufferCreate(&fb, window, SCREEN_W, SCREEN_H, PIXEL_FORMAT_RGBA_8888, 2);
    framebufferMakeLinear(&fb);
    trace_boot("framebuffer-ready");
    int pan_x = 0, pan_y = 0;
    while (appletMainLoop()) {
        if (ge_switch_pad_poll(&sample) != 0) break;
        if (ge_map_input(&state, &config, &sample, &actions) != 0) break;
        if (actions.pause_pressed) break;
        pan_x += (int)(actions.move_x * 4.f);
        pan_y -= (int)(actions.move_y * 4.f);
        if (pan_x > 450) pan_x = 450;
        if (pan_x < -450) pan_x = -450;
        if (pan_y > 250) pan_y = 250;
        if (pan_y < -250) pan_y = -250;
        draw_rom_logo(&fb, &rom, pan_x, pan_y, actions.aim_held ? 8u : 6u);
        if (pan_x == 0 && pan_y == 0 && !actions.aim_held) {
            static int frame_marker = 0;
            if (!frame_marker++) trace_boot("first-rom-sprite-frame-submitted");
        }
    }
    framebufferClose(&fb);
    ge_rom_unload(&rom);
    return 0;
}
