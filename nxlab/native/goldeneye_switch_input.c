#include "goldeneye_switch_input.h"
#include <math.h>
#include <string.h>

static float clamp(float v) { return v > 1.f ? 1.f : (v < -1.f ? -1.f : v); }
static void deadzone(float *x, float *y, float dead) {
    float mag = sqrtf(*x * *x + *y * *y);
    if (mag <= dead) { *x = 0; *y = 0; return; }
    float adjusted = (fminf(mag, 1.f) - dead) / (1.f - dead);
    *x = (*x / mag) * adjusted;
    *y = (*y / mag) * adjusted;
}
ge_input_config ge_default_input_config(void) {
    return (ge_input_config){.move_deadzone = .15f, .look_deadzone = .12f,
        .look_sensitivity_x = 1.f, .look_sensitivity_y = 1.f,
        .invert_y = 0, .aim_toggle = 0, .crouch_toggle = 1};
}
int ge_validate_input_config(const ge_input_config *p) {
    return p && isfinite(p->move_deadzone) && isfinite(p->look_deadzone)
        && p->move_deadzone >= 0 && p->move_deadzone < 1
        && p->look_deadzone >= 0 && p->look_deadzone < 1
        && isfinite(p->look_sensitivity_x) && isfinite(p->look_sensitivity_y)
        && p->look_sensitivity_x >= .1f && p->look_sensitivity_x <= 3.f
        && p->look_sensitivity_y >= .1f && p->look_sensitivity_y <= 3.f;
}
void ge_reset_input(ge_input_state *s, uint32_t held) {
    if (s) { s->previous_buttons = held; s->aim_toggled = 0; s->crouch_toggled = 0; }
}
int ge_map_input(ge_input_state *state, const ge_input_config *c,
                 const ge_pad_sample *pad, ge_input_actions *out) {
    if (!state || !pad || !out || !ge_validate_input_config(c)) return -1;
    if (!isfinite(pad->left_x) || !isfinite(pad->left_y)
        || !isfinite(pad->right_x) || !isfinite(pad->right_y)) return -1;
    ge_input_actions a;
    memset(&a, 0, sizeof(a));
    a.move_x = clamp(pad->left_x); a.move_y = clamp(pad->left_y);
    a.look_x = clamp(pad->right_x); a.look_y = clamp(pad->right_y);
    deadzone(&a.move_x, &a.move_y, c->move_deadzone);
    deadzone(&a.look_x, &a.look_y, c->look_deadzone);
    a.look_x = clamp(a.look_x * c->look_sensitivity_x);
    a.look_y = clamp(a.look_y * c->look_sensitivity_y * (c->invert_y ? -1.f : 1.f));
    uint32_t newly = pad->buttons & ~state->previous_buttons;
    int aim = state->aim_toggled;
    int crouch = state->crouch_toggled;
    if (c->aim_toggle && (newly & GE_BTN_ZL)) aim = !aim;
    if (c->crouch_toggle && (newly & GE_BTN_B)) crouch = !crouch;
    a.aim_held = c->aim_toggle ? aim : !!(pad->buttons & GE_BTN_ZL);
    a.fire_held = !!(pad->buttons & GE_BTN_ZR);
    a.crouch_held = c->crouch_toggle ? crouch : !!(pad->buttons & GE_BTN_B);
    a.interact_pressed = !!(newly & GE_BTN_A);
    a.reload_pressed = !!(newly & GE_BTN_Y);
    a.weapon_next_pressed = !!(newly & (GE_BTN_X | GE_BTN_R));
    a.weapon_prev_pressed = !!(newly & GE_BTN_L);
    a.pause_pressed = !!(newly & GE_BTN_PLUS);
    *out = a;
    state->aim_toggled = aim;
    state->crouch_toggled = crouch;
    state->previous_buttons = pad->buttons;
    return 0;
}
