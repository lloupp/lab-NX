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
    const ge_fast3d_profile supported = { 1, 0, 0, 0, 0 };
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
    puts("Fast3D untextured RGB VBO bridge: PASS");
    return 0;
}
