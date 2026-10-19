# Castle Crashers — M3 playable-game goal

## Target: actual game, not a synthetic demo

Only mark the goal complete when the commercial game code really runs and there
is independent evidence of working menu, controller input, and Switch hardware.
Showing a custom scene with sprites from the game is **not** a playable port.

## Latest real observations

- Original user-owned XBLA package is STFS LIVE, content type 000D0000, Title ID 584108B7.
- Extracted default.xex: 765,952 bytes; entry point 0x820B7090.
- Image base: 0x82000000.
- Payload declares *normal encryption* and *normal/LZX compression* with a 32-KiB window.
- Imports: 146 slots in xam.xex; 255 slots in xboxkrnl.exe.
- A suitable PowerPC image has **not** been extracted, verified or run.
- No code from Castle Crashers has been proven to execute on ARM64.
- Real ReXGlue has not yet been installed in the analysis environment, and
  Clang 17 there does not meet the documented Clang 20+ requirement.

The toolchain doctor can detect these blockers without game bytes:

```sh
python3 -m nxlab.toolchain
```

## Bounded manager with Bonsai 4B

After privately unpacking the XBLA archive and locating the STFS file:

```sh
python3 -m nxlab.goal_manager \
  --input /private/584108B7.stfs \
  --workspace /private/labnx \
  --recipe castle-crashers --codegen --bonsai
```

The manager invokes the existing deterministic supervisor **once**, optionally
consults a trusted local Bonsai endpoint about sanitized diagnostics, writes
a private `goal-plan.json` and stops when a required stage is blocked or
unchanged. A model cannot execute arbitrary commands, bypass the evidence
gates, edit the game or merge code.

Use `--bonsai-url http://127.0.0.1:8080/v1/chat/completions` when the local
model listens on a non-default port. Model activation and SDK installation are
not automatic. Never expose game content, keys, binaries or private paths to a
hosted model.

## Gate sequence (11 independent verifications)

1. Real STFS validated.
2. Real XEX2 metadata validated.
3. Real PowerPC image available (requires compatible loader and access rights).
4. Real PPC-to-C++ codegen verified.
5. At least one actual PPC function executed and behavior validated.
6. XAM/Xboxkrnl services needed for the game verified.
7. First **genuine** game-generated frame captured.
8. Valid Switch ARM64 NRO compiled.
9. Real menu loaded in Eden.
10. Menu/game controls verified.
11. The same sequence verified on a physical Switch.

The status tool intentionally does not infer real gameplay from C++ file
existence, a built NRO or a synthetic render.

## Practical next work

1. On a capable Linux PC, install and pin a current ReXGlue SDK that supports
   `rexglue init --project-name --xex-path --project-root` and Clang 20+.
2. Run the private Castle Crashers codegen attempt and archive the logs. The
   tool may report unsupported encryption, import resolving or function graph
   errors. We must diagnose those from actual output.
3. Establish minimal native function execution before doing GPU translation.
4. Build Xbox service mocks that mimic real ABI and return codes from traces,
   then replace the mocks with correct implementations.
5. Capture a real game-originated frame, then work toward menu input.
6. Only after the game works on a suitable native reference environment,
   validate NRO and real Switch hardware.

SDK references: https://github.com/rexglue/rexglue-sdk/wiki/Getting-Started
and https://github.com/rexglue/rexglue-sdk/wiki/Codegen-Pipeline-Overview .

### License and privacy

Keep commercial game dumps, XEX, assets, firmware, keys and generated private
runtime files outside the public GitHub repository. This PR contains only
original orchestration code, metadata-only tests and project documentation.

**Current state: M3 planning and toolchain diagnosis implemented; game is NOT playable.**
