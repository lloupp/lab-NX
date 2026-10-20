#!/usr/bin/env bash
# Run the user's ORIGINAL authorized Castle PPC snippet in Eden SDL2 CLI.
# This is a guest-instruction proof, NOT game/menu/rendering or ReXGlue ARM64.
set -euo pipefail
if [[ $# -ne 6 ]]; then
  echo "usage: $0 XEX ORIGINAL_DECODED_PE EDEN_SDMC_ROOT NRO EDEN_APPRUN_OR_CLI NEW_REPORT_DIR" >&2
  exit 2
fi
XEX="$(realpath "$1")"
PE="$(realpath "$2")"
SDMC="$(realpath "$3")"
NRO="$(realpath "$4")"
EDEN="$(realpath "$5")"
REPORT="$(realpath -m "$6")"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -f "$XEX" || ! -f "$PE" || ! -f "$NRO" || ! -x "$EDEN" || ! -d "$SDMC" ]]; then
  echo "XEX, original PE, NRO, executable Eden and SDMC must exist" >&2
  exit 2
fi
if [[ -e "$REPORT" ]]; then
  echo "Choose a NEW report folder; never overwrite evidence" >&2
  exit 2
fi
case "$SDMC" in
  */data/eden/sdmc) PROFILE="$(dirname "$(dirname "$(dirname "$SDMC")")")";;
  *) echo "SDMC must be <profile>/data/eden/sdmc in SAME Eden profile" >&2; exit 2;;
esac
case "$EDEN" in
  */AppRun) CMD=("$EDEN" eden-cli);;
  */eden-cli) CMD=("$EDEN");;
  *) echo "Pass the extracted Eden 0.2.1 AppRun or eden-cli binary" >&2; exit 2;;
esac
CHECK="$REPORT"
while [[ "$CHECK" != "/" ]]; do
  if [[ -e "$CHECK/.git" ]]; then
    echo "Private report directory cannot be inside a Git worktree" >&2
    exit 2
  fi
  CHECK="$(dirname "$CHECK")"
done
if [[ -z "$(printenv DISPLAY || true)" ]]; then
  echo "Eden requires an X11 DISPLAY; use your desktop or xvfb-run" >&2
  exit 2
fi
TIME="${LABNX_SECONDS:-75}"
CAP="${LABNX_RSS_LIMIT_MIB:-6500}"
if [[ ! "$TIME" =~ ^[0-9]+$ || ! "$CAP" =~ ^[0-9]+$ ||
      "$TIME" -lt 5 || "$TIME" -gt 120 ||
      "$CAP" -lt 256 || "$CAP" -gt 10000 ]]; then
  echo "Invalid LABNX_SECONDS (5..120) or LABNX_RSS_LIMIT_MIB (256..10000)" >&2
  exit 2
fi
mkdir -m 700 -p "$REPORT" "$PROFILE/config" "$PROFILE/cache" "$PROFILE/runtime"
chmod 700 "$PROFILE/runtime"
export PYTHONPATH="$REPO_ROOT"
python3 -m nxlab.switch_sd --xex "$XEX" --decoded-pe "$PE" \
  --sdmc-root "$SDMC" > "$REPORT/sd-import.json"
python3 "$REPO_ROOT/switch/castle_bootstrap/tests/inspect_nro.py" "$NRO" \
  > "$REPORT/nro-header.txt"
cat > "$REPORT/sdl2-config.ini" <<'EDEN_INI'
[Renderer]
backend\default=false
backend=0
[Core]
memory_layout_mode\default=false
memory_layout_mode=0
EDEN_INI
echo "Original authorized PPC PE. User-only storage; OpenGL, no gameplay claim." > "$REPORT/scope.txt"
if [[ "${LABNX_SOFTWARE_GL:-0}" == 1 ]]; then
  export LIBGL_ALWAYS_SOFTWARE=1
  export LIBGL_DRI3_DISABLE=1
  export MESA_GL_VERSION_OVERRIDE=4.6
  export MESA_GLSL_VERSION_OVERRIDE=460
fi
export HOME="$PROFILE"
export XDG_CONFIG_HOME="$PROFILE/config"
export XDG_DATA_HOME="$PROFILE/data"
export XDG_CACHE_HOME="$PROFILE/cache"
export XDG_RUNTIME_DIR="$PROFILE/runtime"
export SDL_AUDIODRIVER=dummy
echo "Running Eden OpenGL for up to ${TIME}s (RAM safety ceiling ${CAP} MiB RSS)"
python3 "$REPO_ROOT/scripts/compare_emulator_memory.py" \
  --output "$REPORT/run" --seconds "$TIME" --limit-mb "$CAP" -- \
  "${CMD[@]}" --config "$REPORT/sdl2-config.ini" --game "$NRO" \
  > "$REPORT/memory-summary.json"
MAIN=unverified
PPC=unverified
if grep -aq 'LABNX_CASTLE_STAGE0_MAIN_ENTERED' "$REPORT/run/emulator.log"; then
  MAIN=log_marker_found
fi
if grep -aq 'LABNX_GUEST_PPC_LEAF_EXECUTED' "$REPORT/run/emulator.log"; then
  PPC=log_marker_found
fi
cat > "$REPORT/verdict.txt" <<EOF
Eden OpenGL private test completed (diagnostic only).
Guest ARM64 main via SVC log: $MAIN
Original PPC leaf via SVC log: $PPC
Review run/screen-*.png for 'LEAF EXECUTED' with r3=4.
If SVC log is absent, a screenshot of that exact message is required.
Full Xbox runtime, original game frame and gameplay: NOT VERIFIED.
Copyrighted source bytes remain on this local machine, outside Git.
EOF
cat "$REPORT/verdict.txt"
echo "Evidence saved in: $REPORT"
