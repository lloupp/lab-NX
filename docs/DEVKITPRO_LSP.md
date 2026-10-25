# devkitPro ARM64 and LSP setup

The local SDK used for builds is the same pinned `devkitpro/devkita64:20260219` image used by CI. Its compiler, libnx/deko3d headers, libraries, and `uam` are installed under `~/.local/share/devkitpro/20260219`.

## Local ARM64 build

Source the environment helper, then build the smoke NRO or full engine. Keep separate `BUILD` directories for host and container builds because their dependency files contain different absolute paths:

```sh
source scripts/devkitpro-env.sh
make -C nxlab/switch_deko_smoke -j2 \
  BUILD=build-host TARGET=goldeneye-deko-host ROMFS=romfs-host
python3 scripts/build_goldeneye_native_engine.py \
  --work-dir /tmp/ge-engine-build --jobs 4
```

The smoke target uses the actual devkitA64 compiler and SDK headers. The engine script archives the pinned PC-port revision into a fresh work directory and does not bundle a ROM.

## clangd diagnostics with target headers

VS Code's clangd extension launches `scripts/devkitpro-clangd.sh`. It builds the local `lab-nx/devkitpro-lsp:20260219` helper image when needed and runs clangd inside the pinned SDK image, so `/opt/devkitpro/libnx/include` and the installed Switch portlib headers are real SDK headers, not host stubs. The wrapper also queries devkitA64 for its target system include paths.

Generate the compilation database once (or after changing build flags):

```sh
scripts/configure_devkitpro_lsp.sh
```

This compiles the smoke target and graphics API adapter with `bear`, using the real pinned `GfxRenderingAPI` header from the adjacent `goldeneye-pc-port` checkout. Set `GE_UPSTREAM=/path/to/goldeneye-pc-port` if that checkout is elsewhere. The absolute-path compilation database is intentionally ignored by Git. Restart clangd after regenerating it.

The LSP scripts fall back to `sg docker` when the active process has not inherited the supplementary group. For normal Docker commands, log out and back in (or start a `newgrp docker` shell); do not broaden `/var/run/docker.sock` permissions.
