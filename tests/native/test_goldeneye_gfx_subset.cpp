#include "goldeneye_gfx_subset.h"
#include "gfx_cc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static ge_fast3d_vertex vertices[3];
static ge_fast3d_fogtex_vertex fogtex_vertices[3];
static unsigned draws;
static unsigned engine_batches;
static bool sink(void *, const float *vbo, size_t floats, size_t triangles,
                 const ge_fast3d_profile *profile)
{
    size_t count = 0;
    if (profile->shader_id0 == GE_F3D_FOGTEX_RGB3_ID0) {
        bool ok = ge_fast3d_unpack_fogtex_rgb3(
            vbo, floats, triangles, profile, fogtex_vertices, 3, &count) == GE_F3D_OK;
        if (ok) ++engine_batches;
        return ok;
    }
    bool ok = ge_fast3d_unpack_rgb(vbo, floats, triangles, profile, vertices, 3, &count) == GE_F3D_OK;
    if (ok) ++draws;
    return ok;
}
static float triangle[21] = {0, .8f, 0, 2, 1, 0, 0, -.8f, -.8f, 0, 1, 0, 1, 0, .8f, -.8f, 0, 1, 0, 0, 1};
int main(void)
{
    GfxRenderingAPI *api = ge_gfx_subset_api();
    api->init();
    assert(ge_gfx_subset_status() == GE_GFX_BAD_STATE);
    assert(!ge_gfx_subset_attach({nullptr, nullptr}, 1280, 720));
    assert(ge_gfx_subset_attach({nullptr, sink}, 1280, 720));
    /* Check the canonical id against the REAL upstream combiner decoder. */
    CCFeatures features = {};
    gfx_cc_get_features(0x1000, 0, &features);
    assert(features.num_inputs == 1 && !features.used_textures[0] && !features.used_textures[1]);
    assert(features.do_single[0][0] && features.c[0][0][3] == SHADER_INPUT_1);
    /* The first stable nonzero shader key in the live Dam trace uses one
     * texture, fog, two cycles, and three RGB input attributes. */
    CCFeatures traced = {};
    gfx_cc_get_features(GE_F3D_FOGTEX_RGB3_ID0, GE_F3D_FOGTEX_RGB3_ID1, &traced);
    assert(traced.num_inputs == 3 && traced.used_textures[0] && !traced.used_textures[1]);
    assert(traced.opt_fog && traced.opt_2cyc && !traced.opt_alpha && !traced.opt_grayscale);
    float traced_vbo[57];
    for (size_t i = 0; i < 57; ++i) traced_vbo[i] = (float)i / 57.f;
    assert(GE_F3D_OK == ge_gfx_subset_submit_engine_batch(
        traced_vbo, 57, 1, GE_F3D_FOGTEX_RGB3_ID0, GE_F3D_FOGTEX_RGB3_ID1,
        3, 1, 0, 1, 0));
    assert(engine_batches == 1 && fogtex_vertices[0].input_rgb[2][2] == traced_vbo[18]);
    assert(GE_F3D_UNSUPPORTED_PROFILE == ge_gfx_subset_submit_engine_batch(
        traced_vbo, 57, 1, GE_F3D_FOGTEX_RGB3_ID0, 0x112, 3, 1, 0, 1, 0));
    assert(engine_batches == 1); // clamp-S stride remains fail-closed
    assert(api->get_clip_parameters().z_is_from_0_to_1);
    assert(!api->get_clip_parameters().invert_y);
    api->start_frame();
    auto *program = api->create_and_load_new_shader(0x1000, 0);
    assert(program && api->lookup_shader(0x1000, 0) == program);
    uint8_t inputs = 0; bool textures[2] = {true, true};
    api->shader_get_info(program, &inputs, textures);
    assert(inputs == 1 && !textures[0] && !textures[1]);
    api->set_viewport(0, 0, 1280, 720);
    api->set_scissor(0, 0, 1280, 720);
    api->set_depth_mode(false, false, false, false, 0);
    api->draw_triangles(triangle, 21, 1);
    api->end_frame();
    assert(draws == 1 && vertices[0].position[3] == 2);
    assert(ge_gfx_subset_status() == GE_GFX_READY);
    api->start_frame();
    api->set_use_alpha(true, false);
    api->draw_triangles(triangle, 21, 1);
    api->end_frame();
    assert(draws == 1 && ge_gfx_subset_status() == GE_GFX_UNSUPPORTED);
    api->start_frame(); api->draw_triangles(triangle, 21, 1); api->end_frame();
    assert(draws == 1); // rejected cached state survives frame boundaries
    assert(strcmp(ge_gfx_subset_last_operation(), "set_use_alpha") == 0);
    api->init(); api->start_frame();
    assert(!api->create_and_load_new_shader(0x1000, SHADER_OPT_FOG));
    api->draw_triangles(triangle, 21, 1); api->end_frame();
    assert(draws == 1 && ge_gfx_subset_status() == GE_GFX_UNSUPPORTED);
    api->init(); api->start_frame(); api->load_shader(program);
    api->draw_triangles(triangle, 20, 1); api->end_frame();
    assert(draws == 1 && ge_gfx_subset_status() == GE_GFX_DRAW_FAILED);
    api->init(); api->load_shader(program);
    api->draw_triangles(triangle, 21, 1);
    assert(draws == 1 && ge_gfx_subset_status() == GE_GFX_BAD_STATE);
    api->init(); api->start_frame(); api->load_shader(program);
    api->set_depth_mode(true, false, false, false, 0);
    api->draw_triangles(triangle, 21, 1); api->end_frame();
    assert(draws == 1 && ge_gfx_subset_status() == GE_GFX_UNSUPPORTED);
    api->init(); api->start_frame(); api->load_shader(program);
    api->upload_texture(nullptr, 4, 4, false);
    api->draw_triangles(triangle, 21, 1); api->end_frame();
    assert(draws == 1 && ge_gfx_subset_status() == GE_GFX_UNSUPPORTED);
    api->init(); api->start_frame(); api->load_shader(program);
    api->set_scissor(1, 1, 16, 16);
    api->draw_triangles(triangle, 21, 1); api->end_frame();
    assert(draws == 1 && ge_gfx_subset_status() == GE_GFX_UNSUPPORTED);
    puts("Pinned upstream GfxRenderingAPI -> validated vertex sink: PASS (synthetic geometry)");
}
