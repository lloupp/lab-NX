# deko3d backend, stages 1–3, in the full engine — 2026-10-25

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

## Evidence

- Stage-3 NRO: 8,306,744 bytes, SHA-256
  `7133c1d08df03fce8c58bfb8e48b5da93b8c2a334057c725dc1443bd9f2af30d`.
- Patched deko3d (dekotools MME upload): SHA-256
  `64313be5813cffbdb59a3ba3fe356963c98737206b43cb0407b66782b7fc3155`.
  The stock devkitPro `libdeko3d.a` fails at `dkQueueCreate` in Eden.
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

- Alpha/combiner parity: alpha is approximated with `tex0.a`; some flat
  roof/fan surfaces still shade incorrectly.
- No-texture combiner variants (`d000d00010001000:13`) are skipped.
- MSAA is forced to 1; the `different_size` path is not exercised.
- Input, audio and mission completion were not re-validated under the deko
  backend; the GL path remains the reference.
- One command buffer/vertex block; `dkQueueWaitIdle` serialises frames.
- No ROM, sidecar or game frame is added to Git.
