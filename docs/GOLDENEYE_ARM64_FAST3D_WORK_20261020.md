# GoldenEye NX — ARM64 / Fast3D / deko3d, 2026-10-20

## Result

The `dkQueueCreate()` blocker is bypassed in **unmodified official Eden 0.2.1** by independently uploading each exported deko3d MME macro suffix. The guest returns from queue creation and submits 120+ diagnostic frames. A screenshot shows the generated RGB triangle with the Eden status bar reporting 60 FPS.

This is a real ARM64 Switch NRO executing deko3d commands, **not GoldenEye gameplay, a game display list, or physical Switch validation**.

![Generated diagnostic triangle in a fresh Eden profile, not gameplay](evidence/goldeneye-20261020/triangle-fresh-profile.png)

## Preserved work

- Started at PR #24 head `869cef26cfa6c91ff881c69ac67cab31aa6fe0e6`, branch `feat/goldeneye-native-engine-integration`.
- Reviewed PR #13 (ROM validation, logo decoder, input, crossbuilds) and PR #19 (deko3d bootstrap). Their branches are unchanged.
- `d932006` is absent from this clone. No claim is made about its content; this session does not overwrite or recreate it.
- The supplied USA ROM passed the existing private load/CRC/CIC and logo decoding checks. ROM and decoded assets stay outside Git.

## Queue diagnosis

1. The SDK diagnostic reaches `queue-create-lean-start`; Eden throws `std::bad_alloc` or `std::length_error`.
2. Unmodified switchbrew `deko_basic`, built from `669786898205b7beb25ff1731e72982e6d0397d3`, throws the same length error.
3. GDB cannot start its inferior (`ptrace: Operation not permitted`). An in-process `__cxa_throw` observer captures the stack instead, without changing guest instructions or recovering exceptions.
4. Eden release binary build ID `c30f1493fd0259834c9b13b7c7d072a5805af1fb` fails at offsets `0xedc078`, `0xcbaee2`, `0xcb965b`, `0xd2df6a`. Disassembly shows vector resizing after insertion into a compact map.
5. Eden v0.2.1 source, mirror commit `58c1e20ee58efa3900ba616207d460886214480b`, has the corresponding `MacroEngine::Execute` mid-macro path. It retains a vector reference inside `ankerl::unordered_dense::map`, inserts another entry, then reads the invalidated reference. The pinned dependency `7b55cab8418da1603496462ce3ccdb4cb1dc3368` reproduces this as an ASan **heap-use-after-free** in the isolated regression.
6. `patches/eden/v0.2.1-macro-cache-lifetime.patch` materializes the suffix before insertion and fixes a separate stale/end iterator in macro dumping. **The isolated corrected algorithm passes; a complete patched Eden executable was not built.**
7. The optional dekotools patch avoids mid-macro extraction by uploading every exported suffix directly. GPU instruction addresses/bytes and entry bindings remain identical: **181 instructions / 14 exports**, checked byte for byte. Queue command memory remains 64 KiB.
8. A second baseline compiled from the **same pinned deko3d source**, with the original generator, still fails. With the modified generator, queue creation returns and the triangle appears. A repeat without the exception observer also renders the triangle and reaches 120+ frame submissions. The earlier repeat is `triangle-repeat-without-observer.png`; the final trace-reset fix is captured in `triangle-fresh-profile.png`, with its NRO hash in `manifest.json`.

The Work environment exposes Mesa 25.2.8 llvmpipe software Vulkan, no physical GPU. The status bar varied between 1 and 60 FPS across captures; stable performance has not been benchmarked. The screenshot proves a rendered diagnostic, not 60 FPS game performance. The observer also saw caught Vulkan exceptions during the successful run; this is not treated as a validated long-term stability result.

## Fresh-profile startup regression

The first remote Eden run exposed a separate failure before the first guest trace. A SIGSEGV observer localized it to the emulator's filesystem `DeleteDirectory` path: our new trace reset used newlib `remove()` on a nonexistent file before creating its parent directories. The fallback directory-delete request reached a null parent in Eden. Existing local SD directories had hidden this problem.

Commit `a74139e` creates the trace parents and truncates the file using `fopen(..., "w")`, avoiding that request. A completely empty local XDG data/config profile then rendered the triangle and submitted 120+ frames; `triangle-fresh-profile.png` and `guest-fresh-profile.txt` record this test. CPU fastmem experiments did not resolve the filesystem failure and were removed. CI uses ordinary CPU defaults and isolated XDG paths.

The NRO downloaded from the successful CI ARM64 build was also executed locally and rendered correctly. That confirms the remote build artifact separately from the remote emulator run. The remote tests/build passed; final cold-profile Eden CI results must be read at the run linked from PR #24. No failed execution is treated as a pass.

## Incremental engine-facing code

`nxlab/native/goldeneye_n64_memory.[ch]` implements an explicit 8 MiB arena with bounded physical, PC-port V1, KSEG0/KSEG1 and reverse translations, plus Fast3D segments. Segment 5 precedence and tagged offsets follow the upstream convention. Unknown addresses, unbound segments and overflow fail before returning a pointer.

The NRO stages its generated VBO in this arena and verifies physical/KSEG0 aliasing before the bridge. **This does not make direct engine dereferences at fixed addresses safe.** Upstream `dram.c`, absolute `dram_syms.S`, cart mappings and direct pointer conversions still need a coordinated adaptation, compared with the unavailable local work.

`nxlab/engine_adapter/goldeneye_gfx_subset.[h|cpp]` compiles against the real `GfxRenderingAPI` header at GoldenEye PC Port `fda76b69837e6c5aae436e0d3e798989e49b06d2`. All current callbacks are assigned. Unsupported operations latch an error until reinitialization and suppress later draws.

Only canonical single-cycle SHADE RGB (`id0=0x1000`, `id1=0`), full-screen viewport/scissor and no depth/alpha/textures are accepted. Tests verify this shader ID with upstream `gfx_cc.cpp`. The NRO calls the API, which feeds the validated VBO bridge and deko3d vertex memory. The sink consumes input before GPU use; there is no dynamic fenced streaming yet.

**The full `gfx_pc.cpp` interpreter and reconstructed game engine are not linked into this NRO.** Existing ARM64 interpreter crossbuilds are preserved. The new arena transport is not connected to the game's fixed-address ABI.

## Reproduce

Install devkitA64, libnx, deko3d, uam, native C/C++ compilers, Python 3, meson, ninja, flex, bison, make and git. Set `DEVKITPRO` normally. Check out the pinned PC port outside this repository:

```sh
python3 scripts/build_goldeneye_deko_compat.py \
  --work-dir <fresh-build-directory> --upstream <pinned-pc-port-checkout>
```

The script fetches exact deko3d/dekotools commits, builds an original header, applies the upload patch in its own checkout, compares GPU RAM images, and builds `nxlab/switch_deko_smoke/goldeneye-deko-mme.nro`. **The complete script was executed successfully locally.** Installed SDK libraries are not replaced.

The ordinary SDK build remains `make -C nxlab/switch_deko_smoke`. Use separate `BUILD` directories when changing compile-time options. All diagnostic NROs contain only generated geometry and open-source shaders.

## Verification and remaining gates

- Existing Python suite: 92 tests, 1 skipped.
- Native input, Fast3D bridge, private ROM and private logo checks pass.
- New N64 translation, upstream API and pinned macro-cache tests pass under ASan/UBSan. The original macro-cache pattern fails under ASan as expected. LeakSanitizer is disabled locally because process inspection is unavailable; GitHub Actions retains normal settings.
- Real ARM64 loader, SDK diagnostic, adapter diagnostic, official deko_basic, source baseline and MME compatibility diagnostic compile. DKSH shaders are generated with uam.
- The final NRO contains the memory translator and real rendering API adapter symbols.
- Updated CI builds both SDK/MME diagnostics and executes the MME version in Eden. Submission markers are necessary; captured pixels require separate inspection. Remote CI results must be checked after push.

Remaining gates: full engine memory/host ABI, real display lists, dynamic fenced buffers, combiner/textures/depth/blending, input/audio, and the first mission. **The first mission objective is not achieved. Physical Switch execution is untested.**

Evidence: `docs/evidence/goldeneye-20261020/`. No ROM, original assets, firmware, keys or proprietary data are included.

## Follow-up: bounded runtime telemetry and multi-triangle RGB batches

The full-engine build now applies `patches/goldeneye-pc-port/fast3d-runtime-trace.patch`. With `GE_SWITCH`, `gfx_run()` logs up to 64 engine display-list entries and `gfx_flush()` logs up to 128 non-empty batches: shader key/options, float count/stride, triangle count, shader inputs/texture mask, alpha/modulate, RDP/geometry modes, and one transformed vertex sample. It does not dump ROM bytes or the full vertex buffer. The log prefix is `[GE_FAST3D_TRACE]` in the existing engine log. This instrumentation has passed an x86-64 host build with the trace define enabled; the full Switch cross-build is now wired to PR CI.

The deko diagnostic VBO was enlarged to hold the Fast3D bridge's maximum 256-triangle batch for its existing untextured RGB profile. Bridge tests now cover a two-triangle input. The smoke fixture remains synthetic and is not the source of the full-engine trace below; the adapter is still not wired into the engine's real `gfx_flush()` callback.

## Local ARM64/LSP validation update — 2026-10-22

The pinned `devkitpro/devkita64:20260219` image was validated and exported to the user-local SDK path; both the standalone deko3d smoke and the `GE_UPSTREAM` API-adapter variant built as ELF64/AArch64. The complete experimental engine also cross-built from the pinned PC-port revision with the bounded `[GE_FAST3D_TRACE]` instrumentation in the binary. The build manifest records the NRO hash and explicitly keeps `gameplay_verified` false. Python source-archive extraction now retains the Python 3.12 data filter where available and validates path/type entries before using the Python 3.11 fallback.

A Dockerized clangd setup now generates a non-committed compilation database and successfully checks the Switch smoke and adapter sources. clangd queried devkitA64 and resolved the SDK's newlib, libnx and deko3d include paths plus the pinned upstream `GfxRenderingAPI` header. Host C bridge, memory-compatibility, and portal-bounds sanitizer tests pass; the Python suite reports 89 passed and 3 skipped in this checkout.

The earlier local Eden 0.2.1 smoke launch reached the frontend `BootGame` event but did not produce a guest `deko_boot_trace.txt`; it is not a rendered-smoke pass. A subsequent run of the **full trace-enabled engine NRO**, with the private NTSC-U ROM and all generated sidecars in an isolated Eden SD profile, reached `gfx_run` frame 0 and recorded 128 nonempty Fast3D batches. The first stable triangle profile was `d000030d12181218:00000012` (19-float stride, three RGB inputs, TEXEL0, fog and two-cycle, no alpha). It differs from the adapter's canonical SHADE-only RGB profile. The run did not prove a presented game frame; the screenshot was the Eden frontend. A bounded CPU converter for this measured profile and a live `gfx_flush()`-to-adapter observer are now linked in a fresh ARM64 engine build (`672e7122b141bcc65b1ba3e2f7475dadfaca96434045aaaea5c28434fefb6733`). That manifest explicitly says `deko3d_backend_enabled=false`; the subsequent adapter-enabled Eden attempt produced no guest log, so live conversion and presentation are not yet proven. Sanitized trace evidence and the raw local log hash are in `docs/evidence/goldeneye-20261022-fullengine-trace/`; the raw log and ROM-derived data remain outside Git.

## Live adapter conversion recovered — 2026-10-24

The adapter-enabled full-engine NRO now produces a guest log and converts
live engine-origin Fast3D batches in official Eden 0.2.1. The instrumented
build (8,249,400 bytes, SHA-256
`15d833d0ebffe66a6eab13c2316e4ba341787ac7b084c53c656bbf56b2a3e355`) uses
the pinned `devkitpro/devkita64:20260219` SDK, `GE_FAST3D_TRACE=1`, and
`GE_FAST3D_ENGINE_ADAPTER=1`; `deko3d_backend_enabled` remains false.

The earlier "no guest log" symptom was an Eden graphics-initialization
failure, not an NRO startup crash. Under Xvfb/Lavapipe Eden reports
`Device lacks a present queue` and `Failed to initialize VideoCore`, so the
guest never starts. The same NRO on the host display with Intel Vulkan boots
immediately, writes `engine.log` and `boot-early.log`, and reaches `gfx_run`.
The runtime now writes absolute-path boot markers before and after `chdir`;
`fsdevMountSdmc` returned `0x559`, `chdir` returned 0, and both log handles
were valid.

The run rendered 2,700+ frames; Eden's status bar reported about 33 FPS /
30 ms. The adapter observed 128 `gfx_flush()` batches and converted 46 of the
measured fog/texture profile `d000030d12181218:00000012` (`result=0`). The
other 82 batches were rejected fail-closed (`result=2`): 32
`1000020d0000818a:00000013`, 25 `320d020d818a818a:00000012`, 11 zero keys,
9 `020d020d818a818a:00000013`, 3 clamp-S `d000030d12181218:00000112`, and 2
`d000d00010001000:00000013`. The trace and adapter profile counts match
exactly. Conversion remains CPU-only: no deko3d draw or submit is wired, and
the presented game frame is still black. No original GoldenEye frame, menu,
mission, or physical-Switch result is claimed.

Evidence summary: `docs/evidence/goldeneye-20261024-adapter-live/README.md`.
The raw log, instrumented NRO, Eden log, boot markers, and screenshot are
preserved outside Git; the raw log is 87,025 bytes (SHA-256
`3dd5ffdc1ad4877b84e85ca7c19dad7939b18b7eb60190feefebdf415bbaf484`) and
contains embedded NULs.

## First original Dam scene visible — 2026-10-24

The complete ARM64 engine now presents the first original GoldenEye scene in
official Eden 0.2.1. The Dam loads, fades in, and reaches the first-person
view with Bond's pistol and the ammo HUD (`7 | 93`). The final NRO is
8,249,400 bytes, SHA-256
`43476785ab6ee3a9af7db606194e07bea9a0811b991c5f4c3d69e9302ed18bb3`; the
engine has run 2,700+ frames in a longer session and 1,200+ frames in the
MSAA-fix run, at roughly 20-50 ms per frame.

The black presentation at the time came from the default `MSAA = 2` path: the
scene rendered into a multisample FBO and the direct resolve to the default
framebuffer was silently dropped on the Switch Mesa 20.1 nouveau path. The
temporary `MSAA = 1` workaround was superseded on 2026-10-25 by the two-step
resolve in `patches/goldeneye-pc-port/switch-msaa-resolve.patch` (see the
input/MSAA section below).

Controller injection was not proven in that session: the harness used
XSendEvent, which SDL2 ignores. On 2026-10-25 XTEST with a PID-selected,
focused Eden window reached the guest controller (Start opens the Q Watch and
the left stick moves Bond); see below. Physical-Switch execution and mission
completion remain unvalidated.

Evidence summary:
`docs/evidence/goldeneye-20261024-first-dam-frame/README.md`. The raw engine
log, final NRO, frame captures and Eden screenshots are preserved outside Git
in the local first-scene evidence directory.

## Controller input and MSAA resolve in Eden — 2026-10-25

Host keyboard input now reaches the guest. `eden-cli` forwards SDL key events
to the emulated controller, but only for real server input: `xdotool
keydown --window` (XSendEvent) is ignored by SDL2. The working harness
(`scripts/eden_input_probe.py`) selects the window owned by the Eden PID,
focuses it, and sends XTEST key events. With the default keyboard profile,
Start opens the in-game Q Watch and holding Up moves Bond forward.

MSAA is fixed rather than bypassed. The guest Mesa/nouveau path drops a
multisample `glBlitFramebuffer` aimed directly at the default framebuffer
without reporting an error; the back buffer stays black. Resolving the
multisample buffer into an ordinary texture FBO, then blitting that texture
into the window back buffer, produces the correct image. The resolve is in
`patches/goldeneye-pc-port/switch-msaa-resolve.patch`, is compiled on
`__SWITCH__` only, and replaces the removed `switch-msaa-default.patch`.
The path presents up to 4x: an 8x multisample target stays black under this
Eden/Mesa combination, so the renderer clamps Switch MSAA above 4x and logs a
warning. 8x/16x requests therefore present at 4x instead of blacking out.

Host audio was also captured through a PipeWire null-sink monitor: the 57.7 s
recording is silent during boot and then carries game audio (RMS
1,253-3,073), proving the guest audio path reaches the host sink.

Verified under official Eden 0.2.1 on the host X display: MSAA 1x, 2x and 4x
present the Dam; the watch-ring scanline shows the expected extra coverage
step at 2x. Frame 600 render times under software Vulkan were 14.3 ms (1x),
35.4 ms (2x) and 38.6 ms (4x), so this is a functional proof, not a
performance claim. Verification NRO: 8,249,400 bytes, SHA-256
`e97de4923c2a0cc7dada537664b4c285b9aecbfa721e7fead7e03b7aec8e66ae`.

Evidence summary:
`docs/evidence/goldeneye-20261025-input-msaa/README.md`. Raw screenshots,
frame dumps, logs and the final NRO are preserved outside Git in the local
input/MSAA evidence directory.

## Sources and licenses

- GoldenEye PC Port: https://github.com/jkdansereau/goldeneye-pc-port
- deko3d: https://github.com/devkitPro/deko3d
- dekotools: https://github.com/fincs/dekotools — GPL-3.0; source patch retains upstream obligations.
- Eden source: https://git.eden-emu.dev/eden-emu/eden/src/tag/v0.2.1/src/video_core/macro.cpp — its GPL-3.0-or-later/GPL-2.0-or-later source notices apply to the patch.
- Official diagnostic: https://github.com/switchbrew/switch-examples/tree/master/graphics/deko3d/deko_basic

Third-party source is fetched for builds, not vendored. Patches do not relicense the rest of lab-NX.
