# SOTC NX — M1 / MIPS→C++ boot translation (verified)

Date: 2026-10-19. Base: user-provided `Shadow of the Colossus (USA)` PS2 ISO, SHA-256 `d431a5b7e6c7009713d743c22ac5fd61077da40d5f7923e3250fe072a226eacb`. The original 32-bit little-endian MIPS boot executable is `SCUS_974.72`; SHA-1 `b715b3496aad6f7601a0ab8495acd1d151a1ff7b` matches the public SOTC decomp baseline.

## Confirmed (original disc, local host Linux x86-64)

- ISO9660 on-demand reader `ports/sotc/iso_disc.{h,cpp}` compiled and ran against original ISO. Its `probe.cpp` accessed `NICO.DAT` at offset 2,667,340,677 and EOF without extracting the 2.67 GB payload to RAM; 21 total directory entries indexed.
- Host C++ tests passed in debug mode, including nested paths, traversal rejection, corrupt directory pointers and correct EOF handling.
- GitHub Actions [run #39346836184](https://github.com/lloupp/lab-NX/actions/runs/39346836184): host tests **PASS**; devkitA64 ARM64 C++ **object compile PASS**; genuine upstream Celosia `ps2_recomp` x86-64 executable build **PASS**.
- The upstream `funcmap_elf.py` and `xff.py` were executed against the **real** original boot ELF and KERNEL.XFF: 912 named absolute KERNEL imports and 1,425 boot ELF functions identified, 847 named.
- Pinned upstream source: [HenryKun55/celosia at 0d5c35d](https://github.com/HenryKun55/celosia/tree/0d5c35dde50390ccf9a35aa7ae146cfe3ee92168), GPL-3.0. The actual compiled PS2Recomp was executed on the original user-provided ELF using Celosia `game/scus.toml` and the mapped imports:

| Report from actual PS2Recomp binary | Count |
| --- | ---: |
| Functions discovered / processed | 1,425 |
| Native C++ guest functions generated | 1,220 |
| Configured host stubs | 205 |
| Additional indirect entry points | 5,985 |
| Fallback promotions | 102 |
| Fallback entries | 5,066 |
| Decode failures | **0** |
| Unhandled instructions | **0** |
| Warnings | 102 |
| Errors | **0** |

The output directory contains approximately 14 MB of private, game-derived C++ source files (1,426 `*.cpp` files). This is **genuine recompilation of only the PS2 loader**; it is not the full game runtime, does not include KERNEL/MANAGER/GAMECORE code, and is not an ARM64 executable.

## Reproduce without committing proprietary files

Prerequisites: user's legally obtained `SCUS-97472` disc ISO, Celosia clone pinned to `0d5c35d`, and its built `ps2_recomp` executable (the game-free compiler from CI is sufficient).

```bash
python3 tools/sotc_boot_recompile.py \
  --iso "/private/Shadow of the Colossus (USA).iso" \
  --celosia "/path/to/celosia" \
  --recompiler "/path/to/ps2_recomp" \
  --work "/private/sotc-boot-stage1"
```

The script streams just SCUS_974.72 and KERNEL.XFF out of the ISO, recovers symbols, maps functions, invokes upstream PS2Recomp and leaves code/logs in the private directory. Never upload generated code or original binaries to public PRs, GitHub CI artifacts, or repository histories.

## Precise remaining integration work

1. Run the staged upstream Celosia boot runtime on its supported platform; capture `KERNEL.XFF`, `MANAGER.XFF` and `GAMECORE.XFF` at their actual load locations. Their code cannot be safely statically recompiled by simply feeding the unloaded XFF files to the compiler.
2. Recompile the combined fully relocated ELF, configure the host VFS to mount the new on-demand ISO streaming bridge, and link the resulting C++ through devkitA64/libnx. Avoid requiring the entire NICO.DAT in RAM.
3. Adapt actual native rendering and audio to Switch; Celosia's Vita/OpenGL and macOS/Metal implementations are references, not plug-and-play libnx/deko3d backends.
4. Validate a real generated NRO in Eden with original menu/gameplay frames and controllers; then validate RAM and frame times on physical Switch V2.

**Not yet proven:** native game NRO, running PS2 game on Eden, deko3d backend, hardware playability, full module recompilation. The ARM64 success reported above only proves that the portable ISO-streaming component compiled for devkitA64.
