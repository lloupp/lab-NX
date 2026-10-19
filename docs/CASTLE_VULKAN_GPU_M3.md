# Castle Crashers M3.0 — Verified Vulkan/Xenos preflight and guest dispatch repair

This is an evidence-only guide based on **authorized, private** Castle Crashers
Xbox 360 files. No game content, keys, shaders, generated guest code or
native game executables are in the repository.

## Confirmed runtime diagnosis (2026-10-19)

- **No ICD:** Xenos fails to create a Vulkan instance (`ErrorIncompatibleDriver`).
- **Chromium SwiftShader:** a Vulkan 1.3 device exists, but
  `geometryShader=false`. The original Xenos startup rejects the device
  while `vulkan_require_geometry_shader=true`.
- **Explicit diagnostic override:** when
  `--vulkan_require_geometry_shader=false`, the Vulkan presenter **did
  create a 1280x720 swapchain** on SwiftShader. This is GPU setup, not a
  genuine game-rendered frame; disabled geometry shaders may break rendering.
- **Mesa Lavapipe:** recovered the official Debian 13 package
  `mesa-vulkan-drivers_25.0.7-2+deb13u1_amd64.deb` through a GitHub
  Actions run containing **no game files**. SHA-256 was verified against
  Debian's published value
  `caf2f7d296b7522efe74e40a74bce762a3ce84c33b53b5e54e1248ac2e0a13a5`.
  Staged it privately with `dpkg-deb -x`, never installed globally.
  Physical device enumeration succeeded:
  `llvmpipe (LLVM 19.1.7, 256 bits)`, **Vulkan 1.4.305**,
  **geometryShader=true**.
- **Guest runtime fault:** with Lavapipe selected, a native abort backtrace
  resolved to ReXGlue's `rex::runtime::InvalidFunctionTrap` inside the
  recompiled game. The runtime's own critical log identified an indirect call
  to **guest address `0x82114E20`** as unregistered.
- **Function discovery repair:** disassembled genuine PowerPC instructions
  at `0x82114E20`, added the function start to the private ReXGlue
  manifest, regenerated guest C++ with **exit code 0** and rebuilt the native
  x86-64 executable with **exit code 0**.
- **Retest:** with Lavapipe, the repaired executable remained running during
  the **8-second bounded test**, without the previous `InvalidFunctionTrap`.
  Three screenshots of the Xvfb screen taken over 8 seconds were all
  **completely black (one RGB color, 0/0/0)**. There is no verified Castle
  Crashers frame, menu, audio or gameplay.
- **Other prior issue:** in earlier no-GPU runtime runs, huge logs repeatedly
  reported guest read of `0x00000010`. This may be a separate bug; not
  proven resolved. Use bounded log collection, otherwise logs can grow >1 GiB.

**Current status: recompilation and native build succeeded; Vulkan software
device can initialize; guest dispatch progresses past one trap; no playable game.**

## No-root Lavapipe setup (Debian 13 AMD64)

Download the *official, pinned* package from Debian or use the short-lived
GitHub Actions artifact of `mesa-lavapipe-package.yml`. Run:

```bash
python3 -m nxlab.vulkan_probe stage \
  --deb /private/mesa-vulkan-drivers.deb \
  --out /private/labnx-lavapipe

python3 -m nxlab.vulkan_probe probe \
  --icd /private/labnx-lavapipe/labnx-lavapipe-icd.json
```

The stage tool rejects nonmatching SHA-256, refuses to overwrite existing
folders and never modifies a system ICD setting. It writes an ICD JSON
pointing to the extracted `libvulkan_lvp.so` by an absolute path.
On a normal Linux Mint PC with a capable GPU, prefer that system's
driver over software emulation.

## Diagnostic run after native build

With the private Xenos library **staged alongside the game executable**,
and the authorized assets extracted privately:

```bash
ICD=/private/labnx-lavapipe/labnx-lavapipe-icd.json
SDK_LIB=/private/rexglue-sdk/lib

timeout 10s xvfb-run -a env \
  LD_LIBRARY_PATH="$SDK_LIB" \
  VK_DRIVER_FILES="$ICD" VK_ICD_FILENAMES="$ICD" \
  MESA_SHADER_CACHE_DISABLE=true SDL_AUDIODRIVER=dummy \
  /private/build/castlecrashers \
  --game_data_root /private/castle-assets \
  --gpu_plugin xenos \
  --log_level critical \
  --log_file /private/castle-critical.log
```

**Log file may contain user-specific runtime data:** keep it outside Git.
Use `--log_level critical` while diagnosing a fatal error to avoid GB-scale
repeated-error logs. A black window is not a passed rendering test.

## Next engineering steps

1. Add bounded runtime trace recording and actual game-originated frame
   counters, without accepting synthetic output.
2. Diagnose the guest execution path after the repaired indirect dispatch:
   real XAM/Xboxkrnl file/profile state, guest virtual memory, initial
   threads and GPU command submissions.
3. Observe a real Xenos draw / swap and capture its resulting genuine frame.
4. Verify controller interaction in host build, then continue toward
   ARM64/libnx/deko3d NRO and Eden.

`geometryShader=true` in the Vulkan doctor means this one GPU requirement
is satisfied; **it does not certify full device compatibility or gameplay**.
