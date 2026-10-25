#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "$ROOT/scripts/docker-group.sh"
UPSTREAM="${GE_UPSTREAM:-$ROOT/../../goldeneye-pc-port}"
UPSTREAM="$(cd "$UPSTREAM" && pwd -P)"
IMAGE="lab-nx/devkitpro-lsp:20260219"

if ! docker_with_group image inspect "$IMAGE" >/dev/null 2>&1; then
    docker_with_group build -f "$ROOT/docker/devkitpro-lsp.Dockerfile" -t "$IMAGE" "$ROOT" >&2
fi
if [[ ! -s "$ROOT/nxlab/switch_deko_smoke/compile_commands.json" ]]; then
    "$ROOT/scripts/configure_devkitpro_lsp.sh" >&2
fi

docker_with_group run --rm -i \
    -v "$ROOT:$ROOT" \
    -v "$UPSTREAM:/upstream:ro" \
    -w "$ROOT" \
    -e DEVKITPRO=/opt/devkitpro \
    -e HOME=/tmp \
    "$IMAGE" \
    --compile-commands-dir="$ROOT/nxlab/switch_deko_smoke" \
    --query-driver=/opt/devkitpro/devkitA64/bin/aarch64-none-elf-gcc,/opt/devkitpro/devkitA64/bin/aarch64-none-elf-g++ \
    "$@"
