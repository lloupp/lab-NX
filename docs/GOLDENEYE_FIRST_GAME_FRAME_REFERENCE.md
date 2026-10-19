# GoldenEye 007 — verified first original game frame (Linux N64 reference)

Date: 2026-10-19
PR: #13 / branch `feat/goldeneye-ptbr-localization`

## Results

**REAL N64 emulation succeeded** with the user's private, authenticated USA ROM, not synthetic art:

- Input: GoldenEye 007 USA .z64, SHA-1 `abe01e4aeb033b6c0836819f549c791b26cfde83`, CRC32 `B6330846`, 12 MiB.
- Emulator: Mupen64Plus Core 2.5.9, mupen64plus-video-rice OpenGL plugin, RSP HLE, core dynamic recompiler; Linux x86-64 under Xvfb + Mesa llvmpipe.
- ROM identified by actual emulator log as `GoldenEye 007 (U) [!]` with MD5 `70C525880240C1E838B8B1BE35666C3B`, N64 header CRC `DCBC50D1 09FD1AA3`.
- Executed Nintendo logo animation and the **original GoldenEye gun-barrel opening with the Bond character model, and later 3D cast/credits**. Real X11 screenshots were captured locally; the private captures were **not committed nor uploaded to public GitHub**.
- The first screenshots were black because Mupen64Plus package data (ROM database and RiceVideoLinux.ini) was omitted from its portable bundle. Adding official `mupen64plus.ini`, `RiceVideoLinux.ini`, and `InputAutoCfg.ini` to the runtime `--datadir` fixed initialization and produced nonblack game frames.
- The ROM was never transferred to GitHub Actions or included in a public artifact. CI workflows package open-source emulator and config without ROM; local environment runs its privately supplied copy.

## Private reproduction

The Linux Mupen64Plus reference emulator with upstream configs is a **separate test tool**, not an NX port.
After installing Mupen64Plus and its plugins locally:

```sh
# Requires a personal, legitimately sourced USA GoldenEye ROM.
xvfb-run -a -s '-screen 0 1024x768x24 +extension GLX +render -noreset' \
  mupen64plus --gfx mupen64plus-video-rice --rsp mupen64plus-rsp-hle \
  --windowed --resolution 640x480 /private/path/baserom.u.z64
```

Use `scrot` or `xwd` on the virtual display to capture original engine output.

## CLEAR BOUNDARY

This establishes **authentic running N64 game frames, in Linux emulation only**.

The Switch NRO `goldeneye-nx-loader.nro` renders a real ROM-derived Rareware graphic using a custom libnx framebuffer routine, but it still does NOT run the GoldenEye game engine, intro sequence, or a mission. A native game frame in Eden or physical Switch remains **unverified**, as do the PT-BR patch and gameplay integration.

## Next native milestone

Link Fast3D RSP (already successfully cross-compiled as an ARM64 .o) into a real Switch renderer backend, port the engine memory/addressing and host shims, and use evidence (actual frames in Eden or hardware) before claiming native GoldenEye game rendering. Do not replace the native proof with emulator screenshots.
