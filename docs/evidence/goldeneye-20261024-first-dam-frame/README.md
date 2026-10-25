# First original GoldenEye scene visible in Eden — 2026-10-24

## Result

The complete ARM64 engine now presents the first original GoldenEye scene in
official Eden 0.2.1. The Dam level loads, fades in, and reaches the
first-person view with Bond's weapon and the ammo HUD (`7 | 93`). This is
game-origin geometry, not a synthetic fixture.

- Final NRO: 8,249,400 bytes, SHA-256
  `43476785ab6ee3a9af7db606194e07bea9a0811b991c5f4c3d69e9302ed18bb3`.
- Build: pinned `devkitpro/devkita64:20260219`, devkitA64 GCC 15.2.0,
  upstream `fda76b69837e6c5aae436e0d3e798989e49b06d2`, `GE_FAST3D_TRACE=1`,
  `GE_FAST3D_ENGINE_ADAPTER=1`, `deko3d_backend_enabled=false`.
- Private runtime data: NTSC-U ROM, 512 model sidecars, 86 background/setup
  sidecars. None of these are in Git.
- The engine has run 2,700+ frames in a longer session. The final MSAA-fix
  run rendered through frame 1,200 and logged 19-50 ms per frame (roughly
  20-50 FPS, with ~30 FPS observed in the earlier session).

## Root cause of the black presentation

With the default `MSAA = 2`, the engine renders the scene into a multisample
FBO and the direct resolve to the default framebuffer is silently dropped on
the Switch Mesa 20.1 nouveau path: the guest back buffer remains fully black
while the engine continues to render.

Forcing `MSAA = 1` made the engine render directly to the default framebuffer,
so the Dam scene appeared. That workaround was superseded on 2026-10-25: the
direct multisample-to-window blit is the broken step, and resolving into an
ordinary texture FBO first then blitting that texture to the window presents
correctly. See `patches/goldeneye-pc-port/switch-msaa-resolve.patch` and
`docs/evidence/goldeneye-20261025-input-msaa/README.md`.

## Evidence frames

The engine's `[Debug] FrameDump` hook captured the back buffer before swap
(`GE_PCDUMP`-equivalent), at 1224x918:

- Frame 300: the Dam facility, guard, truck, railings and mountains.
- Frame 700: first-person view of the Dam, Bond's pistol and HUD `7 | 93`.
- Frame 1200: first-person view with a guard ahead and the same HUD.

The raw captures are preserved outside Git in the local
`goldeneye-eden-first-scene-20261024` evidence directory alongside the final
NRO, engine log and Eden window screenshots. Only this summary is committed;
no ROM, sidecar, NRO or game frame is added to Git.

## Input status

Controller injection was not proven in that session. The Eden CLI frontend
booted the NRO and the game window received X focus, but `xdotool keydown
--window` uses XSendEvent, which SDL2 ignores, so the emulated controller
never changed. On 2026-10-25 the same frontend accepted XTEST events sent to
the PID-selected focused window: Start opened the Q Watch and the up arrow
moved Bond. Physical-Switch input remains to be validated.

## Reproduction

1. Build with the current patch set (including the MSAA resolve):

   ```sh
   source scripts/devkitpro-env.sh
   python3 scripts/build_goldeneye_native_engine.py \
     --work-dir <temp>/ge-engine --source <repos>/goldeneye-pc-port --jobs 2
   ```

2. Generate the private sidecars from the NTSC-U ROM:

   ```sh
   python3 tools_pc/d43_emit.py ntsc-final
   python3 tools_pc/d69_emit.py ntsc-final
   python3 tools_pc/d88_emit.py ntsc-final --regen
   ```

3. Put the NRO, the private ROM, and `data/pcmodels-*` / `data/pccg-*` in an
   isolated Eden profile. Run the CLI frontend on a display with a working
   Vulkan present queue.

4. Add `[Debug] FrameDump=1-8` (or another range) to the guest
   `data/ge007.ini` to capture the engine back buffer; captures are written
   to `ppm/frame_NNNNNN.ppm` in the guest directory.

## Limits

- MSAA resolves through the two-step Switch path; 1x/2x/4x verified and
  8x/16x requests are clamped to 4x. The `different_size` path is not
  exercised.
- The host audio sink receives game audio; mix correctness, mission
  completion and physical-Switch execution are not validated.
- The engine still uses Fast3D/Mesa/nouveau; the full deko3d backend remains
  unwired.
