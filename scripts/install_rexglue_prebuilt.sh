#!/usr/bin/env bash
# Opt-in installer for pinned, official ReXGlue Linux amd64 binary.
set -euo pipefail
TAG="${REXGLUE_TAG:-nightly-20261002-bd833a2a}"
ROOT="${REXGLUE_INSTALL_ROOT:-$HOME/.local/share/labnx/rexglue}"
DEST="$ROOT/$TAG"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo "Linux x86_64 required" >&2; exit 3
fi
for dep in gh unzip mktemp find sha256sum; do
  command -v "$dep" >/dev/null || { echo "Missing: $dep" >&2; exit 3; }
done
if [[ -e "$DEST" ]]; then
  echo "Refusing to overwrite $DEST" >&2; exit 2
fi
mkdir -p "$ROOT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/download" "$TMP/sdk"
gh release download "$TAG" --repo rexglue/rexglue-sdk \
  --pattern '*linux-amd64*.zip' --dir "$TMP/download"
shopt -s nullglob
archives=("$TMP/download"/*.zip)
if [[ "${#archives[@]}" -ne 1 ]]; then
  echo "Expected one Linux SDK asset, got ${#archives[@]}" >&2; exit 2
fi
sha256sum "${archives[0]}"
unzip -q "${archives[0]}" -d "$TMP/sdk"
CLI="$(find "$TMP/sdk" -type f -name rexglue -print -quit)"
if [[ -z "$CLI" ]]; then
  echo "No ReXGlue executable in SDK" >&2; exit 2
fi
chmod +x "$CLI"
"$CLI" --version
"$CLI" init --help >/dev/null
"$CLI" codegen --help >/dev/null
mv "$TMP/sdk" "$DEST"
CLI="$DEST/${CLI#"$TMP/sdk/"}"
echo "Installed SDK at $DEST"
echo "ReXGlue CLI: $CLI"
