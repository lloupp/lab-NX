#include "goldeneye_fast3d_bridge.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Synthesized data in gfx_pc.cpp's *actual* 7-float untextured RGB layout:
 * clip X,Y,Z,W, then combiner RGB input0. No copyrighted game data.
 */
static const float fast3d_triangle[21] = {
     0.0f, +0.8f, 0.0f, 1.0f, 1.f, 0.f, 0.f,
    -0.8f, -0.8f, 0.0f, 2.0f, 0.f, 1.f, 0.f,
    +0.8f, -0.8f, 0.3f, 1.0f, 0.f, 0.f, 1.f
};

int main(void)
{
    const ge_fast3d_profile supported = { 1, 0, 0, 0, 0, 0, 0 };
    ge_fast3d_profile unsupported = supported;
    ge_fast3d_vertex dst[3];
    size_t n = 777;
    memset(dst, 0, sizeof dst);
    assert(sizeof(ge_fast3d_vertex) == 7 * sizeof(float));
    assert(GE_F3D_OK == ge_fast3d_unpack_rgb(
        fast3d_triangle, 21, 1, &supported, dst, 3, &n));
    assert(n == 3);
    assert(dst[0].position[1] == .8f);
    assert(dst[1].position[3] == 2.f); /* preserve homogeneous W */
    assert(dst[2].position[2] == .3f);
    assert(dst[2].rgb[2] == 1.f);

    /* The same accepted layout can carry a full Fast3D batch, not only the
     * one-triangle bootstrap fixture. */
    float two_triangles[42];
    ge_fast3d_vertex batch[6];
    size_t batch_vertices = 0;
    memcpy(two_triangles, fast3d_triangle, sizeof fast3d_triangle);
    memcpy(two_triangles + 21, fast3d_triangle, sizeof fast3d_triangle);
    assert(GE_F3D_OK == ge_fast3d_unpack_rgb(
        two_triangles, 42, 2, &supported, batch, 6, &batch_vertices));
    assert(batch_vertices == 6 && batch[5].rgb[2] == 1.f);

    /* First stable game-origin trace profile: one texture, fog, two-cycle,
     * three RGB inputs (19 floats per vertex, no clamp-S extra attribute). */
    const ge_fast3d_profile fogtex_profile = {
        3, 1, 0, 1, 0, GE_F3D_FOGTEX_RGB3_ID0, GE_F3D_FOGTEX_RGB3_ID1
    };
    float fogtex_vbo[57];
    for (size_t i = 0; i < 57; ++i)
        fogtex_vbo[i] = (float)i * 0.125f - 1.f;
    ge_fast3d_fogtex_vertex fogtex_vertices[3];
    size_t fogtex_count = 999;
    assert(sizeof(ge_fast3d_fogtex_vertex) == 19 * sizeof(float));
    assert(GE_F3D_OK == ge_fast3d_unpack_fogtex_rgb3(
        fogtex_vbo, 57, 1, &fogtex_profile, fogtex_vertices, 3, &fogtex_count));
    assert(fogtex_count == 3);
    assert(fogtex_vertices[0].position[0] == fogtex_vbo[0]);
    assert(fogtex_vertices[0].texcoord[1] == fogtex_vbo[5]);
    assert(fogtex_vertices[0].fog[0] == fogtex_vbo[6]);
    assert(fogtex_vertices[0].input_rgb[2][2] == fogtex_vbo[18]);
    assert(fogtex_vertices[2].input_rgb[2][2] == fogtex_vbo[56]);

    ge_fast3d_profile unsupported_fogtex = fogtex_profile;
    unsupported_fogtex.shader_id1 = 0x112; /* clamp-S adds a twentieth float */
    assert(GE_F3D_UNSUPPORTED_PROFILE == ge_fast3d_unpack_fogtex_rgb3(
        fogtex_vbo, 57, 1, &unsupported_fogtex, fogtex_vertices, 3, &fogtex_count));
    assert(GE_F3D_MALFORMED_LENGTH == ge_fast3d_unpack_fogtex_rgb3(
        fogtex_vbo, 56, 1, &fogtex_profile, fogtex_vertices, 3, &fogtex_count));
    assert(GE_F3D_CAPACITY == ge_fast3d_unpack_fogtex_rgb3(
        fogtex_vbo, 57, 1, &fogtex_profile, fogtex_vertices, 2, &fogtex_count));
    assert(fogtex_count == 3);

    /* Unsupported GL/combiner profiles must fail closed. */
    unsupported.use_alpha = 1;
    assert(GE_F3D_UNSUPPORTED_PROFILE == ge_fast3d_unpack_rgb(
        fast3d_triangle, 21, 1, &unsupported, dst, 3, &n));
    unsupported = supported; unsupported.textures_mask = 1;
    assert(GE_F3D_UNSUPPORTED_PROFILE == ge_fast3d_unpack_rgb(
        fast3d_triangle, 21, 1, &unsupported, dst, 3, &n));
    unsupported = supported; unsupported.use_fog = 1;
    assert(GE_F3D_UNSUPPORTED_PROFILE == ge_fast3d_unpack_rgb(
        fast3d_triangle, 21, 1, &unsupported, dst, 3, &n));
    unsupported = supported; unsupported.use_grayscale = 1;
    assert(GE_F3D_UNSUPPORTED_PROFILE == ge_fast3d_unpack_rgb(
        fast3d_triangle, 21, 1, &unsupported, dst, 3, &n));
    unsupported = supported; unsupported.shader_inputs = 2;
    assert(GE_F3D_UNSUPPORTED_PROFILE == ge_fast3d_unpack_rgb(
        fast3d_triangle, 21, 1, &unsupported, dst, 3, &n));

    assert(GE_F3D_CAPACITY == ge_fast3d_unpack_rgb(
        fast3d_triangle, 21, 1, &supported, dst, 2, &n));
    assert(GE_F3D_MALFORMED_LENGTH == ge_fast3d_unpack_rgb(
        fast3d_triangle, 20, 1, &supported, dst, 3, &n));
    assert(GE_F3D_MALFORMED_LENGTH == ge_fast3d_unpack_rgb(
        fast3d_triangle, 21, SIZE_MAX, &supported, dst, 3, &n));
    assert(GE_F3D_BAD_ARGUMENT == ge_fast3d_unpack_rgb(
        NULL, 21, 1, &supported, dst, 3, &n));
    assert(n == 3); /* Must not change on failure. */

    float bad[21];
    memcpy(bad, fast3d_triangle, sizeof bad);
    bad[3] = NAN;
    const ge_fast3d_vertex original = dst[0];
    assert(GE_F3D_NONFINITE == ge_fast3d_unpack_rgb(
        bad, 21, 1, &supported, dst, 3, &n));
    assert(memcmp(&original, &dst[0], sizeof original) == 0);

    assert(GE_F3D_OK == ge_fast3d_unpack_rgb(
        fast3d_triangle, 0, 0, &supported, dst, 3, &n));
    assert(n == 0);
    puts("Fast3D RGB and traced fog/texture VBO bridges: PASS");
    return 0;
}
