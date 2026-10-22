#ifndef GOLDENEYE_FAST3D_BRIDGE_H
#define GOLDENEYE_FAST3D_BRIDGE_H
/*
 * Bounded, ROM-free conversions from GoldenEye PC Port's gfx_flush() float
 * VBO layouts to Switch vertex records. Only explicit shader profiles are
 * accepted; this is not a full GfxRenderingAPI implementation.
 *
 * Upstream gfx_pc.cpp, pinned at fda76b69, emits clip x/y/z/w followed by
 * profile-dependent texture, fog and combiner RGB inputs.
 */
#include <stddef.h>
#include <stdint.h>

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
    GE_F3D_NONFINITE,
    GE_F3D_SINK_FAILED
} ge_fast3d_result;

typedef struct {
    unsigned shader_inputs;
    unsigned textures_mask;
    unsigned use_alpha;
    unsigned use_fog;
    unsigned use_grayscale;
    uint64_t shader_id0;
    uint32_t shader_id1;
} ge_fast3d_profile;

typedef struct {
    float position[4];
    float texcoord[2];
    float fog[4];
    float input_rgb[3][3];
} ge_fast3d_fogtex_vertex;

/* The original small bootstrap profile: position vec4 followed by one RGB. */
ge_fast3d_result ge_fast3d_unpack_rgb(
    const float *vbo, size_t float_count, size_t triangle_count,
    const ge_fast3d_profile *profile,
    ge_fast3d_vertex *dst, size_t vertex_capacity,
    size_t *out_vertices);

/* Observed full-engine profile: TEXEL0, fog, two-cycle, three RGB inputs.
 * The clamp-S option changes the VBO stride to 20 and is intentionally not
 * accepted by this first version. */
#define GE_F3D_FOGTEX_RGB3_ID0 UINT64_C(0xd000030d12181218)
#define GE_F3D_FOGTEX_RGB3_ID1 UINT32_C(0x00000012)
ge_fast3d_result ge_fast3d_unpack_fogtex_rgb3(
    const float *vbo, size_t float_count, size_t triangle_count,
    const ge_fast3d_profile *profile,
    ge_fast3d_fogtex_vertex *dst, size_t vertex_capacity,
    size_t *out_vertices);

#ifdef __cplusplus
}
#endif
#endif
