# Full-engine Fast3D trace — 2026-10-22

This is the first new Eden run in this PR that launched the **trace-enabled full engine with the authorized private NTSC-U ROM and locally generated sidecars** (not `switch_deko_smoke`). The source NRO was the previously preserved AArch64 build from upstream `fda76b69837e6c5aae436e0d3e798989e49b06d2`:

- NRO SHA-256: `d3caf5fd167cd8162c9951bf694c97cd2b3088ed0e1b0c13c45a5ca60ac01a63`
- SDK/compiler: `devkitpro/devkita64:20260219`, `aarch64-none-elf-gcc 15.2.0`
- Eden: official 0.2.1, Vulkan/Intel Mesa host
- Runtime data: 512 model sidecars and 86 background/setup sidecars generated in an isolated temporary workspace; the ROM and generated sidecars remain outside Git.
- Raw guest log SHA-256: `7973f255ac57bc95c580a2405f43945031764448110b7d8668b1f3c4a98650c7` (kept in the local temporary Eden profile; not committed because it contains full runtime diagnostics and embedded NULs).

## Observed game-origin batches

`engine.log` proves this guest initialized ROM and sidecars, reached Dam level loading, started the render worker, and entered `gfx_run` for frame 0. The bounded trace recorded 128 nonempty `gfx_flush()` batches before the configured cap. The first seven lines have shader key `0:0` but varying layout/texture/input metadata; they are not treated as a reliable shader-key mapping because the patch currently updates shader-key telemetry from the triangle path while rectangles can also flush the VBO.

The first stable nonzero Fast3D shader profile is:

```text
shader_id0=d000030d12181218  shader_id1=00000012
stride=19 floats  inputs=3  texture_mask=1  alpha=0  modulate=0
other_mode=0099ac20:c4112078  geometry=00002205
```

This profile appeared 70 times in the first 128 batches. A clamp-S variant (`shader_id1=00000112`) appeared 5 times with a 20-float stride. The first exact untextured RGB profile supported by the existing adapter (`0x1000:0`, stride 7, one input, no texture/depth/alpha) **did not occur** in these traces. The observed profile is a one-texture, fogged, two-cycle combiner with three RGB inputs. A bounded CPU bridge converter for this exact 19-float profile is now implemented and tested; it does not yet upload textures or submit a deko3d draw. The clamp-S variant remains fail-closed.

Other observed keys in the same first-frame trace include `320d020d818a818a:00000012` (two texture units, stride 21) and `1000020d0000818a:00000013` (alpha enabled). These are recorded as later candidates, not implemented or visually validated in this milestone.

## Runtime outcome and limits

- The engine reached `gfx_run` and produced game-origin Fast3D batches; this is stronger than the earlier smoke-only Eden attempt.
- Eden emitted Maxwell `Invalid insn` diagnostics during OpenGL/Mesa shader processing. The run did not establish a deko3d draw, a visible GoldenEye frame, or the root cause of the black presentation.
- The screenshot captured the Eden frontend rather than a verified game framebuffer and is intentionally not included as visual proof.
- The first traced NRO predated the live adapter hook. A later ARM64 build linked `ge_gfx_subset_submit_engine_batch()` into the full engine, but a fresh Eden launch of that adapter-enabled artifact produced no guest `engine.log`; live adapter conversion is therefore still unverified.
- The bridge now has a bounded CPU conversion for the exact observed `d000030d12181218:00000012` 19-float layout; host ASan/UBSan tests cover its fields, bounds, and fail-closed clamp-S variant. The full-engine build also links a bounded hook that routes eligible `gfx_flush()` batches through the adapter sink. This proves the code path builds, not that a live Eden batch passed it—the adapter-enabled Eden attempt had no guest log.
- The adapter-enabled build is recorded in `adapter-build-manifest.json`; its ELF contains `geEngineBoot`, `ge_fast3d_unpack_fogtex_rgb3`, and `ge_gfx_subset_submit_engine_batch`. The manifest explicitly records `deko3d_backend_enabled=false`. The current sink only validates/converts VBO data; no full-game batch has yet been submitted to deko3d, and no original-geometry frame is claimed.
