# Complete engine ARM64 experiment — 2026-10-20

## What is real

The complete pinned reconstructed game (upstream `fda76b69837e6c5aae436e0d3e798989e49b06d2`) cross-compiles and links as an AArch64 Switch NRO. Its original CMake source lists include the game, scheduler, audio, reconstructed engine, Fast3D interpreter and renderer. The executable was launched in official Eden 0.2.1 with a privately supplied NTSC-U ROM and locally converted sidecars. Logs confirm entry through the real `mainproc`, cart mapping, 512 model sidecars, 86 background/collision/setup sidecars, shared RDRAM views, audio/controller initialization and game threads.

**First-mission gameplay has not been demonstrated. The heartbeat still reports zero rendered frames. No physical Switch was available in this environment.**

This experiment uses **Fast3D / Switch Mesa / nouveau (OpenGL)**. It does not claim that the complete engine uses deko3d. The earlier deko3d triangle and restricted SHADE RGB API adapter remain separate and preserved. Textures, combiners, depth, fog and alpha in a full deko3d backend still need implementation and validation.

## Build

Install the standard devkitPro AArch64 toolchain/libnx and Switch portlibs `switch-sdl2`, `switch-mesa`, `switch-zlib` with their dependencies (including `switch-libdrm_nouveau`). Also install Python 3.12+, CMake and Ninja.

```sh
export DEVKITPRO=/opt/devkitpro
python3 scripts/build_goldeneye_native_engine.py --work-dir /tmp/ge-engine-build --jobs 4
```

An existing upstream checkout can be supplied with `--source /absolute/path/to/goldeneye-upstream`. The script archives the exact pin, excluding working-tree edits. It refuses to overwrite a nonempty workspace. The generated `build-manifest.json` records the pin, compiler, NRO hash, renderer and unverified gameplay status.

No ROM, sidecars, firmware or keys are accepted, fetched or bundled by the build script. The full-engine NRO includes arrays already compiled by upstream's source list; do not publish that binary to GitHub. The build workflow uploads only its JSON manifest.

## Private runtime data

The experimental entry selects `-level_33` (Dam). It mounts SD and works under `sdmc:/switch/lab-nx/goldeneye/`. The engine writes `engine.log` and `engine-stdout.log` there. The private ROM and upstream-converted `pcmodels-ntsc-final`/`pccg-ntsc-final` directories belong under its `data/`. Generate these locally using upstream's `d43_emit.py`, `d69_emit.py`, and `d88_emit.py --regen`; do not commit their output. This is an experimental developer launch path, not a release installation flow.

## Memory and ABI changes

- `svcMapProcessMemory` needs a real own-process handle. Use the homebrew-supplied handle when available; otherwise copy the current-process pseudo handle through a self IPC session and verify its process ID.
- Heap `Normal` pages are not eligible source memory for this SVC. The experiment uses page-aligned static `CodeData`/BSS backing. Guest tests demonstrate bidirectional sharing, cleanup, live-map rejection and overlap rejection.
- RDRAM V1 remains `0x70000000`. The mirror moves to `0x60000000`: the usual `0x80000000` window overlaps Eden's NRO load region in observed launches. Port address constants and five raw pointer reconstruction expressions follow the new mirror. N64 builds keep their existing behavior.
- Cart data is mapped at `0x10000000` with an auxiliary alias at `0x30000000`. Static backing reserves 96 MiB; larger converted images fail rather than silently falling back to an incompatible heap address.
- Game callbacks need low stacks because the reconstructed code deliberately casts some stack pointers to `u32`. libnx pthread creation cannot directly use the mapped static alias as its startup stack (`ENOMEM`). A small AAPCS64 trampoline retains pthread's normal TLS/startup/cleanup stack while running the callback on an 8 MiB low alias. The callback returns to the original stack before pthread cleanup. Cancellation or exception unwinding across this trampoline is unsupported; the port uses cooperative thread termination. Static capacity is 16 callbacks per launch; slots are not recycled.
- Existing x86-64-specific prototype, image-table, model-hit-pool, music-memory, audio and display-list pointer fixes are also enabled for ARM64 port builds. These are ABI/layout adaptations, not mission-logic changes.
- Scope the game's `strtol` symbol to `geN64Strtol` in C translation units, avoiding a duplicate definition when newlib's internal parsing code also pulls its CRT implementation.
- Host-header routing is adapted for newlib. Subprocess conversion/restart and network update checks are disabled for the Switch build; missing conversion remains a reported failure. Thread-dump support is explicitly unavailable rather than returning fabricated backtraces.

The N64 Makefile, linker script and RSP sources are untouched. The upstream patch is applied only to a disposable source copy. Initial boot checkpoints are conditional Switch diagnostics.

## Validation and limits

- Python regression suite: 92 tests, 1 skipped, passed.
- Memory diagnostic: real ARM64 NRO, built with `-Wall -Wextra -Werror`, executed in official Eden; all recorded alias/lifecycle checks pass.
- Complete engine: all 253 build steps including final link pass locally with devkitA64 GCC 16.1.0. Existing upstream warnings remain; this is not a warning-free build.
- Private converters report all checks passed. Their output remains outside the repository.
- Engine startup and stall evidence is recorded separately from the memory diagnostic. No rendered gameplay, mission completion or performance claim follows from those results.
- The new CI workflow is a build-only check. The previously approved deko3d diagnostic workflow does not validate the complete-engine path.

Next acceptance gate: resolve the stall in `load_font_tables()` inside `lvlStageLoad()` for Dam, reach a submitted real game display list and verify a visible Dam frame plus controller-driven movement. Then implement/validate the complete deko3d rendering path and repeat on physical Switch hardware.
