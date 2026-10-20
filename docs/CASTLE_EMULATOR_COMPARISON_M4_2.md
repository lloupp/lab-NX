# M4.2 — Eden/Ryubing memory diagnostics and a PRIVATE Castle PPC-on-Eden runner

**Evidence captured:** 2026-10-19/20, Ubuntu 24.04 GitHub Actions, devkitPro
\`devkita64:20260219\`, real ARM64 libnx NRO, Eden 0.2.1, Ryubing 1.3.3.

The goal is to distinguish emulator startup from real Switch guest execution.
**No Nintendo keys, firmware, game files, decrypted code, or proprietary assets
were uploaded to GitHub.** All public CI stage-1 tests have **no game image**
and must report PowerPC \`NOT EXECUTED\`.

## Eden guest ARM64 execution — PROVEN

GitHub Actions workflow \`eden-opengl-stage1.yml\` run 39359181891:

| Backend | Result | Peak VmRSS | Peak PSS | Guest proof |
|---|---|---:|---:|---|
| OpenGL with Mesa software renderer | NRO console displayed for 45 s | 4,459.94 MiB | 4,444.16 MiB | YES: screen shows stage-1 console text |
| Null graphics | Process alive through 45 s | 3,930.79 MiB | 3,916.76 MiB | NOT independently visible; black by design |
| Vulkan | \`VK_ERROR_INITIALIZATION_FAILED\` | minimal | minimal | NO |

OpenGL reported \`GL_VERSION 4.6 Compatibility Profile / Mesa 26.1.1\`,
renderer \`softpipe\`. The console screenshot says
\`STAGE-1: PPC SNIPPET / NOT PLAYABLE\` and
\`Private PowerPC PE: NOT EXECUTED\`. Its authenticity is independently
grounded in a captured emulator screen, not a synthetic substitute.

**Why the 4 GiB sandbox OOM-ed:** the Switch emulator consumes roughly
4.4 GiB **real resident memory** after entering the guest, even with a tiny
homebrew NRO and without Castle Crashers game data. The emulated
\`Memory_4Gb\` address space and other 512+ GiB VIRT reservations are *not*
the same as resident memory. Both graphics-null and software OpenGL cross
3.9 GiB RSS/PSS; the 4 GiB local container cannot sustain the former
reliably. A host with 8 GiB or preferably 16 GiB of system RAM should
allow the private check.

## Ryubing independent control — guest not verified

The same stage-1 NRO was also loaded using Ryubing 1.3.3 headless on a
16 GiB GitHub runner. It was correctly recognized as homebrew, but failed
with \`The specified file is not supported by Ryujinx\` and HLE service
exceptions. An independently built **official Switchbrew hbmenu v3.6.1**
NRO, downloaded from a checksum-verified release, fails the exact same way
in the keyless/firmware-less runner. Verified within the Flatpak sandbox
that the original stage-1 file is readable, is 196,608 bytes long and has
the expected \`NRO0\` header. No cause unique to our NRO was demonstrated.

One headless session reached ~3,034 MiB RSS / ~2,987 MiB PSS.
The hbmenu control reached ~4.3 GiB PSS. Neither is valid gameplay memory
measurement: the guest did not start.

## Exact private reproduction of PowerPC proof on Eden

**This is a restricted PowerPC snippet test, NOT a game port.** It uses
the user's own \`default.xex\` and the original privately recovered
\`decoded-powerpc.bin\`, checked to have exactly 2,949,120 bytes and
SHA-256:

\`964aa6b9d993beb8ad9a986d0555e47c36b4b5716b0b8377c6631ae8b39c03ab\`

The required stage-1 NRO can be compiled with devkitPro/libnx from
\`switch/castle_bootstrap\`, or obtained as the noncommercial CI artifact.
Extract Eden 0.2.1 AppImage with \`--appimage-extract\`. Then, on an X11
Linux desktop with sufficient RAM, from the \`lab-NX\` repo:

\`\`\`bash
mkdir -p "$HOME/labnx-private/eden-profile/data/eden/sdmc"

LABNX_SECONDS=75 LABNX_RSS_LIMIT_MIB=6500 \
bash scripts/eden_stage1_private.sh \
  "$HOME/labnx-private/default.xex" \
  "$HOME/labnx-private/decoded-powerpc.bin" \
  "$HOME/labnx-private/eden-profile/data/eden/sdmc" \
  "$HOME/labnx-private/castle_nx_bootstrap.nro" \
  "$HOME/apps/eden/squashfs-root/AppRun" \
  "$HOME/labnx-private/evidence-001"
\`\`\`

For **headless/Xvfb with Mesa software GL**, prefix with
\`LABNX_SOFTWARE_GL=1\` and run the script inside \`xvfb-run -a\`. Do not
force software GL on a normal machine with a compatible GPU unless needed.

The runner:

1. Confirms private original Castle PE size and SHA-256 and XEX Title ID
   before it copies anything into an isolated SDMC profile.
2. Rejects overwriting user files or evidence; refuses private reports
   inside a Git worktree.
3. Uses verified \`eden-cli --config ... --game ...\` and the same profile
   that contains \`data/eden/sdmc/switch/labnx/castle/\`.
4. Selects software-compatible OpenGL, not broken Vulkan; does **not** use
   the invalid old \`--null-render\` command-line option.
5. Samples RSS and PSS, stops at its memory cap, saves timestamps,
   diagnostics and actual Xvfb screenshots (5, 12, 20, 40, 60 seconds).
6. Does not claim execution of the original game just because Eden opens.

**Next evidence gate:** a screenshot of
\`Private PowerPC PE: LEAF EXECUTED\` and
\`PPC snippet at 8208EE10: r3=121 (seed=17)\`, optionally accompanied
by \`LABNX_GUEST_PPC_LEAF_EXECUTED\` emitted from the guest through
\`svcOutputDebugString\`. Without this, original Castle guest instructions
have **not** been confirmed in Eden. The 15 earlier original PPC host
checks are a separate validation.

Even when the above PPC leaf passes, Xbox system runtime, deko3d GPU,
actual Castle Crashers frames and gameplay will remain unfinished.
