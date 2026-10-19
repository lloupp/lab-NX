#!/usr/bin/env bash
# Authorized Castle guest-snippet test in Eden Linux. Never uploads game files.
set -euo pipefail
if [[ $# -ne 6 ]]; then
  echo "usage: $0 XEX PRIVATE_DECODED_PE SDMC_ROOT STAGE1_NRO EDEN_BINARY PRIVATE_REPORT_DIR" >&2
  exit 2
fi
XEX="$1"; PE="$2"; SDMC="$3"; NRO="$4"; EDEN="$5"; REPORT="$6"
if [[ ! -f "$XEX" || ! -f "$PE" || ! -f "$NRO" || ! -x "$EDEN" || ! -d "$SDMC" ]]; then
  echo "Missing XEX, decoded PE, SDMC directory, NRO or Eden executable" >&2
  exit 2
fi
if [[ -e "$REPORT" ]]; then
  echo "Choose a NEW private report directory; refusing overwrite" >&2
  exit 2
fi
if [[ -z "$(printenv DISPLAY || true)" ]]; then
  echo "Eden requires a graphical DISPLAY (desktop X11 or Xvfb)" >&2
  exit 2
fi
mkdir -m 700 -p "$REPORT"
echo "Preparing private SD; decoded PE must match original Castle SHA-256."
python3 -m nxlab.switch_sd --xex "$XEX" --decoded-pe "$PE" --sdmc-root "$SDMC" > "$REPORT/sd-import.json"
set +e
timeout -s TERM -k 3s 90s "$EDEN" --null-render --game "$NRO" > "$REPORT/eden-stdout.log" 2>&1
rc=$?
set -e
printf 'eden_process_exit=%s\n' "$rc" > "$REPORT/status.txt"
echo "The process status alone is not proof of guest PowerPC execution." >> "$REPORT/status.txt"
echo "Inspect the Eden window for 'Private PowerPC PE: LEAF EXECUTED' and r3=121." >> "$REPORT/status.txt"
echo "Also inspect Eden's private GUI log for LABNX_GUEST_PPC_LEAF_EXECUTED." >> "$REPORT/status.txt"
echo "No game frame or playable menu is implied by an executed guest snippet." >> "$REPORT/status.txt"
cat "$REPORT/status.txt"
exit 0
