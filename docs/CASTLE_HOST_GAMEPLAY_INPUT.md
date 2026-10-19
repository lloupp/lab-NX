# Castle Crashers — real native gameplay input verified (Linux host)

## Confirmed on 2026-10-19

- Original, privately supplied Xbox Live Arcade game, Title ID `584108B7`.
- ReXGlue SDK `v0.10.0.24-dev.gbd833a2`, generated C++ and linked Linux
  x86-64 binary; Xenos GPU backend and private Mesa Lavapipe ICD active.
- SDL audio initialized with a **temporary private ALSA null sink**.
- ReXGlue keyboard-to-Xbox controller emulation enabled with
  `--mnk_mode=true` (default is disabled).
- Input was injected through a local `Xvfb` display using XTEST. The ReXGlue
  default mapping is `Return -> Start`, `Space -> A`,
  `A/D -> left-stick horizontal`, and `L -> X`.
- **Directly observed transitions in the real game:**
  1. Original title screen, `Press Start`.
  2. `Return` advanced to Xbox Live notice, `A Continue / B Back`.
  3. `Space` advanced to first-level demo instructions.
  4. Continued to `Character Select`, displaying the green knight.
  5. Confirmed green knight selection; the game loaded an original castle
     interior scene.
  6. After the intro, the game reached the first phase with an on-screen
     character, HUD, NPCs and animated environment.
  7. Holding `A` for 2 seconds and then `D` for 3 seconds visibly moved
     the green knight, with the camera following.

The host build has therefore reached **limited real gameplay with movement**
on Linux x86-64. This is more than a splash-screen demo, and is distinct
from the still-unverified **Nintendo Switch port**.

### Evidence (hashes only, no game screenshots committed)

| Screenshot | Verified SHA-256 |
|---|---|
| Before Start | `d37b34f7a5acf43f4c928b540bd362b2613fef2080eabaaea1cff5f0c7b88dab` |
| Xbox Live confirm screen | `aaacfba4703386c3c633537d29d1c36a90a7f5fa481e476cd61ebd2c00f5eb67` |
| Demo level instructions | `d195d0a4161af83cc6d3bcde9f0280e37fa517a0079090d0d3b79bf01e7faa49` |
| Character selection | `225fcccfd493060ec44727091b4a0f56d1bf964da690eae5f8b7c3bd1638154b` |
| First castle scene | `e7d4465c3f801a0ee8e7ad79094d4c54e9899bc78a211a8aa4bba7d198ac3f25` |
| Moved left | `90121a7a0f8faccfeadd86be192016f9763ec072cae915725f4b77ae5f0fa905` |
| Moved right | `0ae720b7e45adcbc607ff2d330d89cd40db4ce905f08f969028ed46b93b8576d` |

Only hashes and metadata are public. The screenshot images remain in the
owner's private working area. Visual confirmation was performed on those
local images; a hash change on its own is not proof of gameplay.

## Reproduce the input test

First launch your **private host-compiled** `castlecrashers` under Xvfb
with the original game-data directory. Example command in an already-started
local X11 virtual display (`DISPLAY=:125` is illustrative):

```bash
export DISPLAY=:125
export LD_LIBRARY_PATH=/private/rexglue-sdk/lib
export VK_DRIVER_FILES=/private/labnx-lavapipe-icd.json
export VK_ICD_FILENAMES="$VK_DRIVER_FILES"
export SDL_AUDIODRIVER=alsa
export ALSA_CONFIG_PATH=/private/alsa-null.conf

/private/build/castlecrashers \
  --game_data_root /private/castle-assets \
  --gpu_plugin xenos --mnk_mode=true \
  --log_level critical \
  --log_file /private/critical.log
```

The `ALSA_CONFIG_PATH` file must be a local operator-controlled playback
sink when there is no audio device; the standalone diagnostic tool in
`nxlab/runtime_watch.py` can create a temporary null sink.

After the character is in the castle gameplay area (not during the splash
or character-select screens), send bounded keyboard actions:

```bash
python3 -m pip install python-xlib Pillow

# Only for an operator-controlled local Xvfb with access already permitted:
XAUTHORITY=/dev/null python3 -m nxlab.x11_input_probe \
  --display :125 \
  --workspace /private/host-gameplay-evidence-001 \
  --plan recipes/xbox360/castle_host_controls.json
```

The probe sends only whitelisted keys, takes original private screenshots
before/after each action, records SHA-256 hashes and requires **human review**
to declare any gameplay milestone. It never downloads, packages or publishes
the game. The `XAUTHORITY=/dev/null` example only applies to an isolated,
operator-created `Xvfb -ac -nolisten tcp` test instance; retain normal
X11 authentication for ordinary desktops.

## Still incomplete

- The package displays **`Unlock Full Game`** and may be a trial build.
  The test did not bypass licensing or unlock restricted content.
- Combat effectiveness, saving, full-level progression and longer stability
  are **not yet verified**.
- This run executed natively on **Linux x86-64**, **not ARM64**.
- No Switch NRO, libnx/deko3d compatibility, Eden or physical hardware
  gameplay has been achieved.

The next major work item is a genuine ReXGlue ARM64/Switch backend, not
renaming the Linux ELF to a NRO. Keep separate gates for host gameplay and
Nintendo Switch gameplay.
