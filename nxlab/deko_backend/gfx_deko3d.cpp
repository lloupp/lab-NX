/*
 * deko3d backend for the GoldenEye PC port (Switch stage 1).
 *
 * This replaces the SDL/OpenGL window manager and Fast3D's OpenGL rendering
 * API with a deko3d device, swapchain and command stream. It intentionally
 * covers the profiles already described by nxlab/native/goldeneye_fast3d_bridge.h:
 *
 *   - SHADE RGB        (0x1000:0)                 position + one RGB input
 *   - FOGTEX RGB3      (d000030d12181218:00000012) position + tex + fog + 3 RGB
 *
 * Both draw through one precompiled DKSH program that consumes clip position
 * and the first RGB input. Textures are not sampled yet, so textured batches
 * render with their interpolated shade colour. Every other combiner profile
 * keeps the engine's VBO layout but is skipped at draw time; the counters are
 * reported to the log.
 *
 * The geometry path is the real engine's: gfx_pc.cpp builds the float VBO and
 * calls draw_triangles. No ROM data, no synthetic triangle.
 */
#include <switch.h>
#include <deko3d.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "platform.h"
#include "system.h"
#include "gfx_rendering_api.h"
#include "gfx_window_manager_api.h"
#include "gfx_cc.h"
#include "goldeneye_fast3d_bridge.h"
#include "deko_shader_bytes.h"
#include "gfx_deko3d.h"

extern "C" void videoRequestQuit(const char *why);

#define GE_DEKO_FRAMES 2u
#define GE_DEKO_CODE_BYTES (64u * 1024u)
#define GE_DEKO_CMD_BYTES (256u * 1024u)
#define GE_DEKO_VERTEX_BYTES (2u * 1024u * 1024u)
#define GE_DEKO_STAGING_BYTES (8u * 1024u * 1024u)
#define GE_DEKO_MAX_PROGRAMS 64
#define GE_DEKO_MAX_TEXTURES 256

struct DekoProgram {
    uint64_t id0;
    uint32_t id1;
    uint8_t num_inputs;
    bool used_textures[SHADER_MAX_TEXTURES];
    bool supported;
    bool fogtex;
    bool env2tex;
    bool flat;
    bool alpha_combiner;
    bool texedge;
    bool alpha_threshold;
    bool sky;
    bool tex0_fallback;
    bool texmix_fallback;
};

struct DekoTexture {
    DkImage image;
    DkMemBlock mem;
    DkImageView view;
    uint32_t width, height;
    uint32_t mip_levels;
    bool ready;
};

static struct {
    DkDevice device;
    DkSwapchain swapchain;
    DkImage images[GE_DEKO_FRAMES];
    DkImage depth;
    DkMemBlock frame_mem;
    DkMemBlock depth_mem;
    DkMemBlock code_mem;
    DkMemBlock vertex_mem;
    DkMemBlock staging_mem;
    uint32_t staging_used;
    DkMemBlock retired_mem[64];
    uint32_t retired_count;
    DkMemBlock cmd_mem;
    DkMemBlock desc_mem;
    DkImageDescriptor *image_desc;
    DkSamplerDescriptor *sampler_desc;
    DkGpuAddr image_desc_gpu;
    DkGpuAddr sampler_desc_gpu;
    DkSampler sampler;
    uint32_t upload_id;
    uint32_t selected_id[2];
    DekoTexture textures[GE_DEKO_MAX_TEXTURES];
    DkCmdBuf cmd;
    DkQueue queue;
    DkShader vsh;
    DkShader fsh;
    DkShader fogtex_vsh;
    DkShader fogtex_fsh;
    DkShader env_vsh;
    DkShader env_fsh;
    DkShader env_alpha_fsh;
    DkShader env_edge_fsh;
    DkShader env_thresh_fsh;
    DkShader flat_vsh;
    DkShader flat_fsh;
    DkShader sky_fsh;
    DkShader tex0_fsh;
    DkShader texmix_fsh;
    DkImageView color_view;
    DkImageView depth_view;
    DkCmdList frame_cmd;
    uint32_t code_used;
    uint32_t width;
    uint32_t height;
    int slot;
    bool in_frame;
    bool depth_test;
    bool depth_write;
    bool alpha;
    bool modulate;
    size_t vertex_used;
    unsigned draws;
    unsigned skipped;
    unsigned presented;
    unsigned programs;
    DekoProgram program[GE_DEKO_MAX_PROGRAMS];
    DekoProgram *current;
    uint32_t next_texture;
    int vp_x, vp_y, vp_w, vp_h;
    int sc_x, sc_y, sc_w, sc_h;
} g;

static bool gpu_ready;

unsigned gfx_deko3d_draw_calls(void) { return g.draws; }
unsigned gfx_deko3d_skipped_calls(void) { return g.skipped; }
unsigned gfx_deko3d_presented_frames(void) { return g.presented; }

static bool deko_load_shader(DkShader *shader, const unsigned char *bytes, unsigned length)
{
    if (!bytes || !length || length > GE_DEKO_CODE_BYTES) {
        return false;
    }
    const uint32_t offset = g.code_used;
    const uint32_t padded = (length + DK_SHADER_CODE_ALIGNMENT - 1u) & ~(DK_SHADER_CODE_ALIGNMENT - 1u);
    if (offset > GE_DEKO_CODE_BYTES || padded > GE_DEKO_CODE_BYTES - offset) {
        return false;
    }
    uint8_t *dst = (uint8_t *)dkMemBlockGetCpuAddr(g.code_mem);
    if (!dst) {
        return false;
    }
    memcpy(dst + offset, bytes, length);
    DkShaderMaker maker;
    dkShaderMakerDefaults(&maker, g.code_mem, offset);
    dkShaderInitialize(shader, &maker);
    g.code_used += padded;
    return true;
}

static void deko_debug(void *user, const char *context, DkResult result, const char *message)
{
    (void)user;
    sysLogPrintf(LOG_WARNING, "deko3d debug: %s result=%d message=%s",
                 context ? context : "?", (int)result, message ? message : "?");
}

static bool deko_gpu_init(uint32_t width, uint32_t height)
{
    if (gpu_ready) {
        return true;
    }
    g.width = width;
    g.height = height;
    g.vp_w = (int)width;
    g.vp_h = (int)height;
    g.sc_w = (int)width;
    g.sc_h = (int)height;
    g.depth_test = true;
    g.depth_write = true;

    sysLogPrintf(LOG_NOTE, "deko3d: device create");
    DkDeviceMaker device_maker;
    dkDeviceMakerDefaults(&device_maker);
    device_maker.cbDebug = deko_debug;
    g.device = dkDeviceCreate(&device_maker);
    if (!g.device) {
        sysLogPrintf(LOG_ERROR, "deko3d: device creation failed");
        return false;
    }

    DkImageLayoutMaker layout_maker;
    dkImageLayoutMakerDefaults(&layout_maker, g.device);
    layout_maker.flags = DkImageFlags_UsageRender | DkImageFlags_UsagePresent | DkImageFlags_HwCompression;
    layout_maker.format = DkImageFormat_RGBA8_Unorm;
    layout_maker.dimensions[0] = width;
    layout_maker.dimensions[1] = height;
    DkImageLayout layout;
    dkImageLayoutInitialize(&layout, &layout_maker);
    uint32_t image_bytes = dkImageLayoutGetSize(&layout);
    const uint32_t image_align = dkImageLayoutGetAlignment(&layout);
    image_bytes = (image_bytes + image_align - 1u) & ~(image_align - 1u);

    sysLogPrintf(LOG_NOTE, "deko3d: frame memory %u bytes", (unsigned)(GE_DEKO_FRAMES * image_bytes));
    DkMemBlockMaker memory_maker;
    dkMemBlockMakerDefaults(&memory_maker, g.device, GE_DEKO_FRAMES * image_bytes);
    memory_maker.flags = DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image;
    g.frame_mem = dkMemBlockCreate(&memory_maker);
    if (!g.frame_mem) {
        sysLogPrintf(LOG_ERROR, "deko3d: frame memory failed");
        return false;
    }
    const DkImage *swap_images[GE_DEKO_FRAMES];
    for (unsigned i = 0; i < GE_DEKO_FRAMES; ++i) {
        dkImageInitialize(&g.images[i], &layout, g.frame_mem, i * image_bytes);
        swap_images[i] = &g.images[i];
    }
    sysLogPrintf(LOG_NOTE, "deko3d: swapchain create");
    DkSwapchainMaker swap_maker;
    dkSwapchainMakerDefaults(&swap_maker, g.device, nwindowGetDefault(), swap_images, GE_DEKO_FRAMES);
    g.swapchain = dkSwapchainCreate(&swap_maker);
    if (!g.swapchain) {
        sysLogPrintf(LOG_ERROR, "deko3d: swapchain creation failed");
        return false;
    }

    DkImageLayoutMaker depth_layout_maker;
    dkImageLayoutMakerDefaults(&depth_layout_maker, g.device);
    depth_layout_maker.flags = DkImageFlags_UsageRender;
    depth_layout_maker.format = DkImageFormat_Z24S8;
    depth_layout_maker.dimensions[0] = width;
    depth_layout_maker.dimensions[1] = height;
    DkImageLayout depth_layout;
    dkImageLayoutInitialize(&depth_layout, &depth_layout_maker);
    uint32_t depth_bytes = dkImageLayoutGetSize(&depth_layout);
    const uint32_t depth_align = dkImageLayoutGetAlignment(&depth_layout);
    depth_bytes = (depth_bytes + depth_align - 1u) & ~(depth_align - 1u);
    sysLogPrintf(LOG_NOTE, "deko3d: depth memory %u bytes", (unsigned)depth_bytes);
    dkMemBlockMakerDefaults(&memory_maker, g.device, depth_bytes);
    memory_maker.flags = DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image;
    g.depth_mem = dkMemBlockCreate(&memory_maker);
    if (!g.depth_mem) {
        sysLogPrintf(LOG_ERROR, "deko3d: depth memory failed");
        return false;
    }
    dkImageInitialize(&g.depth, &depth_layout, g.depth_mem, 0);
    dkImageViewDefaults(&g.depth_view, &g.depth);

    sysLogPrintf(LOG_NOTE, "deko3d: shader memory");
    dkMemBlockMakerDefaults(&memory_maker, g.device, GE_DEKO_CODE_BYTES);
    memory_maker.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached | DkMemBlockFlags_Code;
    g.code_mem = dkMemBlockCreate(&memory_maker);
    if (!g.code_mem) {
        sysLogPrintf(LOG_ERROR, "deko3d: shader memory failed");
        return false;
    }
    if (!deko_load_shader(&g.vsh, deko_triangle_vsh, deko_triangle_vsh_len) ||
        !deko_load_shader(&g.fsh, deko_color_fsh, deko_color_fsh_len) ||
        !deko_load_shader(&g.fogtex_vsh, deko_fogtex_vsh, deko_fogtex_vsh_len) ||
        !deko_load_shader(&g.fogtex_fsh, deko_fogtex_fsh, deko_fogtex_fsh_len) ||
        !deko_load_shader(&g.env_vsh, deko_env2tex_vsh, deko_env2tex_vsh_len) ||
        !deko_load_shader(&g.env_fsh, deko_env2tex_fsh, deko_env2tex_fsh_len) ||
        !deko_load_shader(&g.env_alpha_fsh, deko_env2tex_alpha_fsh, deko_env2tex_alpha_fsh_len) ||
        !deko_load_shader(&g.env_edge_fsh, deko_env2tex_edge_fsh, deko_env2tex_edge_fsh_len) ||
        !deko_load_shader(&g.env_thresh_fsh, deko_env2tex_thresh_fsh, deko_env2tex_thresh_fsh_len) ||
        !deko_load_shader(&g.flat_vsh, deko_flat_vsh, deko_flat_vsh_len) ||
        !deko_load_shader(&g.flat_fsh, deko_flat_fsh, deko_flat_fsh_len) ||
        !deko_load_shader(&g.sky_fsh, deko_sky_fsh, deko_sky_fsh_len) ||
        !deko_load_shader(&g.tex0_fsh, deko_tex0_fsh, deko_tex0_fsh_len) ||
        !deko_load_shader(&g.texmix_fsh, deko_texmix_fsh, deko_texmix_fsh_len)) {
        sysLogPrintf(LOG_ERROR, "deko3d: DKSH load failed");
        return false;
    }

    sysLogPrintf(LOG_NOTE, "deko3d: vertex memory %u bytes", (unsigned)GE_DEKO_VERTEX_BYTES);
    dkMemBlockMakerDefaults(&memory_maker, g.device, GE_DEKO_VERTEX_BYTES);
    memory_maker.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached;
    g.vertex_mem = dkMemBlockCreate(&memory_maker);
    if (!g.vertex_mem) {
        sysLogPrintf(LOG_ERROR, "deko3d: vertex memory failed");
        return false;
    }

    /* Linear staging for texture uploads. Mipmapped images are block-linear
     * (pitch-linear cannot have mips), so the CPU copy goes through the blit
     * engine with a mip chain blitted level by level. Reset per frame after
     * the queue wait. */
    sysLogPrintf(LOG_NOTE, "deko3d: upload staging %u bytes", (unsigned)GE_DEKO_STAGING_BYTES);
    dkMemBlockMakerDefaults(&memory_maker, g.device, GE_DEKO_STAGING_BYTES);
    memory_maker.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached;
    g.staging_mem = dkMemBlockCreate(&memory_maker);
    if (!g.staging_mem) {
        sysLogPrintf(LOG_WARNING, "deko3d: upload staging failed; textures stay pitch-linear without mips");
    }
    g.staging_used = 0;

    sysLogPrintf(LOG_NOTE, "deko3d: command memory %u bytes", (unsigned)GE_DEKO_CMD_BYTES);
    const uint32_t image_desc_bytes = GE_DEKO_MAX_TEXTURES * (uint32_t)sizeof(DkImageDescriptor);
    const uint32_t sampler_desc_bytes = GE_DEKO_MAX_TEXTURES * (uint32_t)sizeof(DkSamplerDescriptor);
    sysLogPrintf(LOG_NOTE, "deko3d: descriptor memory");
    uint32_t desc_size = image_desc_bytes + sampler_desc_bytes + 64;
    desc_size = (desc_size + DK_MEMBLOCK_ALIGNMENT - 1u) & ~(DK_MEMBLOCK_ALIGNMENT - 1u);
    dkMemBlockMakerDefaults(&memory_maker, g.device, desc_size);
    memory_maker.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached;
    g.desc_mem = dkMemBlockCreate(&memory_maker);
    if (!g.desc_mem) {
        sysLogPrintf(LOG_ERROR, "deko3d: descriptor memory failed");
        return false;
    }
    {
        uint8_t *desc_cpu = (uint8_t *)dkMemBlockGetCpuAddr(g.desc_mem);
        uint8_t *desc_gpu = (uint8_t *)(uintptr_t)dkMemBlockGetGpuAddr(g.desc_mem);
        sysLogPrintf(LOG_NOTE, "deko3d: descriptor block cpu=%p gpu=%p imgbytes=%u smpbytes=%u",
                     (void *)desc_cpu, (void *)desc_gpu, (unsigned)image_desc_bytes,
                     (unsigned)sampler_desc_bytes);
        if (!desc_cpu) {
            sysLogPrintf(LOG_ERROR, "deko3d: descriptor block has no CPU address");
            return false;
        }
        const uintptr_t image_off = ((uintptr_t)desc_cpu + 31u) & ~(uintptr_t)31u;
        g.image_desc = (DkImageDescriptor *)image_off;
        g.image_desc_gpu = (DkGpuAddr)((uintptr_t)desc_gpu + (image_off - (uintptr_t)desc_cpu));
        const uintptr_t sampler_off = (image_off + image_desc_bytes + 31u) & ~(uintptr_t)31u;
        g.sampler_desc = (DkSamplerDescriptor *)sampler_off;
        g.sampler_desc_gpu = (DkGpuAddr)((uintptr_t)desc_gpu + (sampler_off - (uintptr_t)desc_cpu));
        dkSamplerDefaults(&g.sampler);
        g.sampler.minFilter = DkFilter_Linear;
        g.sampler.magFilter = DkFilter_Linear;
        g.sampler.wrapMode[0] = DkWrapMode_Repeat;
        g.sampler.wrapMode[1] = DkWrapMode_Repeat;
        g.sampler.wrapMode[2] = DkWrapMode_Repeat;
        sysLogPrintf(LOG_NOTE, "deko3d: image_desc=%p sampler_desc=%p img_gpu=%llx smp_gpu=%llx",
                     (void *)g.image_desc, (void *)g.sampler_desc,
                     (unsigned long long)g.image_desc_gpu, (unsigned long long)g.sampler_desc_gpu);
        dkSamplerDescriptorInitialize(&g.sampler_desc[0], &g.sampler);
        sysLogPrintf(LOG_NOTE, "deko3d: sampler descriptor initialized");
    }

    sysLogPrintf(LOG_NOTE, "deko3d: command memblock create");
    dkMemBlockMakerDefaults(&memory_maker, g.device, GE_DEKO_CMD_BYTES);
    memory_maker.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached;
    g.cmd_mem = dkMemBlockCreate(&memory_maker);
    if (!g.cmd_mem) {
        sysLogPrintf(LOG_ERROR, "deko3d: command memory failed");
        return false;
    }
    DkCmdBufMaker cmd_maker;
    dkCmdBufMakerDefaults(&cmd_maker, g.device);
    g.cmd = dkCmdBufCreate(&cmd_maker);
    if (!g.cmd) {
        sysLogPrintf(LOG_ERROR, "deko3d: command buffer failed");
        return false;
    }
    dkCmdBufAddMemory(g.cmd, g.cmd_mem, 0, GE_DEKO_CMD_BYTES);

    sysLogPrintf(LOG_NOTE, "deko3d: queue create");
    DkQueueMaker queue_maker;
    dkQueueMakerDefaults(&queue_maker, g.device);
    queue_maker.flags = DkQueueFlags_Graphics | DkQueueFlags_DisableZcull;
    queue_maker.commandMemorySize = DK_QUEUE_MIN_CMDMEM_SIZE;
    queue_maker.perWarpScratchMemorySize = 0;
    g.queue = dkQueueCreate(&queue_maker);
    if (!g.queue) {
        sysLogPrintf(LOG_ERROR, "deko3d: queue creation failed");
        return false;
    }
    gpu_ready = true;
    sysLogPrintf(LOG_NOTE, "deko3d: device/swapchain/queue ready %ux%u", width, height);
    return true;
}

static void deko_apply_states(void)
{
    DkViewport viewport = {(float)g.vp_x, (float)g.vp_y, (float)g.vp_w, (float)g.vp_h, 0.0f, 1.0f};
    /* Fast3D can pass scissor rectangles that extend past the window (negative
     * x/y, oversized width). DkScissor is unsigned, so clamp or every pixel is
     * rejected. */
    int sx0 = g.sc_x;
    int sy0 = g.sc_y;
    int sx1 = g.sc_x + g.sc_w;
    int sy1 = g.sc_y + g.sc_h;
    if (sx0 < 0) sx0 = 0;
    if (sy0 < 0) sy0 = 0;
    if (sx1 > (int)g.width) sx1 = (int)g.width;
    if (sy1 > (int)g.height) sy1 = (int)g.height;
    DkScissor scissor = {(uint32_t)sx0, (uint32_t)sy0,
                         (uint32_t)(sx1 > sx0 ? sx1 - sx0 : 0),
                         (uint32_t)(sy1 > sy0 ? sy1 - sy0 : 0)};
    dkCmdBufSetViewports(g.cmd, 0, &viewport, 1);
    dkCmdBufSetScissors(g.cmd, 0, &scissor, 1);

    DkDepthStencilState depth;
    dkDepthStencilStateDefaults(&depth);
    depth.depthTestEnable = g.depth_test;
    depth.depthWriteEnable = g.depth_write;
    depth.depthCompareOp = DkCompareOp_Lequal;
    dkCmdBufBindDepthStencilState(g.cmd, &depth);

    DkColorState color;
    dkColorStateDefaults(&color);
    if (g.alpha) {
        dkColorStateSetBlendEnable(&color, 0, true);
    }
    dkCmdBufBindColorState(g.cmd, &color);
    DkBlendState blend;
    dkBlendStateDefaults(&blend);
    if (g.modulate) {
        dkBlendStateSetFactors(&blend, DkBlendFactor_DstColor, DkBlendFactor_Zero,
                               DkBlendFactor_One, DkBlendFactor_Zero);
    }
    dkCmdBufBindBlendState(g.cmd, 0, &blend);
    DkColorWriteState write;
    dkColorWriteStateDefaults(&write);
    dkCmdBufBindColorWriteState(g.cmd, &write);
    DkRasterizerState raster;
    dkRasterizerStateDefaults(&raster);
    /* The RDP submits both windings; do not let deko cull them. */
    raster.cullMode = DkFace_None;
    dkCmdBufBindRasterizerState(g.cmd, &raster);
}

static DekoProgram *deko_lookup_program(uint64_t id0, uint32_t id1)
{
    for (unsigned i = 0; i < g.programs; ++i) {
        if (g.program[i].id0 == id0 && g.program[i].id1 == id1) {
            return &g.program[i];
        }
    }
    return nullptr;
}

static struct ShaderProgram *deko_as_handle(DekoProgram *program)
{
    return reinterpret_cast<struct ShaderProgram *>(program);
}

static DekoProgram *deko_from_handle(struct ShaderProgram *handle)
{
    return reinterpret_cast<DekoProgram *>(handle);
}

static struct ShaderProgram *deko_create_shader(uint64_t id0, uint32_t id1)
{
    DekoProgram *existing = deko_lookup_program(id0, id1);
    if (existing) {
        return deko_as_handle(existing);
    }
    if (g.programs >= GE_DEKO_MAX_PROGRAMS) {
        sysLogPrintf(LOG_WARNING, "deko3d: shader pool full (%u)", g.programs);
        return nullptr;
    }
    CCFeatures features = {};
    gfx_cc_get_features(id0, id1, &features);
    DekoProgram *program = &g.program[g.programs++];
    program->id0 = id0;
    program->id1 = id1;
    program->num_inputs = (uint8_t)features.num_inputs;
    program->used_textures[0] = features.used_textures[0];
    program->used_textures[1] = features.used_textures[1];
    program->fogtex = (id0 == GE_F3D_FOGTEX_RGB3_ID0 && id1 == GE_F3D_FOGTEX_RGB3_ID1);
    program->env2tex = !program->fogtex && features.used_textures[0] &&
                       features.used_textures[1] && features.num_inputs >= 2;
    program->flat = !features.used_textures[0] && !features.used_textures[1] &&
                    features.num_inputs == 1 && features.opt_alpha;
    program->alpha_combiner = program->env2tex && features.opt_alpha &&
        features.color_alpha_same[1] &&
        !(features.do_single[1][1] && features.c[1][1][3] == SHADER_1);
    program->texedge = features.opt_texture_edge;
    program->alpha_threshold = features.opt_alpha_threshold;
    /* src/game/sky.c: (SHADE, ENVIRONMENT, TEXEL0, ENVIRONMENT) in both
     * cycles, one texture, no fog. Fast3D numbers SHADE as input 1 and
     * ENVIRONMENT as input 2. The raw-texture fallback ignores the env/shade
     * modulation, so the cloud tile needs this dedicated combiner. */
    program->sky = features.used_textures[0] && !features.used_textures[1] &&
                   features.num_inputs == 2 &&
                   features.c[0][0][0] == SHADER_INPUT_1 &&
                   features.c[0][0][1] == SHADER_INPUT_2 &&
                   features.c[0][0][2] == SHADER_TEXEL0 &&
                   features.c[0][0][3] == SHADER_INPUT_2;
    program->supported = (id0 == 0x1000u && id1 == 0u) || program->fogtex ||
                         program->env2tex || program->flat || program->sky;
    if (!program->supported) {
        if (features.used_textures[0] && !features.used_textures[1] && features.num_inputs >= 1) {
            program->tex0_fallback = true;
        } else if (features.used_textures[0] && features.used_textures[1]) {
            program->texmix_fallback = true;
        }
        program->supported = program->tex0_fallback || program->texmix_fallback;
    }
    if (g.programs <= 8 || program->supported) {
        sysLogPrintf(LOG_NOTE, "deko3d: shader %016llx:%08x inputs=%u tex=%u:%u fogtex=%d env=%d flat=%d ac=%d sky=%d supported=%d",
                     (unsigned long long)id0, id1, program->num_inputs,
                     program->used_textures[0] ? 1u : 0u, program->used_textures[1] ? 1u : 0u,
                     program->fogtex ? 1 : 0, program->env2tex ? 1 : 0,
                     program->flat ? 1 : 0, program->alpha_combiner ? 1 : 0,
                     program->sky ? 1 : 0, program->supported ? 1 : 0);
    }
    return deko_as_handle(program);
}

/* ------------------------------------------------------------------------ */
/* GfxRenderingAPI                                                          */
/* ------------------------------------------------------------------------ */

static const char *deko_api_name(void) { return "deko3d (Switch stage 1)"; }
static int deko_max_texture(void) { return 1024; }
static GfxClipParameters deko_clip(void) { return {true, false}; }

static void deko_unload_shader(struct ShaderProgram *program)
{
    (void)program;
    g.current = nullptr;
}

static void deko_load_shader_program(struct ShaderProgram *program)
{
    g.current = deko_from_handle(program);
}

static struct ShaderProgram *deko_lookup_shader(uint64_t id0, uint32_t id1)
{
    DekoProgram *program = deko_lookup_program(id0, id1);
    return program ? deko_as_handle(program) : nullptr;
}

static void deko_shader_info(struct ShaderProgram *program, uint8_t *num_inputs, bool used_textures[2])
{
    DekoProgram *p = deko_from_handle(program);
    if (num_inputs) {
        *num_inputs = p ? p->num_inputs : 1;
    }
    if (used_textures) {
        used_textures[0] = p ? p->used_textures[0] : false;
        used_textures[1] = p ? p->used_textures[1] : false;
    }
}

static void deko_clear_shaders(void) { g.current = nullptr; }

static DkWrapMode deko_wrap_mode(uint32_t mode)
{
    switch (mode & 3u) {
    case 1: return DkWrapMode_MirroredRepeat;
    case 2: return DkWrapMode_ClampToEdge;
    case 3: return DkWrapMode_MirrorClampToEdge;
    default: return DkWrapMode_Repeat;
    }
}

static uint32_t deko_new_texture(void)
{
    if (g.next_texture >= GE_DEKO_MAX_TEXTURES) {
        return 0;
    }
    const uint32_t id = ++g.next_texture;
    g.upload_id = id;
    return id;
}

static void deko_select_texture(int tile, uint32_t texture_id, bool linear_filter)
{
    (void)linear_filter;
    if (tile >= 0 && tile < 2 && texture_id > 0 && texture_id <= GE_DEKO_MAX_TEXTURES) {
        g.selected_id[tile] = texture_id;
        /* Fast3D's API uploads into the texture most recently passed to
         * select_texture (the GL backend binds it before importing). The
         * engine also recycles evicted ids without calling new_texture, so
         * keying the upload on new_texture alone would write the image into
         * a stale id and leave the selected texture holding old contents. */
        g.upload_id = texture_id;
    }
}

static uint32_t deko_mip_count(uint32_t width, uint32_t height)
{
    /* The descriptor stores at most 16 mip levels. */
    uint32_t levels = 1;
    while ((width > 1 || height > 1) && levels < 16) {
        width = width > 1 ? width >> 1 : 1;
        height = height > 1 ? height >> 1 : 1;
        ++levels;
    }
    return levels;
}

static void deko_retire_texture_mem(DkMemBlock mem)
{
    if (!mem) {
        return;
    }
    /* The command buffer is recorded ahead of submission, so a texture that
     * is re-uploaded or evicted mid-frame can still be referenced by queued
     * copy/blit/draw commands. Keep its memory alive until the next frame has
     * waited out the previous submission. */
    if (g.retired_count < (uint32_t)(sizeof(g.retired_mem) / sizeof(g.retired_mem[0]))) {
        g.retired_mem[g.retired_count++] = mem;
    } else {
        dkMemBlockDestroy(mem);
    }
}

static void deko_upload_texture(const uint8_t *rgba32, uint32_t width, uint32_t height, bool gen_mipmaps)
{
    const uint32_t id = g.upload_id;
    if (!rgba32 || !width || !height || id == 0 || id > GE_DEKO_MAX_TEXTURES) {
        return;
    }
    DekoTexture &tex = g.textures[id - 1];
    if (tex.mem) {
        deko_retire_texture_mem(tex.mem);
        tex.mem = nullptr;
        tex.ready = false;
    }
    tex.mip_levels = 0;
    /* Pitch-linear images cannot carry mipmaps (deko3d rejects
     * mipLevels > 1), so mipmapped textures use the default block-linear
     * layout. Fast3D asks for mipmaps on many world textures; without them
     * the minified grating and cliffs alias badly where GL's mip chain is
     * smooth. Each level is box-filtered on the CPU into the staging buffer
     * and copied into the image by the copy engine (the same path as the
     * base level); GPU blits are avoided because their tiled destination
     * came out uninitialised/garbled under Eden. */
    const uint32_t mip_count = gen_mipmaps ? deko_mip_count(width, height) : 1;
    const uint32_t pitch_stride = (width * 4u + DK_IMAGE_LINEAR_STRIDE_ALIGNMENT - 1u)
                                & ~(DK_IMAGE_LINEAR_STRIDE_ALIGNMENT - 1u);
    uint32_t level_w[16] = {0}, level_h[16] = {0}, level_stride[16] = {0};
    uint64_t level_off[16] = {0};
    uint64_t staging_total = 0;
    bool tiled = false;
    uint32_t staging_base = 0;
    if (mip_count > 1 && g.staging_mem && g.in_frame) {
        uint64_t total = 0;
        uint32_t w = width, h = height;
        for (uint32_t level = 0; level < mip_count; ++level) {
            level_w[level] = w;
            level_h[level] = h;
            level_stride[level] = (w * 4u + DK_IMAGE_LINEAR_STRIDE_ALIGNMENT - 1u)
                                & ~(DK_IMAGE_LINEAR_STRIDE_ALIGNMENT - 1u);
            const uint32_t aligned = (uint32_t)((total + 31u) & ~31u);
            level_off[level] = aligned;
            total = aligned + (uint64_t)level_stride[level] * h;
            w = w > 1 ? w >> 1 : 1;
            h = h > 1 ? h >> 1 : 1;
        }
        const uint32_t base = (g.staging_used + 31u) & ~31u;
        if ((uint64_t)base + total <= GE_DEKO_STAGING_BYTES) {
            tiled = true;
            staging_base = base;
            staging_total = total;
        }
    }

    DkImageLayoutMaker lm;
    dkImageLayoutMakerDefaults(&lm, g.device);
    lm.format = DkImageFormat_RGBA8_Unorm;
    lm.dimensions[0] = width;
    lm.dimensions[1] = height;
    if (tiled) {
        lm.mipLevels = mip_count;
    } else {
        lm.flags = DkImageFlags_PitchLinear;
        lm.mipLevels = 1;
        lm.pitchStride = pitch_stride;
    }
    DkImageLayout layout;
    dkImageLayoutInitialize(&layout, &lm);
    uint64_t size = dkImageLayoutGetSize(&layout);
    const uint32_t align = dkImageLayoutGetAlignment(&layout);
    size = (size + align - 1u) & ~(uint64_t)(align - 1u);
    size = (size + DK_MEMBLOCK_ALIGNMENT - 1u) & ~(uint64_t)(DK_MEMBLOCK_ALIGNMENT - 1u);
    DkMemBlockMaker mm;
    dkMemBlockMakerDefaults(&mm, g.device, (uint32_t)size);
    mm.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image;
    tex.mem = dkMemBlockCreate(&mm);
    if (!tex.mem) {
        sysLogPrintf(LOG_ERROR, "deko3d: texture memory failed %ux%u", width, height);
        return;
    }
    uint8_t *cpu = (uint8_t *)dkMemBlockGetCpuAddr(tex.mem);
    if (!cpu) {
        dkMemBlockDestroy(tex.mem);
        tex.mem = nullptr;
        return;
    }
    if (tiled) {
        uint8_t *staging = (uint8_t *)dkMemBlockGetCpuAddr(g.staging_mem) + staging_base;
        for (uint32_t row = 0; row < height; ++row) {
            memcpy(staging + (size_t)row * level_stride[0],
                   rgba32 + (size_t)row * width * 4u, (size_t)width * 4u);
        }
        dkImageInitialize(&tex.image, &layout, tex.mem, 0);
        dkImageViewDefaults(&tex.view, &tex.image);
        for (uint32_t level = 0; level < mip_count; ++level) {
            if (level > 0) {
                const uint8_t *src = staging + level_off[level - 1];
                uint8_t *dst = staging + level_off[level];
                const uint32_t sw = level_stride[level - 1];
                const uint32_t pw = level_w[level - 1], ph = level_h[level - 1];
                const uint32_t mw = level_w[level], mh = level_h[level];
                const uint32_t dw = level_stride[level];
                for (uint32_t y = 0; y < mh; ++y) {
                    for (uint32_t x = 0; x < mw; ++x) {
                        uint32_t acc[4] = {0, 0, 0, 0}, n = 0;
                        for (uint32_t dy = 0; dy < 2; ++dy) {
                            const uint32_t sy = y * 2u + dy;
                            if (sy >= ph) continue;
                            for (uint32_t dx = 0; dx < 2; ++dx) {
                                const uint32_t sx = x * 2u + dx;
                                if (sx >= pw) continue;
                                const uint8_t *p = src + (size_t)sy * sw + (size_t)sx * 4u;
                                for (int c = 0; c < 4; ++c) acc[c] += p[c];
                                ++n;
                            }
                        }
                        uint8_t *q = dst + (size_t)y * dw + (size_t)x * 4u;
                        for (int c = 0; c < 4; ++c) q[c] = (uint8_t)(acc[c] / (n ? n : 1));
                    }
                }
            }
            DkImageView level_view = tex.view;
            level_view.mipLevelOffset = (uint8_t)level;
            level_view.mipLevelCount = 1;
            DkImageRect rect = {0, 0, 0, level_w[level], level_h[level], 1};
            DkCopyBuf level_buf = {
                dkMemBlockGetGpuAddr(g.staging_mem) + staging_base + (uint32_t)level_off[level],
                level_stride[level],
                (uint32_t)((uint64_t)level_stride[level] * level_h[level])
            };
            dkCmdBufCopyBufferToImage(g.cmd, &level_buf, &level_view, &rect, 0);
        }
        g.staging_used = staging_base + (uint32_t)staging_total;
        tex.mip_levels = mip_count;
    } else {
        for (uint32_t row = 0; row < height; ++row) {
            memcpy(cpu + (size_t)row * pitch_stride,
                   rgba32 + (size_t)row * width * 4u, (size_t)width * 4u);
        }
        dkImageInitialize(&tex.image, &layout, tex.mem, 0);
        dkImageViewDefaults(&tex.view, &tex.image);
        tex.mip_levels = 1;
    }
    tex.width = width;
    tex.height = height;
    tex.ready = true;
    dkImageDescriptorInitialize(&g.image_desc[id - 1], &tex.view, false, false);
    static unsigned logged;
    if (logged++ < 8) {
        sysLogPrintf(LOG_NOTE, "deko3d: texture %u uploaded %ux%u mips=%u%s", id, width, height,
                     tex.mip_levels, tiled ? " tiled" : " pitch");
    }
}

static void deko_sampler_parameters(int sampler, bool linear_filter, uint32_t cms, uint32_t cmt, bool mipmaps)
{
    (void)mipmaps;
    /* Sampler state is per texture, like GL's glTexParameteri. Fast3D only
     * emits a state change when the *texture's* cached state differs, so a
     * sampler shared by a whole unit would keep the last draw's wrap/filter
     * and clamp the sky's UVs (the flat blue sky). Key the descriptor by the
     * texture that select_texture just bound on this unit instead. */
    const uint32_t texture_id = g.selected_id[sampler & 1];
    if (texture_id == 0 || texture_id > GE_DEKO_MAX_TEXTURES) {
        return;
    }
    const DekoTexture &tex = g.textures[texture_id - 1];
    const bool has_mips = tex.ready && tex.mip_levels > 1;
    DkSampler s;
    dkSamplerDefaults(&s);
    s.minFilter = linear_filter ? DkFilter_Linear : DkFilter_Nearest;
    s.magFilter = linear_filter ? DkFilter_Linear : DkFilter_Nearest;
    s.mipFilter = has_mips ? DkMipFilter_Linear : DkMipFilter_None;
    s.lodClampMax = has_mips ? (float)(tex.mip_levels - 1) : 0.0f;
    s.wrapMode[0] = deko_wrap_mode(cms);
    s.wrapMode[1] = deko_wrap_mode(cmt);
    s.wrapMode[2] = DkWrapMode_Repeat;
    dkSamplerDescriptorInitialize(&g.sampler_desc[texture_id - 1], &s);
}

static void deko_depth_mode(bool test, bool update, bool compare, bool prim, uint16_t zmode)
{
    (void)compare;
    (void)prim;
    (void)zmode;
    g.depth_test = test;
    g.depth_write = update;
}

static void deko_depth_range(float near_value, float far_value)
{
    (void)near_value;
    (void)far_value;
}

static void deko_viewport(int x, int y, int width, int height)
{
    static unsigned logged;
    if (logged++ < 4) {
        sysLogPrintf(LOG_NOTE, "deko3d viewport %d,%d %dx%d", x, y, width, height);
    }
    g.vp_x = x;
    g.vp_y = y;
    g.vp_w = width;
    g.vp_h = height;
    if (g.in_frame) {
        deko_apply_states();
    }
}

static void deko_scissor(int x, int y, int width, int height)
{
    static unsigned logged;
    if (logged++ < 4) {
        sysLogPrintf(LOG_NOTE, "deko3d scissor %d,%d %dx%d", x, y, width, height);
    }
    g.sc_x = x;
    g.sc_y = y;
    g.sc_w = width;
    g.sc_h = height;
    if (g.in_frame) {
        deko_apply_states();
    }
}

static void deko_use_alpha(bool use, bool modulate)
{
    g.alpha = use;
    g.modulate = modulate;
    if (g.in_frame) {
        deko_apply_states();
    }
}

static void deko_stage_vertex(const void *data, size_t bytes, uint32_t stride,
                              uint32_t rgb_offset, uint32_t vertices)
{
    const size_t aligned = (g.vertex_used + 3u) & ~(size_t)3u;
    if (aligned + bytes > GE_DEKO_VERTEX_BYTES) {
        g.skipped++;
        return;
    }
    uint8_t *dst = (uint8_t *)dkMemBlockGetCpuAddr(g.vertex_mem) + aligned;
    memcpy(dst, data, bytes);
    const DkGpuAddr gpu = dkMemBlockGetGpuAddr(g.vertex_mem) + aligned;
    DkBufExtents extents = {gpu, bytes};
    dkCmdBufBindVtxBuffers(g.cmd, 0, &extents, 1);
    DkVtxAttribState attribs[2] = {
        {0, 0, 0, DkVtxAttribSize_4x32, DkVtxAttribType_Float, 0},
        {0, 0, rgb_offset, DkVtxAttribSize_3x32, DkVtxAttribType_Float, 0},
    };
    DkVtxBufferState buffers[1] = {{stride, 0}};
    dkCmdBufBindVtxAttribState(g.cmd, attribs, 2);
    dkCmdBufBindVtxBufferState(g.cmd, buffers, 1);
    dkCmdBufDraw(g.cmd, DkPrimitive_Triangles, vertices, 1, 0, 0);
    g.vertex_used = aligned + bytes;
    g.draws++;
}

static void deko_stage_fogtex(const ge_fast3d_fogtex_vertex *data, size_t vertices)
{
    const size_t bytes = vertices * sizeof(*data);
    const size_t aligned = (g.vertex_used + 3u) & ~(size_t)3u;
    if (aligned + bytes > GE_DEKO_VERTEX_BYTES) {
        g.skipped++;
        return;
    }
    uint8_t *dst = (uint8_t *)dkMemBlockGetCpuAddr(g.vertex_mem) + aligned;
    memcpy(dst, data, bytes);
    const DkGpuAddr gpu = dkMemBlockGetGpuAddr(g.vertex_mem) + aligned;
    DkBufExtents extents = {gpu, bytes};
    dkCmdBufBindVtxBuffers(g.cmd, 0, &extents, 1);
    const uint32_t stride = (uint32_t)sizeof(ge_fast3d_fogtex_vertex);
    DkVtxAttribState attribs[6] = {
        {0, 0, (uint32_t)offsetof(ge_fast3d_fogtex_vertex, position), DkVtxAttribSize_4x32, DkVtxAttribType_Float, 0},
        {0, 0, (uint32_t)offsetof(ge_fast3d_fogtex_vertex, texcoord), DkVtxAttribSize_2x32, DkVtxAttribType_Float, 0},
        {0, 0, (uint32_t)offsetof(ge_fast3d_fogtex_vertex, fog), DkVtxAttribSize_4x32, DkVtxAttribType_Float, 0},
        {0, 0, (uint32_t)offsetof(ge_fast3d_fogtex_vertex, input_rgb) + 0u, DkVtxAttribSize_3x32, DkVtxAttribType_Float, 0},
        {0, 0, (uint32_t)offsetof(ge_fast3d_fogtex_vertex, input_rgb) + 12u, DkVtxAttribSize_3x32, DkVtxAttribType_Float, 0},
        {0, 0, (uint32_t)offsetof(ge_fast3d_fogtex_vertex, input_rgb) + 24u, DkVtxAttribSize_3x32, DkVtxAttribType_Float, 0},
    };
    DkVtxBufferState buffers[1] = {{stride, 0}};
    dkCmdBufBindVtxAttribState(g.cmd, attribs, 6);
    dkCmdBufBindVtxBufferState(g.cmd, buffers, 1);
    dkCmdBufDraw(g.cmd, DkPrimitive_Triangles, (uint32_t)vertices, 1, 0, 0);
    g.vertex_used = aligned + bytes;
    g.draws++;
}

static void deko_stage_generic(const ge_fast3d_generic_vertex *data, size_t vertices)
{
    const size_t bytes = vertices * sizeof(*data);
    const size_t aligned = (g.vertex_used + 3u) & ~(size_t)3u;
    if (aligned + bytes > GE_DEKO_VERTEX_BYTES) {
        g.skipped++;
        return;
    }
    uint8_t *dst = (uint8_t *)dkMemBlockGetCpuAddr(g.vertex_mem) + aligned;
    memcpy(dst, data, bytes);
    const DkGpuAddr gpu = dkMemBlockGetGpuAddr(g.vertex_mem) + aligned;
    DkBufExtents extents = {gpu, bytes};
    dkCmdBufBindVtxBuffers(g.cmd, 0, &extents, 1);
    const uint32_t stride = (uint32_t)sizeof(ge_fast3d_generic_vertex);
    const uint32_t tex_off = (uint32_t)offsetof(ge_fast3d_generic_vertex, texcoord);
    const uint32_t clamp_off = (uint32_t)offsetof(ge_fast3d_generic_vertex, clamp);
    const uint32_t in_off = (uint32_t)offsetof(ge_fast3d_generic_vertex, input_rgb);
    DkVtxAttribState attribs[9] = {
        {0, 0, (uint32_t)offsetof(ge_fast3d_generic_vertex, position), DkVtxAttribSize_4x32, DkVtxAttribType_Float, 0},
        {0, 0, tex_off, DkVtxAttribSize_2x32, DkVtxAttribType_Float, 0},
        {0, 0, tex_off + 8u, DkVtxAttribSize_2x32, DkVtxAttribType_Float, 0},
        {0, 0, (uint32_t)offsetof(ge_fast3d_generic_vertex, fog), DkVtxAttribSize_4x32, DkVtxAttribType_Float, 0},
        {0, 0, in_off, DkVtxAttribSize_4x32, DkVtxAttribType_Float, 0},
        {0, 0, in_off + 16u, DkVtxAttribSize_4x32, DkVtxAttribType_Float, 0},
        {0, 0, in_off + 32u, DkVtxAttribSize_4x32, DkVtxAttribType_Float, 0},
        {0, 0, clamp_off, DkVtxAttribSize_2x32, DkVtxAttribType_Float, 0},
        {0, 0, clamp_off + 8u, DkVtxAttribSize_2x32, DkVtxAttribType_Float, 0},
    };
    DkVtxBufferState buffers[1] = {{stride, 0}};
    dkCmdBufBindVtxAttribState(g.cmd, attribs, 9);
    dkCmdBufBindVtxBufferState(g.cmd, buffers, 1);
    dkCmdBufDraw(g.cmd, DkPrimitive_Triangles, (uint32_t)vertices, 1, 0, 0);
    g.vertex_used = aligned + bytes;
    g.draws++;
}

static void deko_skip_draw(const char *why)
{
    static unsigned logged;
    /* draw_triangles fires before the first shader is bound; that is normal
     * startup behaviour and would otherwise drown the interesting skips. */
    if (strcmp(why, "no-current") != 0 && logged++ < 24) {
        sysLogPrintf(LOG_NOTE, "deko3d skip: %s profile=%016llx:%08x texture0=%u ready=%d",
                     why,
                     g.current ? (unsigned long long)g.current->id0 : 0ull,
                     g.current ? g.current->id1 : 0u,
                     g.selected_id[0],
                     (g.selected_id[0] > 0 && g.selected_id[0] <= GE_DEKO_MAX_TEXTURES)
                         ? (g.textures[g.selected_id[0] - 1].ready ? 1 : 0) : -1);
    }
    g.skipped++;
}

static void deko_draw_triangles(float *vbo, size_t vbo_len, size_t triangles)
{
    static unsigned debug_draws;
    if (debug_draws < 10) {
        debug_draws++;
        sysLogPrintf(LOG_NOTE, "deko3d draw: frame=%d current=%p id=%016llx:%08x supported=%d tris=%zu len=%zu",
                     g.in_frame ? 1 : 0, (void *)g.current,
                     g.current ? (unsigned long long)g.current->id0 : 0ull,
                     g.current ? g.current->id1 : 0u,
                     g.current ? (g.current->supported ? 1 : 0) : -1,
                     triangles, vbo_len);
    }
    if (!g.in_frame || !g.current || !g.current->supported || !triangles || !vbo) {
        deko_skip_draw(!g.in_frame ? "not-in-frame" : (!g.current ? "no-current" : (!g.current->supported ? "unsupported" : "empty")));
        return;
    }
    const size_t vertices = triangles * 3u;
    if (g.current->fogtex) {
        ge_fast3d_profile profile = {3, 1, 0, 1, 0, g.current->id0, g.current->id1};
        size_t written = 0;
        ge_fast3d_fogtex_vertex *scratch = (ge_fast3d_fogtex_vertex *)malloc(vertices * sizeof(*scratch));
        if (!scratch) {
            g.skipped++;
            return;
        }
        if (ge_fast3d_unpack_fogtex_rgb3(vbo, vbo_len, triangles, &profile, scratch,
                                         vertices, &written) != GE_F3D_OK ||
            written != vertices) {
            static unsigned logged_bad;
            if (logged_bad++ < 3) {
                sysLogPrintf(LOG_WARNING, "deko3d fogtex unpack failed len=%zu tris=%zu", vbo_len, triangles);
            }
            free(scratch);
            g.skipped++;
            return;
        }
        {
            static unsigned logged_ok;
            if (logged_ok++ < 2) {
                sysLogPrintf(LOG_NOTE, "deko3d fogtex draw verts=%zu first=(%.3f,%.3f,%.3f,%.3f) rgb=(%.3f,%.3f,%.3f) vp=%d,%d,%dx%d sc=%d,%d,%dx%d",
                             written, scratch[0].position[0], scratch[0].position[1],
                             scratch[0].position[2], scratch[0].position[3],
                             scratch[0].input_rgb[0][0], scratch[0].input_rgb[0][1],
                             scratch[0].input_rgb[0][2],
                             g.vp_x, g.vp_y, g.vp_w, g.vp_h,
                             g.sc_x, g.sc_y, g.sc_w, g.sc_h);
            }
        }
        DkShader const *shaders[2] = {&g.fogtex_vsh, &g.fogtex_fsh};
        dkCmdBufBindShaders(g.cmd, DkStageFlag_GraphicsMask, shaders, 2);
        const uint32_t texture_id = g.selected_id[0];
        if (texture_id == 0 || texture_id > GE_DEKO_MAX_TEXTURES ||
            !g.textures[texture_id - 1].ready) {
            free(scratch);
            deko_skip_draw("fogtex-texture-not-ready");
            return;
        }
        dkCmdBufBindTexture(g.cmd, DkStage_Fragment, 0,
                            dkMakeTextureHandle(texture_id - 1, texture_id - 1));
        deko_stage_fogtex(scratch, written);
        free(scratch);
        return;
    }
    if (g.current->sky) {
        ge_fast3d_profile profile = {2, 1, 0, 0, 0, g.current->id0, g.current->id1};
        size_t written = 0;
        ge_fast3d_generic_vertex *scratch =
            (ge_fast3d_generic_vertex *)malloc(vertices * sizeof(*scratch));
        if (!scratch) {
            g.skipped++;
            return;
        }
        if (ge_fast3d_unpack_generic(vbo, vbo_len, triangles, &profile, scratch,
                                     vertices, &written) != GE_F3D_OK ||
            written != vertices) {
            free(scratch);
            g.skipped++;
            return;
        }
        const uint32_t t0 = g.selected_id[0];
        if (t0 == 0 || t0 > GE_DEKO_MAX_TEXTURES || !g.textures[t0 - 1].ready) {
            free(scratch);
            deko_skip_draw("sky-texture-not-ready");
            return;
        }
        static unsigned logged_sky;
        if (logged_sky++ < 2) {
            sysLogPrintf(LOG_NOTE, "deko3d sky draw verts=%zu tex=%u shade=(%.3f,%.3f,%.3f) env=(%.3f,%.3f,%.3f) uv=(%.3f,%.3f)",
                         written, t0,
                         scratch[0].input_rgb[0][0], scratch[0].input_rgb[0][1],
                         scratch[0].input_rgb[0][2],
                         scratch[0].input_rgb[1][0], scratch[0].input_rgb[1][1],
                         scratch[0].input_rgb[1][2],
                         scratch[0].texcoord[0][0], scratch[0].texcoord[0][1]);
        }
        DkShader const *shaders[2] = {&g.env_vsh, &g.sky_fsh};
        dkCmdBufBindShaders(g.cmd, DkStageFlag_GraphicsMask, shaders, 2);
        dkCmdBufBindTexture(g.cmd, DkStage_Fragment, 0, dkMakeTextureHandle(t0 - 1, t0 - 1));
        deko_stage_generic(scratch, written);
        free(scratch);
        return;
    }
    if (g.current->tex0_fallback || g.current->texmix_fallback) {
        ge_fast3d_profile profile = {
            g.current->num_inputs,
            (unsigned)((g.current->used_textures[0] ? 1u : 0u) | (g.current->used_textures[1] ? 2u : 0u)),
            (g.current->id1 & SHADER_OPT_ALPHA) ? 1u : 0u,
            (g.current->id1 & SHADER_OPT_FOG) ? 1u : 0u,
            (g.current->id1 & SHADER_OPT_GRAYSCALE) ? 1u : 0u,
            g.current->id0, g.current->id1
        };
        size_t written = 0;
        ge_fast3d_generic_vertex *scratch =
            (ge_fast3d_generic_vertex *)malloc(vertices * sizeof(*scratch));
        if (!scratch) {
            g.skipped++;
            return;
        }
        if (ge_fast3d_unpack_generic(vbo, vbo_len, triangles, &profile, scratch,
                                     vertices, &written) != GE_F3D_OK ||
            written != vertices) {
            free(scratch);
            g.skipped++;
            return;
        }
        uint32_t t0 = g.selected_id[0];
        uint32_t t1 = g.selected_id[1];
        if (t0 == 0 || t0 > GE_DEKO_MAX_TEXTURES || !g.textures[t0 - 1].ready) {
            free(scratch);
            deko_skip_draw("tex0-texture-not-ready");
            return;
        }
        if (g.current->texmix_fallback &&
            (t1 == 0 || t1 > GE_DEKO_MAX_TEXTURES || !g.textures[t1 - 1].ready)) {
            t1 = t0;
        }
        DkShader const *shaders[2] = {&g.env_vsh,
            g.current->texmix_fallback ? &g.texmix_fsh : &g.tex0_fsh};
        dkCmdBufBindShaders(g.cmd, DkStageFlag_GraphicsMask, shaders, 2);
        dkCmdBufBindTexture(g.cmd, DkStage_Fragment, 0, dkMakeTextureHandle(t0 - 1, t0 - 1));
        if (g.current->texmix_fallback) {
            dkCmdBufBindTexture(g.cmd, DkStage_Fragment, 1, dkMakeTextureHandle(t1 - 1, t1 - 1));
        }
        deko_stage_generic(scratch, written);
        free(scratch);
        return;
    }
    if (g.current->flat) {
        ge_fast3d_profile profile = {1, 0, 1, 1, 0, g.current->id0, g.current->id1};
        size_t written = 0;
        ge_fast3d_generic_vertex *scratch =
            (ge_fast3d_generic_vertex *)malloc(vertices * sizeof(*scratch));
        if (!scratch) {
            g.skipped++;
            return;
        }
        if (ge_fast3d_unpack_generic(vbo, vbo_len, triangles, &profile, scratch,
                                     vertices, &written) != GE_F3D_OK ||
            written != vertices) {
            free(scratch);
            deko_skip_draw("flat-unpack");
            return;
        }
        DkShader const *shaders[2] = {&g.flat_vsh, &g.flat_fsh};
        dkCmdBufBindShaders(g.cmd, DkStageFlag_GraphicsMask, shaders, 2);
        deko_stage_generic(scratch, written);
        free(scratch);
        return;
    }
    if (g.current->env2tex) {
        ge_fast3d_profile profile = {
            g.current->num_inputs,
            (unsigned)((g.current->used_textures[0] ? 1u : 0u) | (g.current->used_textures[1] ? 2u : 0u)),
            (g.current->id1 & SHADER_OPT_ALPHA) ? 1u : 0u,
            (g.current->id1 & SHADER_OPT_FOG) ? 1u : 0u,
            (g.current->id1 & SHADER_OPT_GRAYSCALE) ? 1u : 0u,
            g.current->id0, g.current->id1
        };
        size_t written = 0;
        ge_fast3d_generic_vertex *scratch =
            (ge_fast3d_generic_vertex *)malloc(vertices * sizeof(*scratch));
        if (!scratch) {
            g.skipped++;
            return;
        }
        if (ge_fast3d_unpack_generic(vbo, vbo_len, triangles, &profile, scratch,
                                     vertices, &written) != GE_F3D_OK ||
            written != vertices) {
            free(scratch);
            g.skipped++;
            return;
        }
        const uint32_t t0 = g.selected_id[0];
        const uint32_t t1 = g.selected_id[1];
        if (!t0 || !t1 || t0 > GE_DEKO_MAX_TEXTURES || t1 > GE_DEKO_MAX_TEXTURES ||
            !g.textures[t0 - 1].ready || !g.textures[t1 - 1].ready) {
            free(scratch);
            static unsigned logged_env_skip;
            if (logged_env_skip++ < 24) {
                sysLogPrintf(LOG_NOTE, "deko3d skip: env-texture-not-ready t0=%u ready0=%d t1=%u ready1=%d profile=%016llx:%08x",
                             t0, (t0 > 0 && t0 <= GE_DEKO_MAX_TEXTURES) ? (g.textures[t0-1].ready ? 1 : 0) : -1,
                             t1, (t1 > 0 && t1 <= GE_DEKO_MAX_TEXTURES) ? (g.textures[t1-1].ready ? 1 : 0) : -1,
                             (unsigned long long)g.current->id0, g.current->id1);
            }
            g.skipped++;
            return;
        }
        DkShader const *shaders[2] = {&g.env_vsh, &g.env_fsh};
        if (g.current->alpha_combiner) {
            if (g.current->alpha_threshold) {
                shaders[1] = &g.env_thresh_fsh;
            } else if (g.current->texedge) {
                shaders[1] = &g.env_edge_fsh;
            } else {
                shaders[1] = &g.env_alpha_fsh;
            }
        }
        dkCmdBufBindShaders(g.cmd, DkStageFlag_GraphicsMask, shaders, 2);
        dkCmdBufBindTexture(g.cmd, DkStage_Fragment, 0, dkMakeTextureHandle(t0 - 1, t0 - 1));
        dkCmdBufBindTexture(g.cmd, DkStage_Fragment, 1, dkMakeTextureHandle(t1 - 1, t1 - 1));
        deko_stage_generic(scratch, written);
        free(scratch);
        return;
    }
    ge_fast3d_profile profile = {1, 0, 0, 0, 0, 0x1000u, 0u};
    size_t written = 0;
    ge_fast3d_vertex *scratch = (ge_fast3d_vertex *)malloc(vertices * sizeof(*scratch));
    if (!scratch) {
        g.skipped++;
        return;
    }
    if (ge_fast3d_unpack_rgb(vbo, vbo_len, triangles, &profile, scratch, vertices,
                             &written) != GE_F3D_OK || written != vertices) {
        free(scratch);
        g.skipped++;
        return;
    }
    DkShader const *shaders[2] = {&g.vsh, &g.fsh};
    dkCmdBufBindShaders(g.cmd, DkStageFlag_GraphicsMask, shaders, 2);
    deko_stage_vertex(scratch, written * sizeof(*scratch), sizeof(*scratch),
                      (uint32_t)offsetof(ge_fast3d_vertex, rgb), (uint32_t)written);
    free(scratch);
}

static void deko_api_init(void)
{
    if (!gpu_ready) {
        deko_gpu_init(1280, 720);
    }
    g.current = nullptr;
    g.in_frame = false;
}

static void deko_api_resize(void) { }

static void deko_api_start_frame(void)
{
    if (!gpu_ready) {
        return;
    }
    dkCmdBufClear(g.cmd);
    g.in_frame = true;
    g.vertex_used = 0;
    /* wm_start_frame already waited out the previous submission, so textures
     * retired last frame and the upload staging buffer are free to reuse. */
    for (uint32_t i = 0; i < g.retired_count; ++i) {
        dkMemBlockDestroy(g.retired_mem[i]);
    }
    g.retired_count = 0;
    g.staging_used = 0;
    g.draws = 0;
    g.skipped = 0;
    dkCmdBufBindImageDescriptorSet(g.cmd, g.image_desc_gpu, GE_DEKO_MAX_TEXTURES);
    dkCmdBufBindSamplerDescriptorSet(g.cmd, g.sampler_desc_gpu, GE_DEKO_MAX_TEXTURES);

    DkImageView color_view;
    dkImageViewDefaults(&color_view, &g.images[g.slot]);
    g.color_view = color_view;
    dkCmdBufBindRenderTarget(g.cmd, &g.color_view, &g.depth_view);
    deko_apply_states();
    dkCmdBufClearColorFloat(g.cmd, 0, DkColorMask_RGBA, 0.04f, 0.05f, 0.08f, 1.0f);
    dkCmdBufClearDepthStencil(g.cmd, true, 1.0f, 0, 0);
}

static void deko_api_end_frame(void)
{
    if (!g.in_frame) {
        return;
    }
    g.frame_cmd = dkCmdBufFinishList(g.cmd);
    g.in_frame = false;
}

static void deko_api_finish_render(void) { }

static int deko_create_framebuffer(void)
{
    static int next = 0;
    return next++;
}

static void deko_update_framebuffer(int fb_id, uint32_t width, uint32_t height, uint32_t msaa,
                                    bool invert_y, bool render_target, bool depth, bool extract)
{
    (void)fb_id; (void)width; (void)height; (void)msaa;
    (void)invert_y; (void)render_target; (void)depth; (void)extract;
}

static bool deko_start_draw_to_framebuffer(int fb_id, float noise_scale)
{
    (void)noise_scale;
    return fb_id == 0 || fb_id == 1;
}

static void deko_copy_framebuffer(int dst, int src, int left, int top, bool flip, bool back)
{
    (void)dst; (void)src; (void)left; (void)top; (void)flip; (void)back;
}

static void deko_clear_framebuffer(bool color, bool depth)
{
    if (!g.in_frame) {
        return;
    }
    if (color) {
        dkCmdBufClearColorFloat(g.cmd, 0, DkColorMask_RGBA, 0.04f, 0.05f, 0.08f, 1.0f);
    }
    if (depth) {
        dkCmdBufClearDepthStencil(g.cmd, true, 1.0f, 0, 0);
    }
}

static void deko_resolve_msaa(int target, int source)
{
    (void)target; (void)source;
}

static void *deko_framebuffer_texture(int fb_id)
{
    (void)fb_id;
    return nullptr;
}

static void deko_select_framebuffer_texture(int fb_id) { (void)fb_id; }
static void deko_delete_texture(uint32_t texture_id)
{
    if (texture_id == 0 || texture_id > GE_DEKO_MAX_TEXTURES) return;
    DekoTexture &tex = g.textures[texture_id - 1];
    if (tex.mem) {
        deko_retire_texture_mem(tex.mem);
        tex.mem = nullptr;
        tex.ready = false;
    }
}
static void deko_set_filter(FilteringMode mode) { (void)mode; }
static FilteringMode deko_get_filter(void) { return FILTER_NONE; }
static void deko_set_mipmap(MipmapFilteringMode mode) { (void)mode; }
static void deko_set_anisotropy(int level) { (void)level; }
static int deko_max_anisotropy(void) { return 1; }

static GfxRenderingAPI deko_make_api(void)
{
    GfxRenderingAPI api = {};
    api.get_name = deko_api_name;
    api.get_max_texture_size = deko_max_texture;
    api.get_clip_parameters = deko_clip;
    api.unload_shader = deko_unload_shader;
    api.load_shader = deko_load_shader_program;
    api.create_and_load_new_shader = deko_create_shader;
    api.lookup_shader = deko_lookup_shader;
    api.shader_get_info = deko_shader_info;
    api.clear_shaders = deko_clear_shaders;
    api.new_texture = deko_new_texture;
    api.select_texture = deko_select_texture;
    api.upload_texture = deko_upload_texture;
    api.set_sampler_parameters = deko_sampler_parameters;
    api.set_depth_mode = deko_depth_mode;
    api.set_depth_range = deko_depth_range;
    api.set_viewport = deko_viewport;
    api.set_scissor = deko_scissor;
    api.set_use_alpha = deko_use_alpha;
    api.draw_triangles = deko_draw_triangles;
    api.init = deko_api_init;
    api.on_resize = deko_api_resize;
    api.start_frame = deko_api_start_frame;
    api.end_frame = deko_api_end_frame;
    api.finish_render = deko_api_finish_render;
    api.create_framebuffer = deko_create_framebuffer;
    api.update_framebuffer_parameters = deko_update_framebuffer;
    api.start_draw_to_framebuffer = deko_start_draw_to_framebuffer;
    api.copy_framebuffer = deko_copy_framebuffer;
    api.clear_framebuffer = deko_clear_framebuffer;
    api.resolve_msaa_color_buffer = deko_resolve_msaa;
    api.get_framebuffer_texture_id = deko_framebuffer_texture;
    api.select_texture_fb = deko_select_framebuffer_texture;
    api.delete_texture = deko_delete_texture;
    api.set_texture_filter = deko_set_filter;
    api.get_texture_filter = deko_get_filter;
    api.set_mipmap_filter = deko_set_mipmap;
    api.set_anisotropy_level = deko_set_anisotropy;
    api.get_max_anisotropy_level = deko_max_anisotropy;
    return api;
}

/* ------------------------------------------------------------------------ */
/* GfxWindowManagerAPI                                                      */
/* ------------------------------------------------------------------------ */

static uint32_t wm_width = 1280;
static uint32_t wm_height = 720;
static int wm_target_fps;
static int wm_swap_interval = 1;

static void wm_init(const struct GfxWindowInitSettings *settings)
{
    wm_width = settings->width ? settings->width : 1280;
    wm_height = settings->height ? settings->height : 720;
    if (!deko_gpu_init(wm_width, wm_height)) {
        sysLogPrintf(LOG_ERROR, "deko3d: window init failed");
    }
}

static void wm_close(void)
{
    if (g.queue) {
        dkQueueWaitIdle(g.queue);
        dkQueueDestroy(g.queue);
        g.queue = nullptr;
    }
    if (g.cmd) {
        dkCmdBufDestroy(g.cmd);
        g.cmd = nullptr;
    }
    if (g.cmd_mem) { dkMemBlockDestroy(g.cmd_mem); g.cmd_mem = nullptr; }
    if (g.vertex_mem) { dkMemBlockDestroy(g.vertex_mem); g.vertex_mem = nullptr; }
    if (g.staging_mem) { dkMemBlockDestroy(g.staging_mem); g.staging_mem = nullptr; }
    for (uint32_t i = 0; i < g.retired_count; ++i) {
        dkMemBlockDestroy(g.retired_mem[i]);
    }
    g.retired_count = 0;
    for (uint32_t i = 0; i < GE_DEKO_MAX_TEXTURES; ++i) {
        if (g.textures[i].mem) {
            dkMemBlockDestroy(g.textures[i].mem);
            g.textures[i].mem = nullptr;
            g.textures[i].ready = false;
        }
    }
    if (g.code_mem) { dkMemBlockDestroy(g.code_mem); g.code_mem = nullptr; }
    if (g.depth_mem) { dkMemBlockDestroy(g.depth_mem); g.depth_mem = nullptr; }
    if (g.swapchain) { dkSwapchainDestroy(g.swapchain); g.swapchain = nullptr; }
    if (g.frame_mem) { dkMemBlockDestroy(g.frame_mem); g.frame_mem = nullptr; }
    if (g.device) { dkDeviceDestroy(g.device); g.device = nullptr; }
    gpu_ready = false;
}

static int wm_get_display_mode(int modenum, int *out_w, int *out_h)
{
    if (modenum != 0) {
        return 0;
    }
    if (out_w) *out_w = (int)wm_width;
    if (out_h) *out_h = (int)wm_height;
    return 1;
}
static int wm_get_current_display_mode(int *out_w, int *out_h) { return wm_get_display_mode(0, out_w, out_h); }
static int wm_get_num_display_modes(void) { return 1; }
static int32_t wm_get_fullscreen_state(void) { return 1; }
static void wm_set_fullscreen_changed_callback(void (*cb)(bool)) { (void)cb; }
static void wm_set_fullscreen(bool enable) { (void)enable; }
static void wm_set_fullscreen_exclusive(bool exclusive) { (void)exclusive; }
static void wm_set_fullscreen_flag(int32_t mode) { (void)mode; }
static int32_t wm_get_fullscreen_flag_mode(void) { return 0; }
static int32_t wm_get_maximized_state(void) { return 0; }
static void wm_set_maximize(bool enable) { (void)enable; }
static void wm_get_active_window_refresh_rate(uint32_t *rate) { if (rate) *rate = 60; }
static void wm_set_cursor_visibility(bool visible) { (void)visible; }
static void wm_set_closest_resolution(int32_t width, int32_t height, bool center)
{
    (void)width; (void)height; (void)center;
}
static void wm_set_dimensions(uint32_t width, uint32_t height, int32_t x, int32_t y)
{
    (void)width; (void)height; (void)x; (void)y;
}
static void wm_get_dimensions(uint32_t *width, uint32_t *height, int32_t *x, int32_t *y)
{
    if (width) *width = wm_width;
    if (height) *height = wm_height;
    if (x) *x = 0;
    if (y) *y = 0;
}
static void wm_get_centered_positions(int32_t width, int32_t height, int32_t *x, int32_t *y)
{
    (void)width; (void)height;
    if (x) *x = 0;
    if (y) *y = 0;
}
static void wm_handle_events(void) { }

static bool wm_start_frame(void)
{
    if (!gpu_ready) {
        return false;
    }
    g.slot = dkQueueAcquireImage(g.queue, g.swapchain);
    if (g.slot < 0 || g.slot >= (int)GE_DEKO_FRAMES) {
        return false;
    }
    /* Stage 1 reuses one command buffer and one vertex block. Wait for the
     * previous submission before overwriting either one. */
    dkQueueWaitIdle(g.queue);
    return true;
}

static void wm_swap_buffers_begin(void)
{
    if (!gpu_ready) {
        return;
    }
    dkQueueSubmitCommands(g.queue, g.frame_cmd);
    dkQueuePresentImage(g.queue, g.swapchain, g.slot);
    if (dkQueueIsInErrorState(g.queue)) {
        static unsigned errors;
        if (errors++ < 4) {
            sysLogPrintf(LOG_ERROR, "deko3d: queue entered an error state");
        }
    }
    g.presented++;
    if (g.presented <= 3) {
        sysLogPrintf(LOG_NOTE, "deko3d: frame %u presented draws=%u skipped=%u",
                     g.presented, g.draws, g.skipped);
    }
}

static void wm_swap_buffers_end(void) { }

static double wm_get_time(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static int32_t wm_get_target_fps(void) { return wm_target_fps; }
static void wm_set_target_fps(int fps) { wm_target_fps = fps; }
static bool wm_can_disable_vsync(void) { return false; }
static void *wm_get_window_handle(void) { return nullptr; }
static void wm_set_window_title(const char *title) { (void)title; }
static int wm_get_swap_interval(void) { return wm_swap_interval; }
static bool wm_set_swap_interval(int interval) { wm_swap_interval = interval; return true; }

static GfxWindowManagerAPI deko_make_wm(void)
{
    GfxWindowManagerAPI wm = {};
    wm.init = wm_init;
    wm.close = wm_close;
    wm.get_display_mode = wm_get_display_mode;
    wm.get_current_display_mode = wm_get_current_display_mode;
    wm.get_num_display_modes = wm_get_num_display_modes;
    wm.get_fullscreen_state = wm_get_fullscreen_state;
    wm.set_fullscreen_changed_callback = wm_set_fullscreen_changed_callback;
    wm.set_fullscreen = wm_set_fullscreen;
    wm.set_fullscreen_exclusive = wm_set_fullscreen_exclusive;
    wm.set_fullscreen_flag = wm_set_fullscreen_flag;
    wm.get_fullscreen_flag_mode = wm_get_fullscreen_flag_mode;
    wm.get_maximized_state = wm_get_maximized_state;
    wm.set_maximize = wm_set_maximize;
    wm.get_active_window_refresh_rate = wm_get_active_window_refresh_rate;
    wm.set_cursor_visibility = wm_set_cursor_visibility;
    wm.set_closest_resolution = wm_set_closest_resolution;
    wm.set_dimensions = wm_set_dimensions;
    wm.get_dimensions = wm_get_dimensions;
    wm.get_centered_positions = wm_get_centered_positions;
    wm.handle_events = wm_handle_events;
    wm.start_frame = wm_start_frame;
    wm.swap_buffers_begin = wm_swap_buffers_begin;
    wm.swap_buffers_end = wm_swap_buffers_end;
    wm.get_time = wm_get_time;
    wm.get_target_fps = wm_get_target_fps;
    wm.set_target_fps = wm_set_target_fps;
    wm.can_disable_vsync = wm_can_disable_vsync;
    wm.get_window_handle = wm_get_window_handle;
    wm.set_window_title = wm_set_window_title;
    wm.get_swap_interval = wm_get_swap_interval;
    wm.set_swap_interval = wm_set_swap_interval;
    return wm;
}

extern "C" {
struct GfxWindowManagerAPI gfx_deko3d_wm = deko_make_wm();
struct GfxRenderingAPI gfx_deko3d_api = deko_make_api();
}
