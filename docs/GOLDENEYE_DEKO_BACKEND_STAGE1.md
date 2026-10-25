# GoldenEye NX — deko3d backend, stage 1 (2026-10-25)

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
- Depth (`Z24S8`, `LEQUAL`) and a clamped scissor: Fast3D can pass negative
  scissor rectangles, and `DkScissor` is unsigned, so the rectangle is clamped
  to the framebuffer before recording.
- In the final Dam run the backend records about **63 draws and 92 skips per
  frame**. `deko3d: frame N presented draws=... skipped=...` reports the
  split; skipped batches use combiner profiles that are not implemented yet.

## What is not implemented

- **Textures.** `new_texture`/`upload_texture`/`select_texture`/
  `set_sampler_parameters` are accepted but do not create or bind deko
  images. Both supported profiles therefore draw with their first RGB input
  only. Most Dam geometry is textured, so the rendered geometry is near-black
  on the dark clear colour.
- **Combiner shaders.** One fixed DKSH pair (clip position + RGB) is used for
  both profiles. The other observed combiners
  (`1000020d0000818a:13`, `320d020d818a818a:12`, `020d020d818a818a:13`,
  `d000d00010001000:13`, …) keep the engine's VBO layout for
  `shader_get_info` but are not drawn.
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

Verification NRO: 8,298,552 bytes, SHA-256
`47e25263c078be7fd9797aad2f229a3c5c3f4dd21da9e7a0837e6a47bc6134d9`.
Patched deko3d: SHA-256
`64313be5813cffbdb59a3ba3fe356963c98737206b43cb0407b66782b7fc3155`.

Raw runs and the NRO are preserved outside Git in
`007/goldeneye-deko-backend-20261025/`:

- `run-20261025-133105-xtest/`: production backend, Dam frame, 2-colour
  screenshot (clear + black geometry) and draw/skip counts.
- `diagnostic-triangle-and-game-silhouettes.png`: a temporary build with the
  synthetic clip-space triangle and depth disabled, showing the same deko
  pipeline drawing both the diagnostic triangle and the engine's Bond/guard
  silhouettes over it.
- `goldeneye-native-engine-deko.nro`, `SHA256SUMS`, `MANIFEST.json`.

## Next steps

1. Texture path: deko images + descriptors + a DKSH fragment shader with a
   sampler; wire `upload_texture`/`select_texture`/`set_sampler_parameters`.
2. Combiner shaders for the profiles observed in the Dam trace, using
   `gfx_cc_get_features` data to pick the fixed shader.
3. Depth/z validation and, later, MSAA and command-buffer double buffering.
4. A CI job that builds the patched deko3d and the engine backend; the
   current workflows only build the GL engine.
