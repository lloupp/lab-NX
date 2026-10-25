# deko3d backend, stages 1–2, in the full engine — 2026-10-25

## Result

The complete ARM64 engine boots, submits real Fast3D geometry and presents
through a deko3d backend instead of SDL/OpenGL/Mesa.

- **Stage 1:** deko3d device, 1280x720 swapchain, `Z24S8` depth, command
  buffer/queue; real VBOs for `SHADE RGB` (`0x1000:0`) and `FOGTEX RGB3`
  (`d000030d12181218:00000012`); clamped scissor for Fast3D's negative
  rectangles.
- **Stage 2:** RGBA8 texture uploads into pitch-linear deko images, image
  and sampler descriptor sets, and the FOGTEX combiner shader
  `mix(INPUT_1, TEXEL0, INPUT_2) * INPUT_3` with per-vertex fog. Textured
  characters render; the texture run uploaded textures 1–8 and recorded
  about 165 draws / 105 skips per frame.

The Dam **environment** still uses the 2-texture combiner profiles
(`1000020d0000818a:13`, `320d020d818a818a:12`, `020d020d818a818a:13`,
`d000d00010001000:13`), which are skipped. Their VBO layout is `pos4,
tex0 uv2, tex1 uv2, fog4, inputs` (3 floats per input, 4 with alpha); a
generic unpacker and `mix(TEXEL0, TEXEL1, INPUT_1) * INPUT_2` shader are the
next step.

## Evidence

- Stage-2 NRO: 8,306,744 bytes, SHA-256
  `4f5f42fb37eb3a452f9852da9f7f9fa18150aec76131c4e84d09bfcaa39edaf5`.
- Patched deko3d (dekotools MME upload): SHA-256
  `64313be5813cffbdb59a3ba3fe356963c98737206b43cb0407b66782b7fc3155`.
  The stock devkitPro `libdeko3d.a` fails at `dkQueueCreate` in Eden.
- `stage2-textured-characters.png`: 1280x720 host screenshot from the
  stage-2 run — Bond/guards with textures on the dark clear background.
- `run-20261025-145258-xtest/`, `run-20261025-133105-xtest/` and the stage-1
  `diagnostic-triangle-and-game-silhouettes.png` preserve the earlier
  pipeline proofs and draw/skip counts.
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

See `docs/GOLDENEYE_DEKO_BACKEND_STAGE1.md` for architecture, limits and
next steps.

## Limits

- Only one texture binding and the FOGTEX profile are shaded. The 2-texture
  environment profiles, `use_alpha` VBO variants and clamp extras are not
  parsed yet, so the Dam background is missing.
- MSAA is forced to 1; the `different_size` path is not exercised.
- Input, audio and mission completion were not re-validated under the deko
  backend; the GL path remains the reference.
- One command buffer/vertex block; `dkQueueWaitIdle` serialises frames.
- No ROM, sidecar or game frame is added to Git.
