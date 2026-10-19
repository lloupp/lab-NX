# lab-NX

Test-first Nintendo Switch porting laboratory. **Not** an automatic Xbox 360/PS3 game converter.

## One-command Xbox preflight (M1 + M2)

Python 3.10+; a system `libarchive` is required for compressed 7z/ZIP inputs (no `7z` CLI required). The original, authorized XBLA `.7z` can now be passed **directly** without manual unpacking. An extracted STFS or XEX2 also works.

```bash
python3 -m nxlab.auto \
  --input "/home/user/private/Castle Crashers (World) (XBLA) (1).7z" \
  --workspace "/home/user/labnx-private" \
  --project castle_crashers
```

The workflow detects the archive if present, extracts exactly one STFS member privately, then extracts the single contiguous `default.xex` into the **private workspace**, inspects its XEX2 headers/imports, and saves `runs/<id>/report.json`. The source file is never modified.

To **attempt** codegen with a locally installed ReXGlue:

```bash
python3 -m nxlab.auto \
  --input "/home/user/private/Castle Crashers (World) (XBLA) (1).7z" \
  --workspace "/home/user/labnx-private" \
  --project castle_crashers \
  --codegen \
  --rexglue /opt/rexglue/bin/rexglue
```

The ReXGlue bridge detects the newer `--project-name/--xex-path/--project-root` CLI, creates a private project, and calls `codegen`. If ReXGlue is missing or its CLI differs, it **blocks** the step and records a diagnostic rather than pretending success.

Exit codes: `0` = requested steps passed; `2` = failed step; `3` = blocked by a missing/incompatible SDK. Logs and generated C++ stay private. A codegen pass **does not** mean native functions executed, Xbox imports were solved, or that a Switch NRO exists.

## Individual M1/M2 commands

```bash
python3 -m nxlab inspect-stfs /private/game.stfs --report /private/inventory.json
python3 -m nxlab extract-xex /private/game.stfs /private/default.xex
python3 -m nxlab.m2 /private/default.xex --report /private/m2.json
python3 -m unittest discover -s tests -v
```

## Constraints

- No commercial game file, XEX, asset, key, license or dump belongs in the GitHub repository.
- Workspace MUST be outside any Git working tree.
- The pipeline imports 7z/ZIP via libarchive but only supports unique STFS members and contiguous STFS XEX extraction. Other archive formats and ISO/XDVDFS are not handled.
- No XEX payload decryption, LZX image extraction, ordinals resolution, runtime bridge, graphics translation, ARM64 NRO or actual Switch gameplay are yet proven.
- Synthetic mock ReXGlue tests only validate orchestration, not real PowerPC compilation.

To install a pinned, official ReXGlue Linux x86_64 binary on a machine with network access and `gh` + `unzip`, run `bash scripts/install_rexglue_prebuilt.sh`. This performs an actual CLI self-test and stores the SDK under the user home directory without touching game files. Host compilation of generated code still requires a compatible toolchain (Clang 20+ per SDK documentation). The GitHub Actions SDK smoke workflow tests the pinned upstream Linux binary separately from game data.

See [7z evidence](docs/CASTLE_7Z_E2E.md), [M1](docs/CASTLE_CRASHERS_M1.md), [M2](docs/CASTLE_CRASHERS_M2.md), and [automation status](docs/PIPELINE_AUTOMATION.md).
