# lab-NX

Test-first Nintendo Switch porting laboratory. **Not** an automatic Xbox 360/PS3 game converter.

## One-command Xbox preflight (M1 + M2)

Python 3.10+; no dependencies for metadata inspection. First unpack your authorized XBLA `.7z` file locally, for example with `7z x "Castle Crashers.7z"`. Locate the large STFS file under `584108B7/000D0000/`.

```bash
python3 -m nxlab.auto \
  --input "/home/user/private/584108B7.stfs" \
  --workspace "/home/user/labnx-private" \
  --project castle_crashers
```

The workflow identifies the STFS, extracts the single contiguous `default.xex` into the **private workspace**, inspects its XEX2 headers/imports, and saves `runs/<id>/report.json`. The source file is never modified.

To **attempt** codegen with a locally installed ReXGlue:

```bash
python3 -m nxlab.auto \
  --input "/home/user/private/584108B7.stfs" \
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
- The code only supports contiguous STFS extraction and does not extract a `.7z` itself.
- No XEX payload decryption, LZX image extraction, ordinals resolution, runtime bridge, graphics translation, ARM64 NRO or actual Switch gameplay are yet proven.
- Synthetic mock ReXGlue tests only validate orchestration, not real PowerPC compilation.

See [M1](docs/CASTLE_CRASHERS_M1.md), [M2](docs/CASTLE_CRASHERS_M2.md), and [automation status](docs/PIPELINE_AUTOMATION.md).
