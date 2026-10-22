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
        if (!__builtin_isfinite(vbo[i]))
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

ge_fast3d_result ge_fast3d_unpack_fogtex_rgb3(
    const float *vbo, size_t float_count, size_t triangle_count,
    const ge_fast3d_profile *profile,
    ge_fast3d_fogtex_vertex *dst, size_t vertex_capacity,
    size_t *out_vertices)
{
    const size_t floats_per_vertex = 19u;
    if (!vbo || !profile || !dst || !out_vertices)
        return GE_F3D_BAD_ARGUMENT;
    if (profile->shader_id0 != GE_F3D_FOGTEX_RGB3_ID0 ||
        profile->shader_id1 != GE_F3D_FOGTEX_RGB3_ID1 ||
        profile->shader_inputs != 3 || profile->textures_mask != 1 ||
        profile->use_alpha || !profile->use_fog || profile->use_grayscale)
        return GE_F3D_UNSUPPORTED_PROFILE;
    if (triangle_count > SIZE_MAX / 3u)
        return GE_F3D_MALFORMED_LENGTH;
    const size_t vertices = triangle_count * 3u;
    if (vertices > SIZE_MAX / floats_per_vertex ||
        float_count != vertices * floats_per_vertex)
        return GE_F3D_MALFORMED_LENGTH;
    if (vertices > vertex_capacity)
        return GE_F3D_CAPACITY;
    for (size_t i = 0; i < float_count; ++i) {
        if (!__builtin_isfinite(vbo[i]))
            return GE_F3D_NONFINITE;
    }
    for (size_t i = 0; i < vertices; ++i) {
        const float *src = vbo + i * floats_per_vertex;
        ge_fast3d_fogtex_vertex *vertex = &dst[i];
        for (unsigned j = 0; j < 4; ++j)
            vertex->position[j] = src[j];
        for (unsigned j = 0; j < 2; ++j)
            vertex->texcoord[j] = src[4u + j];
        for (unsigned j = 0; j < 4; ++j)
            vertex->fog[j] = src[6u + j];
        for (unsigned input = 0; input < 3; ++input) {
            for (unsigned channel = 0; channel < 3; ++channel)
                vertex->input_rgb[input][channel] = src[10u + input * 3u + channel];
        }
    }
    *out_vertices = vertices;
    return GE_F3D_OK;
}
