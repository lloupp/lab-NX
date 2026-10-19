"""Bounded ReXGlue game-runtime watchdog; counts errors without storing raw logs.

The operator runs their own authorized private game locally. Reports contain
only error classes and guest addresses; no binary data, paths or screenshots.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time

GUEST_FAULT = re.compile(r"Unhandled guest access violation: (?:read|write) of guest (0x[0-9A-Fa-f]{8})")
INVALID_CALL = re.compile(r"Call to invalid or unregistered function at guest address (0x[0-9A-Fa-f]{8})")


def classify(line, totals, faults, invalid):
    match = GUEST_FAULT.search(line)
    if match:
        totals["guest_access_violation"] += 1
        faults[match.group(1).lower()] += 1
        return
    match = INVALID_CALL.search(line)
    if match:
        totals["unregistered_guest_function"] += 1
        invalid[match.group(1).lower()] += 1
        return
    if "SDL_InitSubSystem(SDL_INIT_AUDIO) failed" in line:
        totals["sdl_audio_init_error"] += 1
    elif "Graphics presentation setup failed" in line or "Unable to create graphics provider" in line:
        totals["gpu_initialization_error"] += 1
    elif "VulkanPresenter: Created" in line:
        totals["vulkan_swapchain_created"] += 1
    elif "[error]" in line.lower():
        totals["other_error"] += 1


def watch(command, duration=6, environ=None):
    if not 0.25 <= duration <= 90:
        raise ValueError("Duration must be between 0.25 and 90 seconds")
    if not command or ("/" in command[0] and not Path(command[0]).is_file()):
        raise ValueError("Invalid executable")
    env = dict(os.environ if environ is None else environ)
    proc = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True, bufsize=0)
    os.set_blocking(proc.stdout.fileno(), False)
    events = selectors.DefaultSelector()
    events.register(proc.stdout, selectors.EVENT_READ)
    totals, faults, invalid = Counter(), Counter(), Counter()
    pending = b""
    start = time.monotonic()
    timed_out = False

    def take(data):
        nonlocal pending
        pending += data
        lines = pending.split(b"\n")
        pending = lines.pop()
        if len(pending) > 65536:
            pending = pending[-4096:]
            totals["oversized_line"] += 1
        for line in lines:
            totals["total_lines"] += 1
            classify(line.decode("utf-8", "replace")[:4096], totals, faults, invalid)

    try:
        while time.monotonic() - start < duration:
            if proc.poll() is not None:
                break
            for key, mask in events.select(0.1):
                buf = os.read(proc.stdout.fileno(), 65536)
                if buf:
                    take(buf)
        timed_out = proc.poll() is None
    finally:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(2)
        for _ in range(64):
            try:
                buf = os.read(proc.stdout.fileno(), 65536)
            except BlockingIOError:
                break
            if not buf:
                break
            take(buf)
        events.close()
        proc.stdout.close()
    if pending:
        classify(pending.decode("utf-8", "replace")[:4096], totals, faults, invalid)
    return {
        "duration_seconds": round(time.monotonic()-start, 2),
        "termination": "time_limit" if timed_out else "process_exit",
        "exit_code": None if timed_out else proc.returncode,
        "counts": dict(totals),
        "guest_faults": dict(faults.most_common(16)),
        "unregistered_targets": dict(invalid.most_common(16)),
        "raw_logs_stored": False,
        "game_frame_verified": False,
        "game_playable": False
    }


def make_alsa_null_config(folder):
    """Provide a local ALSA playback sink without touching /etc/asound.conf."""
    target = Path(folder) / "alsa-null.conf"
    with target.open("x", encoding="utf-8") as stream:
        stream.write("pcm.!default {\n    type null\n}\n"
                     "ctl.!default {\n    type hw\n    card 0\n}\n")
    return target


def run_with_optional_audio(command, seconds, env, alsa_null=False):
    """ALSA null device is isolated per run and destroyed afterwards."""
    if not alsa_null:
        return watch(command, seconds, env)
    with tempfile.TemporaryDirectory(prefix="labnx-alsa-null-") as temp:
        environment = dict(env)
        environment["SDL_AUDIODRIVER"] = "alsa"
        environment["ALSA_CONFIG_PATH"] = str(make_alsa_null_config(temp))
        return watch(command, seconds, environment)


def main(argv=None):
    p = argparse.ArgumentParser(description="lab-NX bounded runtime diagnostics")
    p.add_argument("--exe", required=True, type=Path)
    p.add_argument("--game-data-root", required=True, type=Path)
    p.add_argument("--sdk-lib-dir", required=True, type=Path)
    p.add_argument("--icd", type=Path)
    p.add_argument("--duration", type=float, default=6)
    p.add_argument("--audio-driver", help="Opt-in SDL driver, no dummy by default")
    p.add_argument("--alsa-null", action="store_true", help="Use a private ALSA null playback sink")
    p.add_argument("--xvfb", action="store_true")
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    try:
        if args.alsa_null and args.audio_driver:
            raise ValueError('Choose --alsa-null OR --audio-driver')
        exe = args.exe.expanduser().resolve(strict=True)
        root = args.game_data_root.expanduser().resolve(strict=True)
        sdk = args.sdk_lib_dir.expanduser().resolve(strict=True)
        if not exe.is_file() or not root.is_dir() or not sdk.is_dir():
            raise ValueError("Invalid private executable or data directories")
        environment = os.environ.copy()
        environment["LD_LIBRARY_PATH"] = str(sdk) + (
            (":" + environment["LD_LIBRARY_PATH"]) if environment.get("LD_LIBRARY_PATH") else "")
        environment["MESA_SHADER_CACHE_DISABLE"] = "true"
        environment.pop("SDL_AUDIODRIVER", None)
        if args.audio_driver:
            environment["SDL_AUDIODRIVER"] = args.audio_driver
        if args.icd:
            driver = str(args.icd.expanduser().resolve(strict=True))
            environment["VK_DRIVER_FILES"] = driver
            environment["VK_ICD_FILENAMES"] = driver
        command = [str(exe), "--game_data_root", str(root),
                   "--gpu_plugin", "xenos",
                   "--log_level", "error", "--log_file", "/dev/stdout"]
        if args.xvfb:
            command = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", *command]
        result = run_with_optional_audio(command, args.duration, environment, args.alsa_null)
        if args.output:
            out = args.output.expanduser().resolve()
            if any((folder / ".git").exists() for folder in (out.parent, *out.parents)):
                raise ValueError("Report must remain outside Git checkout")
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 3 if result["guest_faults"] or result["unregistered_targets"] else 0
    except (OSError, ValueError) as exc:
        print("lab-NX runtime watchdog:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
