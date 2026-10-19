#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "goldeneye_switch_input.h"

int main(void) {
    ge_input_config cfg = ge_default_input_config();
    ge_input_state state = {0};
    ge_input_actions out = {0};
    ge_pad_sample sample = {.left_x = 1, .right_y = .7f,
        .buttons = GE_BTN_A | GE_BTN_Y | GE_BTN_ZL | GE_BTN_ZR};
    assert(ge_map_input(&state, &cfg, &sample, &out) == 0);
    assert(out.move_x == 1.f && out.move_y == 0.f);
    assert(out.look_y > .5f && out.look_x == 0.f);
    assert(out.aim_held && out.fire_held && out.interact_pressed && out.reload_pressed);
    assert(!out.crouch_held && !out.pause_pressed);
    assert(ge_map_input(&state, &cfg, &sample, &out) == 0);
    assert(out.aim_held && out.fire_held && !out.interact_pressed && !out.reload_pressed);
    ge_reset_input(&state, sample.buttons);
    assert(ge_map_input(&state, &cfg, &sample, &out) == 0 && !out.interact_pressed);
    cfg.invert_y = 1; cfg.look_sensitivity_y = 2.f;
    assert(ge_map_input(&state, &cfg, &sample, &out) == 0 && out.look_y == -1.f);
    cfg.aim_toggle = 1; cfg.crouch_toggle = 1;
    ge_reset_input(&state, 0);
    sample.buttons = GE_BTN_ZL | GE_BTN_B;
    assert(ge_map_input(&state, &cfg, &sample, &out) == 0 && out.aim_held && out.crouch_held);
    sample.buttons = 0;
    assert(ge_map_input(&state, &cfg, &sample, &out) == 0 && out.aim_held && out.crouch_held);
    sample.buttons = GE_BTN_ZL | GE_BTN_B;
    assert(ge_map_input(&state, &cfg, &sample, &out) == 0 && !out.aim_held && !out.crouch_held);
    cfg.look_deadzone = .5f; sample.right_y = .1f;
    assert(ge_map_input(&state, &cfg, &sample, &out) == 0 && out.look_y == 0.f);
    cfg.look_deadzone = 1.f;
    assert(ge_map_input(&state, &cfg, &sample, &out) == -1);
    cfg.look_deadzone = .15f;
    sample.right_x = NAN;
    assert(ge_map_input(&state, &cfg, &sample, &out) == -1);
    puts("native input: PASS");
    return 0;
}
