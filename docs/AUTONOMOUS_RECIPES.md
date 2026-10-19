# A "recipe that works with other flavors": lab-NX reusable profiles

## What is now automated

The M1/M2 pipeline inspects authorized STFS/XEX files, extracts one contiguous
`default.xex` into a private workspace, inspects metadata, and optionally
invokes an installed ReXGlue CLI for code generation.

The new supervisor adds:

- **Shared recipe inheritance:** Castle Crashers, Forza Horizon and Fallout NV
  inherit the **Xbox 360** profile (XEX, PPC, XAM, Xboxkrnl, deko3d contracts).
- **Platform isolation:** Demon's Souls has its own **PS3** profile, explicitly
  unsupported by the current Xbox backend, so it cannot accidentally use ReXGlue.
- **Evidence gates:** generating C++ marks *PPC codegen* only. No downstream
  milestone (executed PPC, real graphics, NRO, Eden, console) is marked complete
  without its own verifier.
- **Anti-loop checkpoint:** identical source file metadata, recipe and SDK
  fingerprint are executed only once unless an operator requests `--force`.
- **Private history:** per-game run summary and next action under a directory
  outside Git. The JSON contains no XEX bytes or assets.
- **Deterministic next action:** failure stops the loop and requests diagnosis;
  it does not make an unbounded sequence of guesses or call an LLM on its own.

## Linux Mint example

First privately unpack your XBLA archive and locate the STFS file.

```sh
python3 -m nxlab.supervisor \
  --input /home/user/games-private/584108B7.stfs \
  --workspace /home/user/labnx-private \
  --recipe castle-crashers \
  --codegen
```

If the SDK is missing, codegen reports a real blocker and returns nonzero.
Run the command again after installing ReXGlue; the SDK fingerprint change permits
a new attempt. Use `--force` only when rerunning an identical test intentionally.

For the other Xbox games, use the same supervisor with a different `--recipe`
profile, **and supply a supported STFS/XEX file**. ISO extraction and special
game runtime adaptations are not yet handled by this pipeline.

```sh
python3 -m nxlab.supervisor --input /private/forza.xex \
  --workspace /private/labnx --recipe forza-horizon
```

## Proposed autonomy milestones

| Stage | Current state |
|---|---|
| Identify shared platform recipe | Implemented |
| Execute analysis / optional SDK step | Implemented |
| Prevent no-progress loops | Implemented |
| Record private evidence and next task | Implemented |
| Invoke a coding LLM and apply patches autonomously | Not implemented |
| Verify emitted C++ as real PPC execution | Not implemented |
| Automatically solve Xbox runtime/graphics | Not implemented |
| Compile, run and compare original game on Switch | Not implemented |

Next: add a **sandboxed, opt-in coding-agent adapter** (e.g. Pi/OpenCode) that
only sees sanitized diagnostic logs, proposes an isolated branch, runs CI,
and requests review for changes. Never send original game dumps or keys to
hosted LLMs and never merge unverified changes automatically.

This is not proof that one recipe works unmodified for every game: profiles
share infrastructure, while game-specific compatibility still requires work.
