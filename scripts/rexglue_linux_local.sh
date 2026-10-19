#!/usr/bin/env bash
# Optional, operator-run ReXGlue SDK installer for Linux Mint / Ubuntu.
# Does not access game files or publish assets; dependencies are user-managed.
set -euo pipefail

SOURCE_DIR="${REXGLUE_SOURCE_DIR:-$HOME/rexglue-sdk}"
PREFIX="${REXGLUE_PREFIX:-$HOME/.local/rexglue}"
REF="${REXGLUE_REF:-}" # Set to a reviewed commit hash for reproducible builds.
JOBS="${REXGLUE_BUILD_JOBS:-2}"

for program in git cmake ninja clang++-20; do
  if ! command -v "$program" >/dev/null 2>&1; then
    echo "Missing $program (ReXGlue needs Clang 20+ plus GTK3 headers)" >&2
    exit 3
  fi
done

if [[ -e "$SOURCE_DIR" && ! -d "$SOURCE_DIR/.git" ]]; then
  echo "Source path exists but is not a Git checkout; refusing to overwrite" >&2
  exit 2
fi

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  git clone --recursive https://github.com/rexglue/rexglue-sdk.git "$SOURCE_DIR"
fi

if [[ -n "$REF" ]]; then
  git -C "$SOURCE_DIR" fetch --tags origin "$REF"
  git -C "$SOURCE_DIR" checkout --detach "$REF"
  git -C "$SOURCE_DIR" submodule update --init --recursive
fi

echo "SDK revision: $(git -C "$SOURCE_DIR" rev-parse HEAD)"
mkdir -p "$PREFIX"
(
  cd "$SOURCE_DIR"
  CC=clang-20 CXX=clang++-20 cmake --preset linux-amd64 \
    -DCMAKE_INSTALL_PREFIX="$PREFIX"
  cmake --build out/build/linux-amd64 --target install --parallel "$JOBS"
)
if [[ ! -x "$PREFIX/bin/rexglue" ]]; then
  echo "Installed CLI not found in $PREFIX/bin/rexglue" >&2
  exit 2
fi
"$PREFIX/bin/rexglue" init --help
echo "ReXGlue ready at $PREFIX/bin/rexglue"
echo "Next: run python3 -m nxlab.goal_manager --input <private.xex> --workspace <private-dir> --codegen --bonsai"
