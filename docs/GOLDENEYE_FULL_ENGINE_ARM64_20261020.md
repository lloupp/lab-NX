# Complete engine ARM64 experiment — 2026-10-20

## Latest session result (supersedes the early stall interpretation)

The complete ARM64 engine and Dam loader execute in an actual Switch NRO in official Eden. A longer local diagnostic run processed/swapped more than 600 real engine frames, but the captured presentation remained black. This is **not verified visible gameplay or mission completion**.

The unmodified devkitPro OpenGL triangle visibly rendered at 60 FPS despite the same Maxwell `Invalid insn` messages. Those messages alone therefore do not identify the GoldenEye blocker. SDL/EGL drawable/context/presentation behavior remains under investigation. An experimental EGL-size fallback did not establish visible gameplay and is not included in the published validated patch.

The portal scanner fix, real kernel register sampling and actual-scanner ASan/UBSan regression are published in `47cdb72`. The full-engine cross-build plus portal regression passed remotely: https://github.com/lloupp/lab-NX/actions/runs/39456713980 . The separate deko3d diagnostic's three jobs also passed: https://github.com/lloupp/lab-NX/actions/runs/39456713888 . Neither workflow proves full-game gameplay.

During a diagnostic source build of Eden with the macro-cache fix, the Work execution environment stopped accepting new processes and file access, preventing further runtime checks. No successfully executed patched-Eden build is claimed. The full deko3d engine backend and physical Switch validation remain incomplete.

## What is real

The complete pinned reconstructed game (upstream `fda76b69837e6c5aae436e0d3e798989e49b06d2`) cross-compiles and links as an AArch64 Switch NRO. Its original CMake source lists include the game, scheduler, audio, reconstructed engine, Fast3D interpreter and renderer. The executable was launched in official Eden 0.2.1 with a privately supplied NTSC-U ROM and locally converted sidecars. Logs confirm entry through the real `mainproc`, cart mapping, 512 model sidecars, 86 background/collision/setup sidecars, shared RDRAM views, audio/controller initialization and game threads. The portal-bound fix subsequently allows `lvlStageLoad()` to finish for Dam, including player/object setup and the final level-control checkpoint.

**First-mission gameplay has not been demonstrated. Early short captures reported zero rendered frames; the later longer run above advanced beyond 600 while presentation stayed black. No physical Switch was available in this environment.**

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
- Host-header routing is adapted for newlib. Subprocess conversion/restart and network update checks are disabled for the Switch build; missing conversion remains a reported failure. A watchdog can sample actual callback registers with `svcSetThreadActivity` / `svcGetThreadContext3` / immediate resume. It reports every SVC result and raw PC/LR/SP/FP, not a fabricated stack trace.

The N64 Makefile, linker script and RSP sources are untouched. The upstream patch is applied only to a disposable source copy. Initial boot checkpoints are conditional Switch diagnostics.

## Validation and limits

- Python regression suite: 92 tests, 1 skipped, passed.
- Memory diagnostic: real ARM64 NRO, built with `-Wall -Wextra -Werror`, executed in official Eden; all recorded alias/lifecycle checks pass.
- Complete engine: all 253 build steps including final link pass locally with devkitA64 GCC 16.1.0. Existing upstream warnings remain; this is not a warning-free build.
- Private converters report all checks passed. Their output remains outside the repository.
- Engine startup and stall evidence is recorded separately from the memory diagnostic. No rendered gameplay, mission completion or performance claim follows from those results.
- The complete-engine CI build passed: https://github.com/lloupp/lab-NX/actions/runs/39454406279 (commit `9f0d976`). The new CI workflow is a build-only check. The previously approved deko3d diagnostic workflow does not validate the complete-engine path.

Next acceptance gate: resolve black presentation in the complete engine, reach a submitted real game display list and verify a visible Dam frame plus controller-driven movement. Then implement/validate the complete deko3d rendering path and repeat on physical Switch hardware.

Earlier pre-portal-fix NRO SHA256: `6120987c40c461c90319ac0a4cceba258ccc6143d5d6965b769100af7f85f8a6` (8,237,112 bytes; compiled from the published engine patch). The matching fresh-profile trace reaches the first font ROM copy and then records zero-frame heartbeats. The screenshot shows a stalled renderer, not gameplay.

## Follow-up: actual stall found and corrected

The last file-log line was an incomplete indicator: kernel register sampling found the main callback repeatedly inside `sub_GAME_7F0B37EC`, called by `load_bg_file`, not in the font loader. The scanner used `&g_BgCurrentRoom` as its table end, relying on the next global remaining adjacent to `specialportalarray`. ARM64 host layout does not guarantee that ordering/padding. Reading past the 20-byte table eventually entered an endless byte-index range ending in 255. The host path now uses the actual array extent and pointer-width comparison; N64 code keeps its original path.

`tests/native/test_goldeneye_portal_bounds.py` extracts and compiles the actual scanner and table from the pinned source plus this patch. ASan/UBSan tests exercise 3 level cases, including both authored range sets. The original adjacency boundary reproduces a global buffer overflow with separated host symbols; the corrected boundary passes. No ROM is involved in this regression.

After the fix, the full Dam level loader reaches its final video/control initialization checkpoints. Official Eden 0.2.1 then emits Maxwell shader decoder assertions (`Invalid insn`, including zero words) on the Mesa/nouveau path. Rendered-frame count remains zero. These messages also occur in a working SDK triangle, so they do not establish the root cause. Black presentation after mission loading remains unresolved. The original font-loading interpretation is superseded by these register and sanitizer results.

Current portal-fixed NRO SHA256: `fdd17cb00557502b40e36349c5f15686d50375e8369d1d9336277e4b798c7633` (8,237,112 bytes). See `portal-fixed-build-manifest.json` and the matching `engine-portal-fixed.txt` / `eden-mesa-shader-errors.txt`.
