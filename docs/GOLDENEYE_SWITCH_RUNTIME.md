# GoldenEye 007 on Switch: ARM64 runtime stage (not gameplay)

## Verified progress (2026-10-19)

- N64 US ROM 12 MiB, original SHA1 `abe01e4aeb033b6c0836819f549c791b26cfde83`, CRC32 `B6330846`. Verified by the loader **locally from the user's supplied ROM** (no upload to GitHub).
- `nxlab/native/goldeneye_rom_runtime.c` validates native ROM header, CIC-6102 bootcode and N64 checksum, loads into an allocated 12 MiB buffer and rejects modified invalid headers.
- `nxlab/switch_loader/Makefile` compiles to a real AArch64 libnx `.nro` with devkitPro. The NRO is a **private-ROM preload / HID diagnostic**, NOT a game port, renderer or gameplay.
- `nxlab/native/goldeneye_switch_libnx.c` polls Joy-Con/Pro Controller input and `goldeneye_switch_input.c` converts it to Xbox-like independent semantic actions; the genuine GoldenEye engine does NOT consume those actions yet.
- Real GoldenEye PC Port source at pinned commit `fda76b69837e6c5aae436e0d3e798989e49b06d2` compiles as a Linux game engine using CMake on GitHub Actions. This is not a Switch build.
- Extra CI probes compile a genuine `port/fast3d/gfx_cc.cpp` object as Switch AArch64. A single graphic component does **not** constitute the renderer.

## Fetch the ROM-free NRO artifact

Go to [GitHub Actions: GoldenEye engine ARM64 path](https://github.com/lloupp/lab-NX/actions/workflows/goldeneye-engine-path.yml) and open the newest successful run, then choose `goldeneye-nx-rom-loader-nro` under **Artifacts**. The archive contains `goldeneye-nx-loader.nro`.

Manual build when devkitPro + devkitA64/libnx are installed:

```sh
cd nxlab/switch_loader
make -j2
```

Place the NRO and a **privately owned** ROM on the Switch microSD:

```
sdmc:/switch/goldeneye-nx-loader.nro
sdmc:/switch/lab-nx/goldeneye/baserom.u.z64
```

An alternate patched ROM is looked up first at `sdmc:/switch/lab-nx/goldeneye/ge007.ptbr.z64`, but it must have correct N64 checksums. If the translation patch creates a ROM of different size/layout, sidecar extraction must be rechecked.

Run via hbmenu; the loader prints ROM status, checksum, and controller values. Press **+** to exit. **It cannot show GoldenEye graphics or start a mission**, even with a valid ROM. No physical hardware run is claimed.

## Next engine integration path (required for gameplay)

1. Replace the PC-only **fixed-address virtual mappings** and absolute-ROM-symbol assumption (`port/src/romdata.c`, `port/src/romassets_u.s`, `portaddr.h`) with Switch-safe address translation or explicitly reserved mapping, while validating game pointer semantics. The simple heap preload used by this NRO is not a drop-in replacement for the current engine mapping.
2. Implement the `GfxRenderingAPI`/window-manager backend for Switch (deko3d or a proven compatible GPU API), adapting Fast3D display-list output, textures, render targets, depth and shaders. Upstream presently uses OpenGL.
3. Port other host shims (thread/timer/fs/audio and startup), then wire `goldeneye_switch_input.c` actions directly into gameplay and menus.
4. Generate `pcmodels`/`pccg` sidecars privately from the original ROM using GoldenEye PC Port tools; verify that a PT-BR patch preserves the expected offsets and texture/font layouts.
5. Compile a **real game NRO** from reconstructed source, verify actual frames/mission in Eden and test on physical Switch V2.

**Do not mark the project playable** before steps 1–5 have real runtime evidence. Keep PR #13 in draft. Do not commit any copyrighted ROM, font, textures, data sidecars, firmware or console keys.

## Source / licensing

- GoldenEye PC Port: https://github.com/jkdansereau/goldeneye-pc-port
- Its original port layer is MIT-licensed; inherited decompilation sources have separate provenance and are **not** represented as MIT.
- Official Switch examples: https://github.com/switchbrew/switch-examples
