# M2.9 — Castle Crashers real ReXGlue codegen and Linux host build

## Verified on the user's private authorized game (2026-10-19)

This milestone uses the **real** ReXGlue SDK and the original extracted Xbox 360
`default.xex`, not synthetic game code. The game files, compiled C++ and
executable remain private and are not included in the repository.

| Gate | Verified outcome |
|---|---|
| SDK | ReXGlue 0.10.0.24-dev.gbd833a2 official Linux amd64 |
| SDK archive checksum | SHA-256 `0a56565221a4e75f91fc71f787d9299a0d0298127b970c8a88a292f8d3a3befe` |
| XEX recognized | Title ID `584108B7`; version `0.0.1.3` |
| ReXGlue `init` | Exit 0, private manifest and CMake project |
| Initial `codegen` | Blocked: one `UnresolvedCall` to `0x820E15E8` |
| Function discovery fix | `0x820E15E8 = {}` as explicit function start |
| Complete official codegen | Exit 0, 41 files emitted; 17 C++ recompilation units |
| Generated C++ volume | Approximately 17.5 MB |
| Initial GCC build | Not suitable: weak function aliases missing; link failed |
| Clang compilation | Clang 17.0.0 in **experimental** mode; 25 build steps, exit 0 |
| Second boundary fix | `0x82112BC0 = { size = 988 }` |
| Linked Linux executable | ELF64 x86-64, **12,006,504 bytes**, no errors |
| Real Xbox guest gameplay | **Not independently verified** |
| Switch ARM64 NRO | **Not generated** |
| Menu / game frame | **Not rendered** |

The function-size hint was determined by examining authentic guest control
flow. Without it, three branch destinations inside `sub_82112BC0` were
missing from generated C++, causing missing-label compiler errors. The
final codegen emitted those labels and compiled successfully.

The official SDK recommends **Clang 20+**; Clang 17 succeeded for this
bounded host compilation, but this does not establish full supported runtime
compatibility. Prefer Clang 20+ on Linux Mint when available.

## Repeatable private build

Install the official Linux SDK to a private/user prefix. Keep the extracted,
authorized XEX outside Git.

```bash
python3 -m pip install tomli  # needed on Python 3.10 only

python3 -m nxlab.rex_native \
  --xex /private/castle/default.xex \
  --workspace /private/labnx-runs \
  --sdk-prefix /private/rexglue-sdk/linux-amd64 \
  --hints recipes/xbox360/castle_crashers_functions.toml \
  --compiler clang++ \
  --parallel 2 \
  --timeout 300
```

The tool creates an isolated private run directory, initializes a ReXGlue
project, copies only vetted function hints, invokes codegen, compiles with
CMake and links the native host executable. It generates a private
`report.json` with SHA-256 hashes and separate stage statuses.

Exit 0 means the **requested native build succeeded**; it never means the
game is playable. No source or binary is sent to GitHub, Bonsai or a hosted
agent. The host linker requires the SDK in `CMAKE_PREFIX_PATH`.

## First runtime smoke test — incomplete

A private Xbox 360 STFS package was separately extracted to **708** original
files under a game-data directory. Every entry was contiguous and the
extracted XEX hash matched its previous independent extraction.

The new native x86-64 executable started with an X11 virtual display
(`Xvfb`) and a private `--game_data_root` directory. The application
created a 1280×720 window; runtime threads were visible. The window was
**completely black** during a bounded 10–16-second smoke test.

This is **not** a valid game-originated frame. No Castle Crashers menu,
audio, controller behavior or actual gameplay was demonstrated. A future
graphics/runtime task must instrument the Xbox GPU command path and capture
verified game-originated frames.


## GPU backend preflight (after native link)

The all-black X11 window occurred with the ReXGlue GPU plugin disabled by
default (empty `gpu_plugin` cvar in this SDK). The Xenos plugin exists at
`<SDK>/lib/librexgpu-xenos.so`, but the SDK loader searches for this file
**next to the game executable**. Merely changing `LD_LIBRARY_PATH` does not
stage the plugin.

A verified local CMake change:

```cmake
rexglue_setup_target(castlecrashers GPU_PLUGINS xenos)
```

configured and rebuilt successfully, and staged the plugin beside the
executable. The same operation is now available through:

```bash
python3 -m nxlab.rex_native --xex /private/default.xex \
  --sdk-prefix /private/rexglue-sdk --workspace /private/runs \
  --hints recipes/xbox360/castle_crashers_functions.toml \
  --gpu-plugin xenos
```

At runtime, the official plugin must be enabled explicitly with
`--gpu_plugin xenos`. The Xvfb test with plugin staging returned exit code
**1**, rather than a real game frame. The isolated Linux environment has no
default installed Vulkan ICD; manually selecting Chromium SwiftShader exposes
a Vulkan 1.0.5 device, but this still did not complete presentation setup.
Its compatibility with the SDK is not established. **GPU ready: false**.

The private plugin binary and game files are never committed. A platform
with a compatible graphics driver is required for the next genuine rendering
test. A GPU library loaded or a window created is *not* a game-originated
frame.

## Specific engineering next steps

1. Extend the supervised runtime with a private process watchdog, diagnostic
   thread sampling and reproducible Xvfb screenshots, with strict cleanup.
2. Ensure the Xbox filesystem/game-data root resolves files correctly; record
   guest file-open failures and fix the first reproducible blocker.
3. Configure and test the ReXGlue Xenos GPU backend, using Vulkan software
   fallback where appropriate; obtain a **real** frame.
4. Instrument the first real game thread's progress, API imports and GPU
   commands; prioritize XAM/Xboxkrnl calls observed in traces.
5. Only after native graphics/input work, prepare ARM64/libnx/deko3d and
   produce an authentic NRO for Eden and hardware testing.

All game binaries, generated C++ and host executable stay private. This PR
only includes portable orchestration and address/size hints, not game bytes.
