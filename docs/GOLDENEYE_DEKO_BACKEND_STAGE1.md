# GoldenEye NX — deko3d backend, stages 1–6 (2026-10-25/26)

## What this is

This is a real engine backend, not the standalone deko3d smoke.
`nxlab/deko_backend/gfx_deko3d.cpp` implements both `GfxWindowManagerAPI` and
`GfxRenderingAPI` and is compiled into the full engine when
`GE_DEKO3D_BACKEND` is defined. The engine creates a deko3d device, swapchain
and queue on `nwindowGetDefault()`, records its own Fast3D float VBOs, and
presents through deko3d instead of SDL/OpenGL/Mesa.

The build links a deko3d built from the pinned source with the dekotools MME
upload patch. The stock `libdeko3d.a` from devkitPro hits the Eden
`dkQueueCreate` failure (`std::bad_alloc` / `vector::_M_default_append`).

## What works

- deko3d device, 1280x720 swapchain, depth image, command buffer and queue.
- The engine boots, reaches the Dam, and presents every frame; the clear
  colour is visible in the Eden window.
- Real game geometry is submitted through deko3d for the two profiles already
  described by `nxlab/native/goldeneye_fast3d_bridge.h`:
  - `SHADE RGB` (`0x1000:0`), 7 floats/vertex;
  - `FOGTEX RGB3` (`d000030d12181218:00000012`), 19 floats/vertex.
- Stage 2 adds RGBA8 texture uploads (pitch-linear deko images), image and
  sampler descriptor sets, and a FOGTEX fragment shader implementing
  `mix(INPUT_1, TEXEL0, INPUT_2) * INPUT_3` with per-vertex fog. Textured
  characters now render; the texture run uploaded textures 1–8 and recorded
  about **165 draws / 105 skips per frame**.
- Stage 3 adds a generic VBO unpacker (`ge_fast3d_unpack_generic`) for the
  2-texture profiles and an environment shader implementing
  `mix(TEXEL0, TEXEL1, INPUT_1) * INPUT_2` with fog. The Dam exterior now
  renders through deko3d; the stage-3 run records about **139–148 draws and
  14 skips per frame**.
- Stage 4 adds exact alpha modes per profile: opaque for
  `1000020d…:13`/`320d020d…:12`/FOGTEX, `mix(t0.a,t1.a,in0.a)*in1.a` for
  `color_alpha_same` profiles (`020d020d…:13`), and a flat white shader for
  the no-texture `d000d00010001000:13` profile. The Dam aerial view renders
  through deko3d.
- Stage 5 adds clamp-S/T limits per vertex (generic VBO clamp scalars drive
  UV clamping in the env shaders) and texedge/alpha-threshold fragment
  variants (`discard` at 0.5 or 8/256).
- Stage 6 binds `DkBlendState` (alpha-blended surfaces were black) and adds
  texture fallbacks for the remaining unsupported profiles; the sky/backdrop
  hole is filled. Aerial re-check: `stage6-aerial-confirmed.png` has no
  clear-colour pixels in the top region.
- Stage 7 adds the cloud-sky combiner and per-texture sampler state. The sky
  profile `0000000010002821:00000000` renders with
  `mix(ENVIRONMENT, SHADE, TEXEL0)`, the
  `(SHADE - ENVIRONMENT) * TEXEL0 + ENVIRONMENT` formula `src/game/sky.c`
  emits. The flat blue itself was a sampler bug: Fast3D records wrap/filter
  per *texture* (GL stores it on the texture object), but the backend kept
  one sampler descriptor per unit, so the sky inherited the previous frame's
  clamp mode and its UVs (well past 1.0) collapsed onto the last texel.
  `mix(ENV, 1, 68/255) = (80,103,139)` matches the observed flat `(79,103,138)`
  exactly. Samplers are now keyed by texture id, and texture uploads follow
  `select_texture` (the GL built-in upload happens on the bound texture),
  so recycled cache ids no longer write into a stale texture. The Dam sky
  now shows the cloud tile instead of a flat plate.
- Depth (`Z24S8`, `LEQUAL`) and a clamped scissor: Fast3D can pass negative
  scissor rectangles, and `DkScissor` is unsigned, so the rectangle is clamped
  to the framebuffer before recording.
- `deko3d: frame N presented draws=... skipped=...` reports the split.
  Batches whose combiner is not modelled by a dedicated shader use the
  generic 1-/2-texture fallbacks instead of being dropped.

## What is not implemented

- **Alpha and clamp variants.** The generic unpacker accepts `use_alpha`
  VBOs and clamp-S/T extras, but the fragment shaders approximate alpha with
  `tex0.a` and do not model every combiner alpha path. Some surfaces (large
  flat roof/fan geometry) still shade incorrectly.
- **Mipmaps and noise.** Textures are uploaded as a single RGBA8 level and
  the sampler never selects a mip, so minified surfaces (walkway grating,
  distant cliffs) alias where GL's generated mip chain is smooth. The noise
  dither path is not implemented.
- **No-texture combiner variants** such as `d000d00010001000:13` are parsed
  but not shaded (skipped).
- MSAA is forced to 1; the two-step GL resolve is not used by this backend.
- The `different_size` render path is not exercised.
- One command buffer and one vertex block are reused; the backend calls
  `dkQueueWaitIdle` at frame start, so it serialises CPU/GPU. Double buffering
  is a later optimisation.

## Build and run

```sh
# 1. Patched deko3d (MME upload fix) and the smoke NRO
DEVKITPRO=<pinned devkitPro> python3 scripts/build_goldeneye_deko_compat.py \
  --work-dir <deko-work> --upstream <pinned goldeneye-pc-port>

# 2. Full engine with the deko3d backend
DEVKITPRO=<pinned devkitPro> python3 scripts/build_goldeneye_native_engine.py \
  --work-dir <engine-work> --source <pinned goldeneye-pc-port> \
  --jobs 4 --deko3d \
  --deko-lib <deko-work>/deko3d/lib/libdeko3d.a

# 3. Run the NRO in Eden with the ROM and sidecars, as for the GL engine.
```

`--deko3d` applies `patches/goldeneye-pc-port/deko3d-backend.patch`, copies
the backend and compiles the two DKSH programs with `uam`. Without
`--deko-lib` the build links the stock devkitPro library and will fail at
`dkQueueCreate` in Eden.

## Evidence

Verification NRO (stage 6): 8,319,032 bytes, SHA-256
`9f1f89945f6e9ab12b0d9fc618c7a9ce224a11d85d3f79ee112684091f996909`.
Stage 7 NRO: 8,319,032 bytes, SHA-256
`4c0232bf5150d15ec9ba247cebdda781494fd038c11abd0c27a922d3efb7f8e5`.
Patched deko3d: SHA-256
`64313be5813cffbdb59a3ba3fe356963c98737206b43cb0407b66782b7fc3155`.

Raw runs and the NRO are preserved outside Git in
`007/goldeneye-deko-backend-20261025/`:

- `run-20261026-115644-xtest/`: stage-6 sky/backdrop view (`stage6-sky-backdrop-filled.png`).
- Stage 7 Dam flyover with the cloud sky: `stage7-sky-clouds.png`, engine log
  `stage7-sky-clouds-engine.log` (same folder).
- `run-20261026-114037-xtest/`: stage-5 Dam aerial view with
  `stage5-clamp-edge-dam.png`.
- `run-20261025-172002-xtest/`: stage-4 Dam aerial view with
  `stage4-alpha-combiner-dam.png` and the engine log.
- `run-20261025-162838-xtest/`: stage-3 full Dam exterior with
  `stage3-full-dam-textured.png` and the engine log (8 texture uploads,
  ~139–148 draws/14 skips).
- `run-20261025-145258-xtest/`: stage-2 texture run with
  `stage2-textured-characters.png` and the engine log.
- `run-20261025-133105-xtest/`: stage-1 run, 2-colour screenshot and
  draw/skip counts.
- `diagnostic-triangle-and-game-silhouettes.png`: a temporary build with the
  synthetic clip-space triangle and depth disabled, showing the same deko
  pipeline drawing both the diagnostic triangle and the engine's Bond/guard
  silhouettes over it.
- `goldeneye-native-engine-deko.nro`, `SHA256SUMS`, `MANIFEST.json`.

## Next steps

1. The aerial black shape was the clear colour through missing backdrop
   geometry (stage 6); the flat blue sky was sampler state leaking between
   textures (stage 7). Both are fixed. Next: mipmap generation for minified
   textures and the noise dither path.
2. Depth/z validation and, later, MSAA and command-buffer double buffering.
3. The `deko3d-engine-build` CI job builds the patched deko3d and the engine
   backend alongside the GL jobs.
