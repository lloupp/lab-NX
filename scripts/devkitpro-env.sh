#!/usr/bin/env bash
# Source this file to use the pinned local devkitPro installation.
if [[ -z "${DEVKITPRO:-}" ]]; then
    DEVKITPRO="$HOME/.local/share/devkitpro/20260219"
fi
if [[ ! -x "$DEVKITPRO/devkitA64/bin/aarch64-none-elf-gcc" ]]; then
    printf 'devkitA64 compiler not found under DEVKITPRO=%s\n' "$DEVKITPRO" >&2
    return 1 2>/dev/null || exit 1
fi
export DEVKITPRO
export PATH="$DEVKITPRO/devkitA64/bin:$DEVKITPRO/tools/bin:$PATH"
