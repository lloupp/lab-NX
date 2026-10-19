/* Optional hardware adapter; compile with devkitA64/libnx.
 * Reading HID does not itself mean the game engine consumes the actions. */
#ifdef __SWITCH__
#include <switch.h>
#include "goldeneye_switch_input.h"

static PadState ge_pad;
static float axis(s32 value) {
    float v = (float)value / 32767.f;
    return v > 1.f ? 1.f : (v < -1.f ? -1.f : v);
}
void ge_switch_pad_init(void) {
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&ge_pad);
}
int ge_switch_pad_poll(ge_pad_sample *out) {
    if (!out) return -1;
    padUpdate(&ge_pad);
    u64 held = padGetButtons(&ge_pad);
    HidAnalogStickState l = padGetStickPos(&ge_pad, 0);
    HidAnalogStickState r = padGetStickPos(&ge_pad, 1);
    u32 buttons = 0;
    if (held & HidNpadButton_A) buttons |= GE_BTN_A;
    if (held & HidNpadButton_B) buttons |= GE_BTN_B;
    if (held & HidNpadButton_X) buttons |= GE_BTN_X;
    if (held & HidNpadButton_Y) buttons |= GE_BTN_Y;
    if (held & HidNpadButton_L) buttons |= GE_BTN_L;
    if (held & HidNpadButton_R) buttons |= GE_BTN_R;
    if (held & HidNpadButton_ZL) buttons |= GE_BTN_ZL;
    if (held & HidNpadButton_ZR) buttons |= GE_BTN_ZR;
    if (held & HidNpadButton_Plus) buttons |= GE_BTN_PLUS;
    *out = (ge_pad_sample){.left_x = axis(l.x), .left_y = axis(l.y),
        .right_x = axis(r.x), .right_y = axis(r.y), .buttons = buttons};
    return 0;
}
#endif
