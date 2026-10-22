#ifndef GOLDENEYE_GFX_SUBSET_H
#define GOLDENEYE_GFX_SUBSET_H
#include "gfx_rendering_api.h"
#include "goldeneye_fast3d_bridge.h"
#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    void *user;
    /* Synchronous sink: must consume/copy all vertices before returning.
     * May not retain or overwrite GPU-in-flight storage without a fence. */
    bool (*draw)(void *user, const float *vbo, size_t floats, size_t triangles,
                 const ge_fast3d_profile *profile);
} ge_gfx_sink;

enum { GE_GFX_READY, GE_GFX_UNSUPPORTED, GE_GFX_BAD_STATE, GE_GFX_DRAW_FAILED };
/* A concrete upstream GfxRenderingAPI subset, not the full game renderer.
 * Only canonical single-cycle SHADE RGB (id0=0x1000,id1=0), full-screen
 * viewport/scissor, no textures, no depth, no alpha and main framebuffer.
 * Unsupported operations latch an error until init; no later draw is submitted.
 */
bool ge_gfx_subset_attach(ge_gfx_sink sink, unsigned width, unsigned height);
struct GfxRenderingAPI *ge_gfx_subset_api(void);
/* Bounded mirror hook for the full-engine trace path. It forwards only known
 * VBO profiles to the attached sink; this CPU bridge is not itself a GPU draw. */
ge_fast3d_result ge_gfx_subset_submit_engine_batch(
    const float *vbo, size_t floats, size_t triangles,
    uint64_t shader_id0, uint32_t shader_id1, unsigned shader_inputs,
    unsigned textures_mask, unsigned use_alpha, unsigned use_fog,
    unsigned use_grayscale);
int ge_gfx_subset_status(void);
const char *ge_gfx_subset_last_operation(void);
#ifdef __cplusplus
}
#endif
#endif
