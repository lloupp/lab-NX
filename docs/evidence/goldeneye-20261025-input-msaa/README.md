# Controller input and Switch MSAA resolve in Eden — 2026-10-25

## Result

Two open gates from the first Dam frame are closed in official Eden 0.2.1:

1. **Host input reaches the guest's emulated controller.** Pressing Start
   opens the in-game Q Watch pause screen, and holding the up arrow moves
   Bond forward (the left stick is driven by `emulate_analog_keyboard`).
2. **MSAA presents on the Switch Mesa/nouveau path.** MSAA 2x (the engine
   default) and 4x now render the Dam scene; the previous "force MSAA=1"
   workaround is removed.

The verification NRO is 8,249,400 bytes, SHA-256
`9c8fe6400db0de21ca97bedda7b5de24ab7f8038cc388bd4c132c9a76ed4eba1`,
built from the pinned engine with the repository patch set, including
`patches/goldeneye-pc-port/switch-msaa-resolve.patch` (SHA-256
`5fb6f469a706fdf9bf06eb8884286dc2961784d07da7730af19d88d991556c1f`).
Runs used the `eden-cli` frontend on the host X display (`:0`) with
Vulkan/lavapipe. Physical Switch hardware remains unvalidated.

## Why keyboard injection failed before

`eden-cli` is the yuzu_cmd SDL2 frontend. It forwards `SDL_KEYDOWN` /
`SDL_KEYUP` scancodes to `InputCommon::Keyboard::PressKey`, so the emulated
controller path itself was fine. The earlier harness sent
`xdotool keydown --window <id>`, i.e. XSendEvent. SDL2's X11 backend does not
process those synthetic events, so the guest never saw a button change even
though the harness logged `input_sent=true`.

The working recipe:

1. Start the game and wait for the engine's frame log.
2. Select the window owned by the Eden PID (`xdotool search --pid`), not a
   window whose title merely contains "Eden" (an early run focused a terminal
   and typed into it).
3. `xdotool windowfocus --sync <id>` and `windowraise`.
4. Inject with XTEST: `xdotool keydown <keysym>` / `keyup` **without**
   `--window`.

With Eden's default keyboard profile (`keyboard_enabled=true`,
`emulate_analog_keyboard=true`), `m` is Start (SDL scancode 16) and the arrow
keys drive the left stick (up = scancode 82). Evidence in the
`input_and_msaa2` run:

- `00_before.png`: first-person Dam view before input.
- `01_watch.png`: Q Watch opened by Start — an unambiguous guest reaction.
- `02_up_held.png` / `03_after_move.png`: camera moved forward while the up
  arrow was held, then settled after release.

## MSAA root cause

Guest GL is Mesa 20.1.0-rc3, GL 4.3 compatibility profile,
`GL_MAX_SAMPLES=8`. Rendering into a 2x multisample FBO works, and
`glBlitFramebuffer` from that FBO **directly into the default framebuffer**
reports `GL_NO_ERROR` with both framebuffers `GL_FRAMEBUFFER_COMPLETE`
(`0x8cd5`) — yet the window back buffer stays black. The guest's own
`glReadPixels(GL_BACK)` returns zeros, so this is not just an Eden
presentation problem.

A one-shot probe at frame 300 isolated the path:

| Operation | GL error | Result |
| --- | --- | --- |
| MSAA FBO → default framebuffer (direct) | 0 | back buffer black |
| MSAA FBO → ordinary RGB8 texture FBO | 0 | full scene (mean 0.228) |
| Texture FBO → default framebuffer | 0 | full scene (mean 0.228) |

Both steps work; only the direct multisample-to-window blit is dropped.
The fix keeps the multisampled colour buffer, resolves it into a cached
ordinary texture FBO, and then blits that texture into the window back
buffer:

```text
MSAA renderbuffer --glBlitFramebuffer--> cached RGB8 texture FBO
cached texture    --glBlitFramebuffer--> default framebuffer
```

The cached texture is recreated only when the render size changes. This is
enabled on `__SWITCH__` only; desktop keeps the upstream single-step resolve.

## Verification

- **MSAA levels:** 1x, 2x and 4x all present the Dam scene. 8x/16x were not
  run; the guest reports a maximum of 8 samples.
- **Antialiasing:** a horizontal scanline across the watch ring edge
  (y=200, paired final runs) shows one coverage step at 1x and two at 2x:
  - 1x: `0,0,0` → `184,58,14` → `255,80,20`
  - 2x: `0,0` → `111,35,9` → `225,70,18` → `255,80,20`
- **Render time at frame 600** (llvmpipe software Vulkan, not hardware):
  1x 14.3 ms, 2x 35.4 ms, 4x 38.6 ms. MSAA costs roughly 2.5x here; the
  two-step resolve adds one full-frame copy per frame.
- **Input:** Start and left-stick-up both reach the guest in the same run as
  MSAA 2x.

## Reproduction

```sh
python3 scripts/eden_input_probe.py \
  --eden <Eden.AppImage> \
  --nro <goldeneye-native-engine-msaa-resolve.nro> \
  --rom <GoldenEye 007 (USA).z64|.zip> \
  --data-dir <guest data/ with pcmodels-* and pccg-*> \
  --display :0 \
  --msaa 2 --frame-dump 640-660:10 \
  --sequence watch-move --wait-frame 600
```

An Xvfb display is not sufficient for Eden's Vulkan frontend on this host:
lavapipe needs DRI3 and reports `Device lacks a present queue`. Use a real X
display or another Vulkan device with a present queue.

## Evidence layout

Raw artifacts are preserved outside Git in
`007/goldeneye-eden-input-msaa-20261025/`:

- `run-20261025-031121-xtest/`: input sequence plus MSAA 2x.
- `run-20261025-031251-xtest/`: MSAA 1x control (no input).
- `run-20261025-031337-xtest/`: MSAA 4x control (no input).
- `run-20261025-031632-xtest/`: input sequence plus MSAA 1x (paired AA control).
- `goldeneye-native-engine-msaa-resolve.nro`, `SHA256SUMS`,
  `MANIFEST.json`.

No ROM, sidecar, NRO or game frame is added to Git; only this summary is
committed.

## Limits

- Physical Switch execution, audio interaction and mission completion remain
  unvalidated.
- MSAA 8x/16x are untested; the two-step resolve is sample-count agnostic but
  only 1x/2x/4x were exercised.
- The `different_size` MSAA path (game viewport smaller than the window) was
  not exercised. The normal aspect modes keep the dimensions and viewport
  equal, so the tested path is the one the engine uses by default.
- The engine still renders through Fast3D/Mesa/nouveau; the full deko3d
  backend remains unwired.
