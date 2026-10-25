# Local validation — 2026-10-22

This record captures local build and diagnostic results for PR #25. Checksums and outcomes are in `manifest.json`.

- `switch_deko_smoke` built as an AArch64 NRO using the pinned Docker SDK and again with the extracted local SDK. The optional `GE_UPSTREAM` build also compiled the `GfxRenderingAPI` adapter against the pinned PC-port header.
- The full experimental engine cross-build completed from upstream commit `fda76b69837e6c5aae436e0d3e798989e49b06d2`; its NRO contains the bounded Fast3D trace format string. This proves compilation/linkage only, not that the game engine emitted a display list.
- Host ASan/UBSan bridge/memory tests and the portal-bounds regression passed. The complete Python test run had three skips.
- clangd parsed the ARM64 smoke and adapter translation units using the compilation database. Its driver query returned the devkitA64 newlib include paths; the command database uses `/opt/devkitpro/libnx/include`, `/opt/devkitpro/portlibs/switch/include`, and the pinned upstream Fast3D interface header.
- Eden 0.2.1 was launched with the smoke NRO and logged the frontend `BootGame` event. The process was terminated before a guest SD trace appeared. No submitted frame or rendered image was verified, so this is recorded as a failed/incomplete runtime attempt, not a pass.

The earlier synthetic triangle evidence remains separate in `docs/evidence/goldeneye-20261020/`. Neither record proves a frame containing original GoldenEye game geometry. No ROM, keys, or proprietary game assets are stored in this directory.
