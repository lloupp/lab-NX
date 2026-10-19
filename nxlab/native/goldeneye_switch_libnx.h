#ifndef GOLDENEYE_SWITCH_LIBNX_H
#define GOLDENEYE_SWITCH_LIBNX_H
#include "goldeneye_switch_input.h"
#ifdef __SWITCH__
void ge_switch_pad_init(void);
int ge_switch_pad_poll(ge_pad_sample *out);
#endif
#endif
