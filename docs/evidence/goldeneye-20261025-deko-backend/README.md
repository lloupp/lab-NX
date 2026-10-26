# deko3d backend, stages 1–7, in the full engine — 2026-10-25

## Result

The complete ARM64 engine boots, submits real Fast3D geometry and presents
through a deko3d backend instead of SDL/OpenGL/Mesa. The **full Dam exterior
now renders through deko3d**: rocks, road, truck, railings, tunnel lights and
the facility are visible in `stage3-full-dam-textured.png`.

- **Stage 1:** deko3d device, 1280x720 swapchain, `Z24S8` depth, command
  buffer/queue; `SHADE RGB` and `FOGTEX RGB3` profiles; clamped scissor.
- **Stage 2:** RGBA8 texture uploads, image/sampler descriptor sets, and the
  FOGTEX combiner `mix(INPUT_1, TEXEL0, INPUT_2) * INPUT_3` with fog.
- **Stage 3:** generic VBO unpacker (`ge_fast3d_unpack_generic`) for the
  2-texture profiles and an environment shader
  `mix(TEXEL0, TEXEL1, INPUT_1) * INPUT_2` with fog. The Dam run records
  about **139–148 draws and 14 skips per frame** (8 textures uploaded).
- **Stage 4:** exact alpha modes per profile — opaque for
  `1000020d…:13`/`320d020d…:12`/FOGTEX, `mix(t0.a,t1.a,in0.a)*in1.a` for
  `color_alpha_same` profiles (`020d020d…:13`), and a flat white shader for
  the no-texture `d000d00010001000:13` profile. The Dam aerial view renders
  through deko3d (`stage4-alpha-combiner-dam.png`).
- **Stage 5:** per-vertex clamp-S/T limits drive UV clamping in the env
  shaders; texedge/alpha-threshold fragment variants discard low-alpha
  texels (`stage5-clamp-edge-dam.png`).
- **Stage 6:** `DkBlendState` for alpha surfaces and texture fallbacks for
  the remaining profiles; the clear-colour hole above the dam is filled
  (`stage6-aerial-confirmed.png`, `stage6-sky-backdrop-filled.png`).
- **Stage 7:** the cloud-sky combiner
  `mix(ENVIRONMENT, SHADE, TEXEL0)` plus per-texture sampler descriptors.
  Fast3D records wrap/filter per texture (GL keeps it on the texture
  object); the shared per-unit sampler clamped the sky's UVs to the last
  texel, producing the flat blue plate. With sampler state keyed by texture
  id — and uploads following `select_texture`, as GL's built-in upload does
  — the Dam sky shows the cloud tile (`stage7-sky-clouds.png`).

## Evidence

- Stage-6 NRO: 8,319,032 bytes, SHA-256
  `9f1f89945f6e9ab12b0d9fc618c7a9ce224a11d85d3f79ee112684091f996909`.
- Patched deko3d (dekotools MME upload): SHA-256
  `64313be5813cffbdb59a3ba3fe356963c98737206b43cb0407b66782b7fc3155`.
  The stock devkitPro `libdeko3d.a` fails at `dkQueueCreate` in Eden.
- `stage7-sky-clouds.png`: Dam view with the cloud sky after the sampler
  and combiner fix.
- `stage6-aerial-confirmed.png`: aerial view with the former black hole filled.
- `stage6-sky-backdrop-filled.png`: sky/backdrop geometry drawn again after
  the fallback profiles.
- `stage5-clamp-edge-dam.png`: the Dam aerial view with clamp-S/T and
  texedge variants.
- `stage4-alpha-combiner-dam.png`: the Dam aerial view rendered by the
  deko3d backend with the stage-4 alpha modes.
- `stage3-full-dam-textured.png`: the Dam exterior rendered by the deko3d
  backend (1280x720 host screenshot).
- `stage2-textured-characters.png`, the stage-1 runs and the diagnostic
  triangle screenshot preserve the earlier milestones.
- Raw artifacts: `007/goldeneye-deko-backend-20261025/`.

## Reproduction

```sh
# Patched deko3d (MME upload fix) and smoke
DEVKITPRO=<pinned> python3 scripts/build_goldeneye_deko_compat.py \
  --work-dir <deko-work> --upstream <pinned goldeneye-pc-port>

# Engine backend
DEVKITPRO=<pinned> python3 scripts/build_goldeneye_native_engine.py \
  --work-dir <engine-work> --source <pinned goldeneye-pc-port> --jobs 4 \
  --deko3d --deko-lib <deko-work>/deko3d/lib/libdeko3d.a
```

See `docs/GOLDENEYE_DEKO_BACKEND_STAGE1.md` for architecture and next steps.

## Remaining work

- Mipmaps are not generated (minified textures alias); noise dither path not
  implemented.
- MSAA is forced to 1; the `different_size` path is not exercised.
- Input, audio and mission completion were not re-validated under the deko
  backend; the GL path remains the reference.
- One command buffer/vertex block; `dkQueueWaitIdle` serialises frames.
- No ROM, sidecar or game frame is added to Git.
