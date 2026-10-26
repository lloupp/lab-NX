#ifndef GFX_DEKO3D_H
#define GFX_DEKO3D_H

#include "gfx_rendering_api.h"
#include "gfx_window_manager_api.h"

#ifdef __cplusplus
extern "C" {
#endif

extern struct GfxWindowManagerAPI gfx_deko3d_wm;
extern struct GfxRenderingAPI gfx_deko3d_api;

/* Draw statistics, for the engine log and evidence runs. */
unsigned gfx_deko3d_draw_calls(void);
unsigned gfx_deko3d_skipped_calls(void);
unsigned gfx_deko3d_presented_frames(void);

#ifdef __cplusplus
}
#endif

#endif
