#ifndef GOLDENEYE_SWITCH_INPUT_H
#define GOLDENEYE_SWITCH_INPUT_H
#include <stdint.h>
/* libnx-neutral boundary: game must consume these semantic actions. */
enum ge_button {
    GE_BTN_A = 1u << 0, GE_BTN_B = 1u << 1,
    GE_BTN_X = 1u << 2, GE_BTN_Y = 1u << 3,
    GE_BTN_L = 1u << 4, GE_BTN_R = 1u << 5,
    GE_BTN_ZL = 1u << 6, GE_BTN_ZR = 1u << 7,
    GE_BTN_PLUS = 1u << 8,
};
typedef struct {
    float left_x, left_y, right_x, right_y; /* -1..1, +Y=up */
    uint32_t buttons;
} ge_pad_sample;
typedef struct {
    float move_deadzone, look_deadzone;
    float look_sensitivity_x, look_sensitivity_y;
    int invert_y, aim_toggle, crouch_toggle;
} ge_input_config;
typedef struct {
    float move_x, move_y, look_x, look_y;
    int aim_held, fire_held, crouch_held;
    int interact_pressed, reload_pressed, weapon_next_pressed;
    int weapon_prev_pressed, pause_pressed;
} ge_input_actions;
typedef struct {
    uint32_t previous_buttons;
    int aim_toggled, crouch_toggled;
} ge_input_state;
ge_input_config ge_default_input_config(void);
int ge_validate_input_config(const ge_input_config *config);
void ge_reset_input(ge_input_state *state, uint32_t buttons_already_held);
int ge_map_input(ge_input_state *state, const ge_input_config *config,
                 const ge_pad_sample *sample, ge_input_actions *out);
#endif
