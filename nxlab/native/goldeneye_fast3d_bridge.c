#include "goldeneye_fast3d_bridge.h"
#include <math.h>
#include <stdint.h>

ge_fast3d_result ge_fast3d_unpack_rgb(
    const float *vbo, size_t float_count, size_t triangle_count,
    const ge_fast3d_profile *profile,
    ge_fast3d_vertex *dst, size_t vertex_capacity,
    size_t *out_vertices)
{
    /* Avoid multiplying any potentially untrusted count until bounded. */
    if (!vbo || !profile || !dst || !out_vertices)
        return GE_F3D_BAD_ARGUMENT;
    if (profile->shader_inputs != 1 || profile->textures_mask != 0 ||
        profile->use_alpha || profile->use_fog || profile->use_grayscale)
        return GE_F3D_UNSUPPORTED_PROFILE;
    if (triangle_count > SIZE_MAX / 3u)
        return GE_F3D_MALFORMED_LENGTH;
    const size_t vertices = triangle_count * 3u;
    if (vertices > SIZE_MAX / 7u || float_count != vertices * 7u)
        return GE_F3D_MALFORMED_LENGTH;
    if (vertices > vertex_capacity)
        return GE_F3D_CAPACITY;
    /* Validate before mutating the destination or output count. */
    for (size_t i = 0; i < float_count; ++i) {
        if (!isfinite(vbo[i]))
            return GE_F3D_NONFINITE;
    }
    for (size_t i = 0; i < vertices; ++i) {
        const float *src = vbo + i * 7u;
        for (unsigned j = 0; j < 4; ++j)
            dst[i].position[j] = src[j];
        for (unsigned j = 0; j < 3; ++j)
            dst[i].rgb[j] = src[4u + j];
    }
    *out_vertices = vertices;
    return GE_F3D_OK;
}
