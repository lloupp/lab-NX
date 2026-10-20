#include "goldeneye_gfx_subset.h"
#include <limits.h>
#include <string.h>

struct ShaderProgram { uint64_t id0; uint32_t id1; };
static ShaderProgram shade = {0x1000, 0};
static ShaderProgram *loaded;
static ge_gfx_sink output;
static unsigned screen_width, screen_height;
static int status = GE_GFX_BAD_STATE;
static const char *operation = "not-attached";
static bool attached, in_frame;

static void fail(const char *name, int error = GE_GFX_UNSUPPORTED)
{
    if (status == GE_GFX_READY) { status = error; operation = name; }
}
static const char *name(void) { return "deko3d SHADE RGB subset"; }
static int max_texture(void) { return 0; }
static GfxClipParameters clip(void) { return {true, false}; }
static void unload(ShaderProgram *) { loaded = nullptr; }
static void load(ShaderProgram *p)
{
    loaded = nullptr;
    if (p == &shade) loaded = p; else fail("load_shader");
}
static ShaderProgram *lookup(uint64_t id0, uint32_t id1)
{
    return id0 == shade.id0 && id1 == 0 ? &shade : nullptr;
}
static ShaderProgram *create(uint64_t id0, uint32_t id1)
{
    ShaderProgram *p = lookup(id0, id1);
    load(p);
    return p;
}
static void shader_info(ShaderProgram *p, uint8_t *n, bool textures[2])
{
    if (n) *n = p == &shade ? 1 : 0;
    if (textures) textures[0] = textures[1] = false;
    if (p != &shade || !n || !textures) fail("shader_get_info", GE_GFX_BAD_STATE);
}
static void clear_shaders(void) { loaded = nullptr; }
static uint32_t new_texture(void) { fail("new_texture"); return 0; }
static void select_texture(int, uint32_t, bool) { fail("select_texture"); }
static void upload(const uint8_t *, uint32_t, uint32_t, bool) { fail("upload_texture"); }
static void sampler(int, bool, uint32_t, uint32_t, bool) { fail("set_sampler_parameters"); }
static void depth(bool test, bool update, bool compare, bool prim, uint16_t mode)
{
    if (test || update || compare || prim || mode) fail("set_depth_mode");
}
static void depth_range(float near_value, float far_value)
{
    if (near_value != 0.f || far_value != 1.f) fail("set_depth_range");
}
static void viewport(int x, int y, int w, int h)
{
    if (x || y || w != (int)screen_width || h != (int)screen_height) fail("set_viewport");
}
static void scissor(int x, int y, int w, int h)
{
    if (x || y || w != (int)screen_width || h != (int)screen_height) fail("set_scissor");
}
static void alpha(bool use, bool modulate)
{
    if (use || modulate) fail("set_use_alpha");
}
static void draw(float *vbo, size_t count, size_t triangles)
{
    if (!in_frame || !loaded) fail("draw_without_frame_or_shader", GE_GFX_BAD_STATE);
    if (status != GE_GFX_READY) return;
    const ge_fast3d_profile profile = {1, 0, 0, 0, 0};
    if (!output.draw(output.user, vbo, count, triangles, &profile))
        fail("draw_sink", GE_GFX_DRAW_FAILED);
}
static void init(void)
{
    loaded = nullptr;
    in_frame = false;
    status = attached ? GE_GFX_READY : GE_GFX_BAD_STATE;
    operation = attached ? "ready" : "not-attached";
}
static void resize(void) { fail("on_resize"); }
static void start(void)
{
    if (!attached || in_frame) { fail("start_frame", GE_GFX_BAD_STATE); return; }
    /* Preserve unsupported state across frames. Only init/reattach recovers;
     * otherwise cached engine state might silently retain a rejected mode. */
    in_frame = true;
}
static void end(void)
{
    if (!in_frame) fail("end_frame", GE_GFX_BAD_STATE);
    in_frame = false;
}
static void finish(void) { /* sink consumes CPU input synchronously */ }
static int framebuffer(void) { fail("create_framebuffer"); return -1; }
static void update_fb(int, uint32_t, uint32_t, uint32_t, bool, bool, bool, bool)
{ fail("update_framebuffer_parameters"); }
static bool draw_fb(int id, float)
{
    if (id != 0) fail("start_draw_to_framebuffer");
    return status == GE_GFX_READY;
}
static void copy_fb(int, int, int, int, bool, bool) { fail("copy_framebuffer"); }
static void clear_fb(bool color, bool depth_buffer)
{
    /* This adapter has no clear sink yet. Do not pretend a clear happened. */
    if (color || depth_buffer) fail("clear_framebuffer");
}
static void resolve(int, int) { fail("resolve_msaa_color_buffer"); }
static void *fb_texture(int) { fail("get_framebuffer_texture_id"); return nullptr; }
static void select_fb(int) { fail("select_texture_fb"); }
static void delete_texture(uint32_t) { fail("delete_texture"); }
static void filter(FilteringMode mode) { if (mode != FILTER_NONE) fail("set_texture_filter"); }
static FilteringMode get_filter(void) { return FILTER_NONE; }
static void mipmap(MipmapFilteringMode mode) { if (mode != MIPMAP_DISABLED) fail("set_mipmap_filter"); }
static void anisotropy(int level) { if (level > 1 || level < 0) fail("set_anisotropy_level"); }
static int max_anisotropy(void) { return 1; }

/* Named assignments deliberately compile against the pinned REAL upstream
 * header. Added/changed callback signatures must break the build. */
static GfxRenderingAPI make_api(void)
{
    GfxRenderingAPI api = {};
    api.get_name = name; api.get_max_texture_size = max_texture;
    api.get_clip_parameters = clip; api.unload_shader = unload;
    api.load_shader = load; api.create_and_load_new_shader = create;
    api.lookup_shader = lookup; api.shader_get_info = shader_info;
    api.clear_shaders = clear_shaders; api.new_texture = new_texture;
    api.select_texture = select_texture; api.upload_texture = upload;
    api.set_sampler_parameters = sampler; api.set_depth_mode = depth;
    api.set_depth_range = depth_range; api.set_viewport = viewport;
    api.set_scissor = scissor; api.set_use_alpha = alpha;
    api.draw_triangles = draw; api.init = init; api.on_resize = resize;
    api.start_frame = start; api.end_frame = end; api.finish_render = finish;
    api.create_framebuffer = framebuffer; api.update_framebuffer_parameters = update_fb;
    api.start_draw_to_framebuffer = draw_fb; api.copy_framebuffer = copy_fb;
    api.clear_framebuffer = clear_fb; api.resolve_msaa_color_buffer = resolve;
    api.get_framebuffer_texture_id = fb_texture; api.select_texture_fb = select_fb;
    api.delete_texture = delete_texture; api.set_texture_filter = filter;
    api.get_texture_filter = get_filter; api.set_mipmap_filter = mipmap;
    api.set_anisotropy_level = anisotropy; api.get_max_anisotropy_level = max_anisotropy;
    return api;
}

extern "C" bool ge_gfx_subset_attach(ge_gfx_sink sink, unsigned width, unsigned height)
{
    if (!sink.draw || !width || !height || width > INT_MAX || height > INT_MAX) return false;
    output = sink; screen_width = width; screen_height = height; attached = true;
    init();
    return true;
}
extern "C" GfxRenderingAPI *ge_gfx_subset_api(void)
{
    static GfxRenderingAPI api = make_api();
    return &api;
}
extern "C" int ge_gfx_subset_status(void) { return status; }
extern "C" const char *ge_gfx_subset_last_operation(void) { return operation; }
