#ifndef GOLDENEYE_FAST3D_BRIDGE_H
#define GOLDENEYE_FAST3D_BRIDGE_H
/*
 * A bounded, ROM-free bridge from GoldenEye PC Port's gfx_flush() float VBO
 * to the Switch deko3d vertex format. This is intentionally ONE shader
 * profile, not a full GfxRenderingAPI implementation.
 *
 * Upstream gfx_pc.cpp, draw path (commit fda76b69):
 *  clip x, y, z, w; for each untextured shader input RGB r, g, b.
 * Other profiles (texture, fog, grayscale, alpha) MUST be rejected here.
 */
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float position[4];
    float rgb[3];
} ge_fast3d_vertex;

typedef enum {
    GE_F3D_OK = 0,
    GE_F3D_BAD_ARGUMENT,
    GE_F3D_UNSUPPORTED_PROFILE,
    GE_F3D_MALFORMED_LENGTH,
    GE_F3D_CAPACITY,
    GE_F3D_NONFINITE
} ge_fast3d_result;

typedef struct {
    unsigned shader_inputs;    /* exactly 1 RGB input */
    unsigned textures_mask;    /* must be 0 */
    unsigned use_alpha;        /* must be 0 */
    unsigned use_fog;          /* must be 0 */
    unsigned use_grayscale;    /* must be 0 */
} ge_fast3d_profile;

/* Exactly 7 float values per vertex in the only currently accepted profile.
 * The downstream DKSH consumes a vec4 homogeneous clip-space position and
 * RGB. The z range has already been adjusted by gfx_pc.cpp.
 * All capacities are vertex counts; out_vertices is unchanged on failure.
 */
ge_fast3d_result ge_fast3d_unpack_rgb(
    const float *vbo, size_t float_count, size_t triangle_count,
    const ge_fast3d_profile *profile,
    ge_fast3d_vertex *dst, size_t vertex_capacity,
    size_t *out_vertices);

#ifdef __cplusplus
}
#endif
#endif
