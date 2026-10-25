# Controller input, MSAA and host audio in Eden — 2026-10-25

## Result

Three gates from the first Dam frame are now covered in official Eden 0.2.1:

1. **Host input reaches the guest's emulated controller.** Pressing Start
   opens the in-game Q Watch pause screen, and holding the up arrow moves
   Bond forward (the left stick is driven by `emulate_analog_keyboard`).
2. **MSAA presents on the Switch Mesa/nouveau path.** MSAA 2x (the engine
   default) and 4x render the Dam scene. 8x/16x targets are not presented by
   this path, so the engine clamps the Switch MSAA level to 4x instead of
   leaving a black screen.
3. **Guest audio reaches the host sink.** A monitor capture of a PipeWire
   null sink contains the game audio: silent during boot, then RMS
   1,253–3,073 for the rest of the run.

The verification NRO is 8,249,400 bytes, SHA-256
`e97de4923c2a0cc7dada537664b4c285b9aecbfa721e7fead7e03b7aec8e66ae`,
built from the pinned engine with the repository patch set, including
`patches/goldeneye-pc-port/switch-msaa-resolve.patch` (SHA-256
`26dbed2df997e37e4480884a616ad6235173bc90be786d0d993f4688605c11b6`).
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
2. Select the window owned by the Eden process. Searching by PID alone is
   not enough because the AppImage wrapper forks; select by
   `WM_CLASS=eden-cli` and never by a title that merely contains "Eden" (an
   early run focused a terminal and typed into it).
3. `xdotool windowfocus --sync <id>` and `windowraise`.
4. Inject with XTEST: `xdotool keydown <keysym>` / `keyup` **without**
   `--window`.

With Eden's default keyboard profile (`keyboard_enabled=true`,
`emulate_analog_keyboard=true`), `m` is Start (SDL scancode 16) and the arrow
keys drive the left stick (up = scancode 82). Evidence in the
`final_input_and_msaa2` run:

- `00_before.png`: first-person Dam view before input.
- `01_watch.png`: Q Watch opened by Start — an unambiguous guest reaction.
- `02_up_held.png` / `03_after_move.png`: camera moved forward while the up
  arrow was held, then settled after release.

## MSAA root cause and fix

Guest GL is Mesa 20.1.0-rc3, GL 4.3 compatibility profile,
`GL_MAX_SAMPLES=8`. Rendering into a multisample FBO works, and
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

## 8x/16x clamp

The same resolve works at 2x and 4x, but an 8x multisample target is never
presented by this Eden/Mesa path: with the pre-clamp build, MSAA 8x stayed
black at both 320x240 (mean 0.0037, 10 colours) and 640x480 (mean 0.0019,
5 colours), while 4x at 320x240 and 2x/4x at the default 1224x918 presented.
16x is already outside the driver's `GL_MAX_SAMPLES=8`.

The engine now clamps the Switch MSAA level to 4x before creating the
framebuffer and logs:

```text
[WARN ] video: Switch MSAA above 4x is not presented; clamping to 4x
```

With the clamp, an 8x request presents at 4x at the default window size
(mean 0.192, 16,161 colours) and 16x presents at 320x240 (mean 0.241,
11,437 colours). The clamp is a safety limit, not evidence that 8x works on
physical hardware; that remains untested.

## Verification

- **MSAA levels:** 1x, 2x and 4x present the Dam natively. 8x/16x requests
  present at the clamped 4x.
- **Antialiasing:** a horizontal scanline across the watch ring edge
  (y=200, paired runs) shows one coverage step at 1x and two at 2x:
  - 1x: `0,0,0` → `184,58,14` → `255,80,20`
  - 2x: `0,0` → `111,35,9` → `225,70,18` → `255,80,20`
- **Render time at frame 600** (llvmpipe software Vulkan, not hardware):
  1x 14.3 ms, 2x 35.4 ms, 4x 38.6 ms. MSAA costs roughly 2.5x here; the
  two-step resolve adds one full-frame copy per frame.
- **Input:** Start and left-stick-up both reach the guest in the final run,
  which also renders at MSAA 2x.

## Host audio capture

The guest engine opens an SDL audio device at 22050 Hz; Eden resamples and
plays through its host sink. To prove samples actually leave the emulator,
the harness was run with `--host-audio --audio-sink lab_null
--audio-record .../audio/game-msaa2.wav` after creating a PipeWire null sink
(`pactl load-module module-null-sink sink_name=lab_null`). Nothing was
audible on the physical output.

The 57.69 s WAV (peak 15,818, overall RMS 2,260) is silent for the first
5 s of boot and then carries game audio for the rest of the run:

```text
 0- 5 s  RMS    0.0
 5-10 s  RMS 1253.6
10-15 s  RMS 1503.6
15-20 s  RMS 1723.5
20-25 s  RMS 2274.0
25-30 s  RMS 2442.8
30-35 s  RMS 2759.0
35-40 s  RMS 2837.0
40-45 s  RMS 2744.0
45-50 s  RMS 3072.9
50-55 s  RMS 2814.2
55-57 s  RMS 2114.5
```

This proves the guest audio path reaches the host sink. It does not judge
mix correctness, individual sound effects, or live interaction.

## Reproduction

```sh
python3 scripts/eden_input_probe.py \
  --eden <Eden.AppImage> \
  --nro <goldeneye-native-engine-msaa-resolve.nro> \
  --rom <GoldenEye 007 (USA).z64|.zip> \
  --data-dir <guest data/ with pcmodels-* and pccg-*> \
  --display :0 \
  --msaa 2 --frame-dump 700-700:1 \
  --sequence watch-move --wait-frame 600
```

For audio, create a null sink, then add:

```sh
pactl load-module module-null-sink sink_name=lab_null
python3 scripts/eden_input_probe.py ... \
  --host-audio --audio-sink lab_null \
  --audio-record evidence/audio/game.wav
```

An Xvfb display is not sufficient for Eden's Vulkan frontend on this host:
lavapipe needs DRI3 and reports `Device lacks a present queue`. Use a real X
display or another Vulkan device with a present queue.

## Evidence layout

Raw artifacts are preserved outside Git in
`007/goldeneye-eden-input-msaa-20261025/`:

- `run-20261025-121110-xtest/`: final NRO, input sequence and MSAA 2x.
- `run-20261025-120658-xtest/` and `audio/game-msaa2.wav`: host audio
  capture at MSAA 2x.
- `run-20261025-120951-xtest/`: 8x request clamped to 4x, default window.
- `run-20261025-120855-xtest/`: 16x request clamped to 4x, 320x240.
- `run-20261025-115922-xtest/`: pre-clamp 8x black screen (320x240).
- `run-20261025-120820-xtest/`: clamp validation on an intermediate build.
- Pre-clamp 1x/2x/4x controls: `run-20261025-031251-xtest` (1x),
  `run-20261025-031121-xtest` (2x), `run-20261025-031337-xtest` (4x) and
  `run-20261025-031632-xtest` (1x watch control). That build differs from
  the final NRO only by the >4x clamp.
- `goldeneye-native-engine-msaa-resolve.nro`, `SHA256SUMS`,
  `MANIFEST.json`.

No ROM, firmware, keys, sidecar or game frame is added to Git; only this
summary is committed.

## Limits

- Physical Switch execution and mission completion remain unvalidated.
- 8x/16x do not present through this Eden/Mesa path and are clamped to 4x;
  whether physical hardware presents them is unknown.
- The `different_size` MSAA path (game viewport smaller than the window) was
  not exercised. The normal aspect modes keep the dimensions and viewport
  equal, so the tested path is the one the engine uses by default.
- Audio capture proves samples reach the host sink, not mix correctness or
  interactive audio behaviour.
- The engine still renders through Fast3D/Mesa/nouveau; the full deko3d
  backend remains unwired.
