# Adapter-enabled full engine: guest log recovered — 2026-10-24

## Result

The adapter-enabled full-engine NRO boots in official Eden 0.2.1, writes the
guest log, reaches `gfx_run`, and converts live engine-origin Fast3D batches
through the adapter sink.

- NRO: 8,249,400 bytes, SHA-256
  `15d833d0ebffe66a6eab13c2316e4ba341787ac7b084c53c656bbf56b2a3e355`.
  This is the same build configuration as the earlier `672e7122...` artifact,
  with additional boot markers added to `ge_engine_switch_runtime.c`.
- Build: pinned `devkitpro/devkita64:20260219`, devkitA64 GCC 15.2.0;
  `GE_FAST3D_TRACE=1`, `GE_FAST3D_ENGINE_ADAPTER=1`;
  `deko3d_backend_enabled=false`.
- Run: official Eden 0.2.1, Intel Vulkan on the host display, private NTSC-U
  ROM and locally generated sidecars (512 model sidecars, 86 bg/setup
  sidecars). No ROM, sidecar, or NRO is in Git.
- The guest reached `gfx_run`; 2,700+ frames were rendered and Eden's status
  bar reported about 33 FPS / 30 ms.
- Adapter: 46 batches of the measured fog/texture profile
  `d000030d12181218:00000012` converted successfully (`result=0`); 82 batches
  of other observed profiles were rejected fail-closed (`result=2`).
  GPU submission remains unwired.
- Presentation is still black; no original GoldenEye frame is claimed.

## Why the previous attempt produced no log

The earlier adapter-enabled Eden attempt recorded no guest `engine.log`. The
same NRO reproduces that symptom when Eden cannot initialize its Vulkan
present queue under Xvfb/Lavapipe (`Device lacks a present queue`,
`Failed to initialize VideoCore`): the guest is never started. Running the
same NRO on the host display with Intel Vulkan boots it and creates the log
immediately. This is an emulator/display initialization failure, not an NRO
startup crash.

## Boot markers

`fsdevMountSdmc()` returned `0x559`, but `chdir` returned 0 and both
`freopen` handles were non-null; the engine wrote `engine.log`, `boot-early.log`,
and the model/background sidecars. The runtime now writes absolute-path markers
before and after `chdir`, so a future mount or working-directory failure leaves
evidence instead of an empty profile.

## Log summary

- 175 `[GE_FAST3D_ADAPTER]` lines: 1 attach, 128 batch results, 46 successful
  CPU conversions.
- 384 `[GE_FAST3D_TRACE]` lines for frames 0..63 (bounded trace).
- 128 `fast3d-render-list` batches with these shader keys:

  | Batches | Shader key | Adapter result |
  |---:|---|---|
  | 46 | `d000030d12181218:00000012` | converted (`result=0`) |
  | 32 | `1000020d0000818a:00000013` | unsupported (`result=2`) |
  | 25 | `320d020d818a818a:00000012` | unsupported (`result=2`) |
  | 11 | `0000000000000000:00000000` | unsupported (`result=2`) |
  | 9 | `020d020d818a818a:00000013` | unsupported (`result=2`) |
  | 3 | `d000030d12181218:00000112` (clamp-S) | unsupported (`result=2`) |
  | 2 | `d000d00010001000:00000013` | unsupported (`result=2`) |

- The trace and adapter counts match exactly, confirming the adapter observes
  the same batches recorded by the trace hook.
- `engine.log`: 87,025 bytes raw with embedded NULs; 86,984 bytes after
  removing NULs. Raw SHA-256
  `3dd5ffdc1ad4877b84e85ca7c19dad7939b18b7eb60190feefebdf415bbaf484`;
  sanitized SHA-256
  `92f05fe681706f532668a79ce23c8c95c28e8f8b7cdcc860415241f1affe8cf0`.
- The raw log, instrumented NRO, Eden log, boot markers, and screenshot are
  preserved outside Git in the local `goldeneye-eden-adapter-live-20261024`
  evidence directory. This report contains only the summary.

## Reproduction

1. Build the adapter engine from the pinned upstream with the local SDK:

   ```sh
   source scripts/devkitpro-env.sh
   python3 scripts/build_goldeneye_native_engine.py \
     --work-dir <temp>/ge-engine --source <repos>/goldeneye-pc-port --jobs 2
   ```

2. Generate the private sidecars in the PC-port checkout (ROM and output stay
   outside Git):

   ```sh
   python3 tools_pc/d43_emit.py ntsc-final
   python3 tools_pc/d69_emit.py ntsc-final
   python3 tools_pc/d88_emit.py ntsc-final --regen
   ```

3. Run Eden on a display whose Vulkan driver has a present queue. Copy the
   NRO, private ROM, `pcmodels-*`, and `pccg-*` into the emulated SD profile.
   Xvfb/Lavapipe may fail before guest startup; use a host display with Intel
   Vulkan for this configuration.

4. Inspect the guest `engine.log` and `boot-early.log` under
   `sdmc:/switch/lab-nx/goldeneye/`.

## Limits

- The adapter conversion is CPU-only; no deko3d draw or submit exists
  (`GPU submit not wired`).
- The game still presents through Fast3D/Mesa/nouveau; the black frame is
  unresolved.
- No physical Switch run and no original GoldenEye frame, menu, or mission.
