# Castle Crashers — first real Switch NRO (stage 0, NOT gameplay)

This folder produces an authentic **ARM64 Nintendo Switch NRO** using the
official devkitPro devkitA64, libnx, and elf2nro. It is a toolchain,
filesystem and controller *bootstrap*, **not a port of the game yet**.
The commercial executable is not embedded in it.

## What it does

- Starts on Switch Horizon via libnx and creates a plain diagnostic console.
- Reads, but does **not** decrypt or execute, an operator-owned XEX from
  `sdmc:/switch/labnx/castle/default.xex`.
- Validates XEX2 header bounds, Title ID `584108B7`, declared image size,
  PowerPC entry point, compression and encryption type.
- Polls controller input using `padInitializeDefault`, `padUpdate` and
  `padGetButtonsDown`. Press **+** to exit the diagnostics.
- Clearly identifies itself as non-playable; no commercial assets, startup
  videos, graphics or shaders are bundled or rendered.

The same XEX parser is compiled and independently tested on x86-64.
On 2026-10-19 it additionally passed against the **real Castle Crashers
default.xex** recovered privately from the authorized 146,616,320-byte XBLA
STFS container. Title ID and entry point were as expected.

## Build on a Linux/Windows machine with devkitPro

```sh
cd switch/castle_bootstrap
DEVKITPRO=/opt/devkitpro make -j2
# writes castle_nx_bootstrap.nro
```

For repeatable CI, see `.github/workflows/castle-switch-nro.yml`: builds with
`devkitpro/devkita64:20260219`, compiles a host fixture, verifies the NRO0
header and publishes the unsigned, noncommercial .nro artifact.

To launch on the **physical Switch** using Homebrew Menu, copy
`castle_nx_bootstrap.nro` to:

```text
sdmc:/switch/castle_nx_bootstrap.nro
```

Copy **your own** extracted `default.xex` privately to the following path
on the SD card:

```text
sdmc:/switch/labnx/castle/default.xex
```

On Eden, mount the same relative path in Eden's emulated `sdmc` directory;
its exact host location depends on the profile/configuration. This file is
private and **must not** be committed to GitHub or attached to CI artifacts.

## Eden smoke verification

The workflow downloads the official Eden v0.2.1 Linux AppImage, opens the
actual NRO under Xvfb and saves screenshots and logs for inspection.
It must **not** classify an open Eden window, a timeout, a black frame, or
a missing-keys dialog as successful ARM64 guest execution.
A successful stage-0 result must visibly show the program's explicit
`lab-NX / Castle Crashers Switch bootstrap` banner in an emulator screenshot,
or contain an independently verifiable guest-execution trace.

## What is NOT implemented

- PowerPC game code linked into this NRO.
- ReXGlue's Linux/x86-64 runtime ported to Horizon/libnx.
- Xbox memory, kernel/XAM/Xboxkrnl ABI, game asset loading and filesystem VFS.
- Xenos graphics translated to deko3d, authentic Castle Crashers frames,
  working game menu, audio or gameplay.
- Controller input wired to an actual Castle Crashers game thread.

The successful **Linux** ReXGlue project (full game-origin codegen and native
x86-64 title screen) is a separate achievement. Its Linux ELF executable and
host libraries cannot simply be copied or relinked as a Switch NRO.

## Technical next stage: first guest routine inside libnx

1. Produce freestanding ARM64 objects from a restricted, verified subset of
   the private, game-derived ReXGlue C++ (not public source).
2. Design a Switch-compatible `PPCContext` and bounded guest memory interface
   with correct big-endian semantics and exception handling.
3. Link a small real guest-origin routine to the bootstrap NRO **privately**,
   prove deterministic inputs/outputs on Switch/Eden and reject false evidence.
4. Expand Xbox service import contracts, thread dispatch, file loading and
   graphics commands via libnx/deko3d.
5. Capture a true game-originated frame and prove title/menu/gameplay.

The NRO distributed from this directory intentionally contains no game code.
