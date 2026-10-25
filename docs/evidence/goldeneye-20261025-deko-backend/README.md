# deko3d backend stage 1 in the full engine — 2026-10-25

## Result

The complete ARM64 engine now boots and presents through a deko3d backend
instead of SDL/OpenGL/Mesa. It creates its own deko3d device, swapchain,
depth image, command buffer and queue on the Switch default window, records
the engine's Fast3D float VBOs, and presents every frame in Eden 0.2.1.

Real game geometry reaches deko3d. In the Dam run the backend records about
**63 draws and 92 skips per frame**. The two supported profiles are:

- SHADE RGB (`0x1000:0`), 7 floats/vertex;
- FOGTEX RGB3 (`d000030d12181218:00000012`), 19 floats/vertex.

Textures and the combiner shader set are not implemented yet, so the
supported batches draw with their first RGB input only and the scene is
near-black on the dark clear colour. The other five combiner profiles keep
the correct VBO layout for the engine but are skipped at draw time.

## Evidence

- NRO: 8,298,552 bytes, SHA-256
  `47e25263c078be7fd9797aad2f229a3c5c3f4dd21da9e7a0837e6a47bc6134d9`.
- Patched deko3d (dekotools MME upload): SHA-256
  `64313be5813cffbdb59a3ba3fe356963c98737206b43cb0407b66782b7fc3155`.
  The stock devkitPro `libdeko3d.a` fails at `dkQueueCreate` in Eden.
- Production run: `run-20261025-133105-xtest` — Dam frame, draw/skip
  counters, two-colour screenshot (clear plus black geometry).
- Diagnostic screenshot
  `diagnostic-triangle-and-game-silhouettes.png`: a temporary build that
  draws a synthetic clip-space triangle through the same deko pipeline, with
  depth disabled, so the engine's Bond/guard silhouettes are visible over it.
  This is a pipeline proof, not a game frame.

Raw artifacts are preserved outside Git in
`007/goldeneye-deko-backend-20261025/`.

## Reproduction

```sh
# Patched deko3d and smoke
DEVKITPRO=<pinned> python3 scripts/build_goldeneye_deko_compat.py \
  --work-dir <deko-work> --upstream <pinned goldeneye-pc-port>

# Engine backend
DEVKITPRO=<pinned> python3 scripts/build_goldeneye_native_engine.py \
  --work-dir <engine-work> --source <pinned goldeneye-pc-port> --jobs 4 \
  --deko3d --deko-lib <deko-work>/deko3d/lib/libdeko3d.a
```

See `docs/GOLDENEYE_DEKO_BACKEND_STAGE1.md` for the architecture, the exact
limits and the next steps (textures, combiner shaders, CI).

## Limits

- No texture sampling or combiner shaders yet; the scene is near-black.
- MSAA is forced to 1; the `different_size` path is not exercised.
- Input, audio and mission completion were not re-validated under the deko
  backend; the GL path remains the reference for those.
- No ROM, sidecar or game frame is added to Git.
