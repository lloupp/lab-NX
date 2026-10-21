/*
 * GoldenEye NX / deko3d stage 1: real Switch GPU bootstrap.
 *
 * This is an independent GPU smoke test. The triangle is GENERATED geometry,
 * NOT a display list, texture, or frame from GoldenEye 007.
 *
 * The draw sequence follows the public-domain-style switchbrew/deko_basic
 * architecture. Shaders are compiled by devkitPro uam to DKSH at build time.
 * This program does not load any commercial ROM or proprietary Nintendo keys.
 */
#include <switch.h>
#include <deko3d.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#define GE_FB_WIDTH 1280
#define GE_FB_HEIGHT 720
#define GE_NUM_FRAMES 2
#define GE_CODE_BYTES (64u * 1024u)
#define GE_CMD_BYTES (16u * 1024u)
#define GE_TRACE "sdmc:/switch/lab-nx/goldeneye/deko_boot_trace.txt"

typedef struct {
    DkDevice device;
    DkMemBlock frame_mem;
    DkImage frames[GE_NUM_FRAMES];
    DkSwapchain swapchain;
    DkMemBlock code_mem;
    DkMemBlock vertex_mem;
    uint32_t code_used;
    DkShader vertex;
    DkShader fragment;
    DkMemBlock command_mem;
    DkCmdBuf command_buffer;
    DkCmdList bind_target[GE_NUM_FRAMES];
    DkCmdList render;
    DkQueue queue;
} GeDeko;

static GeDeko g_gpu;

/* Host-to-GPU vertex staging: the primitive is a synthetic test ONLY. The
 * layout (3x position + 3x color) matches the two precompiled DKSH inputs.
 * This provides a concrete vertex-buffer path for a future Fast3D bridge.
 */
typedef struct {
    float pos[3];
    float rgb[3];
} GeDekoVertex;

static const GeDekoVertex g_triangle[3] = {
    { {  0.0f,  0.8f, 0.0f }, { 1.0f, 0.0f, 0.0f } },
    { { -0.8f, -0.8f, 0.0f }, { 0.0f, 1.0f, 0.0f } },
    { {  0.8f, -0.8f, 0.0f }, { 0.0f, 0.0f, 1.0f } }
};


static void ge_trace(const char *message)
{
    mkdir("sdmc:/switch", 0777);
    mkdir("sdmc:/switch/lab-nx", 0777);
    mkdir("sdmc:/switch/lab-nx/goldeneye", 0777);
    FILE *file = fopen(GE_TRACE, "a");
    if (!file) return;
    fprintf(file, "%s\n", message);
    fclose(file);
}

static bool ge_load_shader(DkShader *shader, const char *path)
{
    FILE *file = fopen(path, "rb");
    if (!file) return false;
    if (fseek(file, 0, SEEK_END) != 0) { fclose(file); return false; }
    long length = ftell(file);
    if (length <= 0 || length > GE_CODE_BYTES) {
        fclose(file);
        return false;
    }
    rewind(file);
    uint32_t offset = g_gpu.code_used;
    uint32_t size = (uint32_t)length;
    uint32_t padded = (size + DK_SHADER_CODE_ALIGNMENT - 1u)
                    & ~(DK_SHADER_CODE_ALIGNMENT - 1u);
    if (offset > GE_CODE_BYTES || padded > GE_CODE_BYTES - offset) {
        fclose(file);
        return false;
    }
    uint8_t *destination = (uint8_t*)dkMemBlockGetCpuAddr(g_gpu.code_mem);
    if (!destination || fread(destination + offset, 1, size, file) != size) {
        fclose(file);
        return false;
    }
    fclose(file);
    DkShaderMaker maker;
    dkShaderMakerDefaults(&maker, g_gpu.code_mem, offset);
    dkShaderInitialize(shader, &maker);
    g_gpu.code_used += padded;
    return true;
}

static void ge_graphics_shutdown(void)
{
    if (g_gpu.queue) {
        dkQueueWaitIdle(g_gpu.queue);
        dkQueueDestroy(g_gpu.queue);
        g_gpu.queue = NULL;
    }
    if (g_gpu.command_buffer) {
        dkCmdBufDestroy(g_gpu.command_buffer);
        g_gpu.command_buffer = NULL;
    }
    if (g_gpu.command_mem) {
        dkMemBlockDestroy(g_gpu.command_mem);
        g_gpu.command_mem = NULL;
    }
    if (g_gpu.vertex_mem) {
        dkMemBlockDestroy(g_gpu.vertex_mem);
        g_gpu.vertex_mem = NULL;
    }
    if (g_gpu.code_mem) {
        dkMemBlockDestroy(g_gpu.code_mem);
        g_gpu.code_mem = NULL;
    }
    if (g_gpu.swapchain) {
        dkSwapchainDestroy(g_gpu.swapchain);
        g_gpu.swapchain = NULL;
    }
    if (g_gpu.frame_mem) {
        dkMemBlockDestroy(g_gpu.frame_mem);
        g_gpu.frame_mem = NULL;
    }
    if (g_gpu.device) {
        dkDeviceDestroy(g_gpu.device);
        g_gpu.device = NULL;
    }
}

/* Reference profile: same simple graphics-only queue flags used by the
 * Atmosphere GPU console renderer. Create it directly after the device so a
 * host failure is not conflated with DKSH, command list, or swapchain setup.
 * Leave deko3d's validated command-memory and scratch defaults intact.
 */
static bool ge_create_reference_queue(void)
{
    DkQueueMaker queue_maker;
    dkQueueMakerDefaults(&queue_maker, g_gpu.device);
    queue_maker.flags = DkQueueFlags_Graphics;
    ge_trace("queue-create-reference-start");
    g_gpu.queue = dkQueueCreate(&queue_maker);
    ge_trace("queue-create-returned");
    if (!g_gpu.queue) { ge_trace("queue-create-failed"); return false; }
    ge_trace("queue-ready");
    return true;
}

static bool ge_graphics_init(void)
{
    DkDeviceMaker maker;
    dkDeviceMakerDefaults(&maker);
    g_gpu.device = dkDeviceCreate(&maker);
    if (!g_gpu.device) { ge_trace("device-create-failed"); return false; }
    ge_trace("device-created");
    if (!ge_create_reference_queue()) return false;

    DkImageLayoutMaker layout_maker;
    dkImageLayoutMakerDefaults(&layout_maker, g_gpu.device);
    layout_maker.flags = DkImageFlags_UsageRender | DkImageFlags_UsagePresent | DkImageFlags_HwCompression;
    layout_maker.format = DkImageFormat_RGBA8_Unorm;
    layout_maker.dimensions[0] = GE_FB_WIDTH;
    layout_maker.dimensions[1] = GE_FB_HEIGHT;

    DkImageLayout layout;
    dkImageLayoutInitialize(&layout, &layout_maker);
    uint32_t image_bytes = dkImageLayoutGetSize(&layout);
    uint32_t align = dkImageLayoutGetAlignment(&layout);
    image_bytes = (image_bytes + align - 1u) & ~(align - 1u);

    DkMemBlockMaker memory_maker;
    dkMemBlockMakerDefaults(&memory_maker, g_gpu.device, GE_NUM_FRAMES * image_bytes);
    memory_maker.flags = DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image;
    g_gpu.frame_mem = dkMemBlockCreate(&memory_maker);
    if (!g_gpu.frame_mem) { ge_trace("frame-memory-failed"); return false; }

    const DkImage *swap_images[GE_NUM_FRAMES];
    for (unsigned i = 0; i < GE_NUM_FRAMES; ++i) {
        dkImageInitialize(&g_gpu.frames[i], &layout, g_gpu.frame_mem, i * image_bytes);
        swap_images[i] = &g_gpu.frames[i];
    }

    DkSwapchainMaker swap_maker;
    dkSwapchainMakerDefaults(&swap_maker, g_gpu.device, nwindowGetDefault(), swap_images, GE_NUM_FRAMES);
    g_gpu.swapchain = dkSwapchainCreate(&swap_maker);
    if (!g_gpu.swapchain) { ge_trace("swapchain-create-failed"); return false; }
    ge_trace("swapchain-created");

    dkMemBlockMakerDefaults(&memory_maker, g_gpu.device, GE_CODE_BYTES);
    memory_maker.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached | DkMemBlockFlags_Code;
    g_gpu.code_mem = dkMemBlockCreate(&memory_maker);
    if (!g_gpu.code_mem) { ge_trace("shader-memory-failed"); return false; }

    if (!ge_load_shader(&g_gpu.vertex, "romfs:/shaders/triangle_vsh.dksh") ||
        !ge_load_shader(&g_gpu.fragment, "romfs:/shaders/color_fsh.dksh")) {
        ge_trace("dksh-load-failed");
        return false;
    }
    ge_trace("dksh-loaded");

    /* CPU-writable / GPU-readable vertex storage. The backing block follows
     * deko3d alignment rules even though the actual triangle is tiny. */
    dkMemBlockMakerDefaults(&memory_maker, g_gpu.device, DK_MEMBLOCK_ALIGNMENT);
    memory_maker.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached;
    g_gpu.vertex_mem = dkMemBlockCreate(&memory_maker);
    if (!g_gpu.vertex_mem) { ge_trace("vertex-memory-failed"); return false; }
    void *vertex_cpu = dkMemBlockGetCpuAddr(g_gpu.vertex_mem);
    if (!vertex_cpu) { ge_trace("vertex-address-failed"); return false; }
    memcpy(vertex_cpu, g_triangle, sizeof(g_triangle));
    ge_trace("cpu-vertex-buffer-uploaded");

    dkMemBlockMakerDefaults(&memory_maker, g_gpu.device, GE_CMD_BYTES);
    memory_maker.flags = DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached;
    ge_trace("command-memory-alloc-start");
    g_gpu.command_mem = dkMemBlockCreate(&memory_maker);
    ge_trace("command-memory-alloc-returned");
    if (!g_gpu.command_mem) { ge_trace("command-memory-failed"); return false; }

    DkCmdBufMaker command_maker;
    dkCmdBufMakerDefaults(&command_maker, g_gpu.device);
    ge_trace("command-buffer-create-start");
    g_gpu.command_buffer = dkCmdBufCreate(&command_maker);
    ge_trace("command-buffer-create-returned");
    if (!g_gpu.command_buffer) { ge_trace("command-buffer-failed"); return false; }
    ge_trace("command-buffer-add-memory-start");
    dkCmdBufAddMemory(g_gpu.command_buffer, g_gpu.command_mem, 0, GE_CMD_BYTES);
    ge_trace("command-buffer-add-memory-returned");

    for (unsigned i = 0; i < GE_NUM_FRAMES; ++i) {
        ge_trace("bind-render-target-start");
        DkImageView view;
        dkImageViewDefaults(&view, &g_gpu.frames[i]);
        dkCmdBufBindRenderTarget(g_gpu.command_buffer, &view, NULL);
        g_gpu.bind_target[i] = dkCmdBufFinishList(g_gpu.command_buffer);
        ge_trace("bind-render-target-finished");
    }

    DkViewport viewport = { 0.f, 0.f, (float)GE_FB_WIDTH, (float)GE_FB_HEIGHT, 0.f, 1.f };
    DkScissor scissor = { 0, 0, GE_FB_WIDTH, GE_FB_HEIGHT };
    DkShader const *shaders[] = { &g_gpu.vertex, &g_gpu.fragment };
    DkRasterizerState raster;
    DkColorState color;
    DkColorWriteState write;
    dkRasterizerStateDefaults(&raster);
    dkColorStateDefaults(&color);
    dkColorWriteStateDefaults(&write);

    ge_trace("render-commands-recording-start");
    dkCmdBufSetViewports(g_gpu.command_buffer, 0, &viewport, 1);
    dkCmdBufSetScissors(g_gpu.command_buffer, 0, &scissor, 1);
    dkCmdBufClearColorFloat(g_gpu.command_buffer, 0, DkColorMask_RGBA,
                           0.08f, 0.14f, 0.25f, 1.f);
    dkCmdBufBindShaders(g_gpu.command_buffer, DkStageFlag_GraphicsMask, shaders, 2);
    dkCmdBufBindRasterizerState(g_gpu.command_buffer, &raster);
    dkCmdBufBindColorState(g_gpu.command_buffer, &color);
    dkCmdBufBindColorWriteState(g_gpu.command_buffer, &write);
    DkVtxAttribState attributes[2] = {
        { 0, 0, offsetof(GeDekoVertex, pos), DkVtxAttribSize_3x32, DkVtxAttribType_Float, 0 },
        { 0, 0, offsetof(GeDekoVertex, rgb), DkVtxAttribSize_3x32, DkVtxAttribType_Float, 0 }
    };
    DkVtxBufferState buffer_states[1] = {
        { sizeof(GeDekoVertex), 0 }
    };
    DkBufExtents vertex_buffer = {
        dkMemBlockGetGpuAddr(g_gpu.vertex_mem), sizeof(g_triangle)
    };
    dkCmdBufBindVtxAttribState(g_gpu.command_buffer, attributes, 2);
    dkCmdBufBindVtxBufferState(g_gpu.command_buffer, buffer_states, 1);
    dkCmdBufBindVtxBuffers(g_gpu.command_buffer, 0, &vertex_buffer, 1);
    ge_trace("vertex-buffer-bound");
    dkCmdBufDraw(g_gpu.command_buffer, DkPrimitive_Triangles, 3, 1, 0, 0);
    g_gpu.render = dkCmdBufFinishList(g_gpu.command_buffer);
    ge_trace("render-commands-recorded");

    ge_trace("deko3d-ready");
    return true;
}

static bool ge_graphics_present(void)
{
    static unsigned calls = 0;
    bool first = (++calls == 1);
    if (first) ge_trace("first-frame-acquire-start");
    int slot = dkQueueAcquireImage(g_gpu.queue, g_gpu.swapchain);
    if (slot < 0 || slot >= GE_NUM_FRAMES) {
        if (first) ge_trace("first-frame-acquire-failed");
        return false;
    }
    if (first) ge_trace("first-frame-image-acquired");
    dkQueueSubmitCommands(g_gpu.queue, g_gpu.bind_target[slot]);
    dkQueueSubmitCommands(g_gpu.queue, g_gpu.render);
    if (first) ge_trace("first-frame-commands-submitted");
    dkQueuePresentImage(g_gpu.queue, g_gpu.swapchain, slot);
    if (first) ge_trace("first-frame-present-returned");
    return !dkQueueIsInErrorState(g_gpu.queue);
}

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    fsdevMountSdmc();
    /* Never accept milestones left over from a previous boot on the SDMC. */
    mkdir("sdmc:/switch", 0777);
    mkdir("sdmc:/switch/lab-nx", 0777);
    mkdir("sdmc:/switch/lab-nx/goldeneye", 0777);
    FILE *trace_file = fopen(GE_TRACE, "w");
    if (trace_file) fclose(trace_file);
    ge_trace("main-entered");

    Result romfs_result = romfsInit();
    if (R_FAILED(romfs_result)) {
        ge_trace("romfs-init-failed");
        return 1;
    }
    ge_trace("romfs-mounted");

    if (!ge_graphics_init()) {
        ge_graphics_shutdown();
        romfsExit();
        return 2;
    }
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeDefault(&pad);
    unsigned frames = 0;
    while (appletMainLoop()) {
        padUpdate(&pad);
        if (padGetButtonsDown(&pad) & HidNpadButton_Plus) break;
        if (!ge_graphics_present()) {
            ge_trace("present-failed");
            break;
        }
        if (++frames == 1) ge_trace("first-deko-frame-submitted");
        if (frames == 120) ge_trace("deko-120-frames-submitted");
    }
    ge_graphics_shutdown();
    romfsExit();
    ge_trace("shutdown-clean");
    return 0;
}
