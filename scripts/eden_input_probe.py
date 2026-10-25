#!/usr/bin/env python3
"""Exercise host input in Eden and capture the guest's reaction.

The probe builds a throw-away Eden profile, boots a Switch NRO through the
`eden-cli` frontend, focuses the emulator window by PID (never a terminal
that merely mentions "Eden" in its title), and injects keys through XTEST.

Why XTEST: the SDL2 frontend only sees real server key events. `xdotool
keydown --window <id>` uses XSendEvent and is ignored by SDL2, which is why
earlier attempts showed `input_sent=true` with no effect in the guest.

Default sequence ("watch-move"), using Eden's default keyboard profile:
  m        -> + (Start)   opens/closes the Q Watch pause screen
  Up       -> left stick up (forward); emulate_analog_keyboard must be on
The watch screenshot is the unambiguous proof that a controller button
reached the guest; the Up screenshots show analog movement.

Keys are sent only to the window owned by the Eden process. If no such
window exists the probe exits without sending anything.

Raw guest frames can be captured with --frame-dump (engine [Debug]
FrameDump), for example --frame-dump 500-520:10.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import zipfile
import zlib

SD_REL = Path("switch/lab-nx/goldeneye")
EXPECTED_SHA1 = "abe01e4aeb033b6c0836819f549c791b26cfde83"
EXPECTED_CRC32 = 0xB6330846


def read_rom(path: Path) -> bytes:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".z64")]
            if len(names) != 1:
                raise SystemExit("ROM ZIP must contain exactly one .z64")
            return archive.read(names[0])
    return path.read_bytes()


def validate_rom(data: bytes) -> dict:
    sha1 = hashlib.sha1(data).hexdigest()
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    if len(data) != 12 * 1024 * 1024 or data[:4] != bytes.fromhex("80371240"):
        raise SystemExit("not the 12 MiB big-endian USA ROM")
    if sha1 != EXPECTED_SHA1 or crc32 != EXPECTED_CRC32:
        raise SystemExit(f"ROM mismatch sha1={sha1} crc32={crc32:08x}")
    return {"sha1": sha1, "crc32": f"{crc32:08X}", "size": len(data)}


def patch_config(template: Path, home: Path) -> str:
    """Copy an Eden CLI config, pointing it at `home` and enabling keyboard."""
    text = template.read_text().replace(str(template.parents[2]), str(home))
    out = []
    for line in text.splitlines():
        if line.startswith("keyboard_enabled") and "\\default" not in line:
            line = "keyboard_enabled=true"
        elif line.startswith("keyboard_enabled\\default"):
            line = "keyboard_enabled\\default=false"
        elif line.startswith("emulate_analog_keyboard") and "\\default" not in line:
            line = "emulate_analog_keyboard=true"
        elif line.startswith("emulate_analog_keyboard\\default"):
            line = "emulate_analog_keyboard\\default=false"
        out.append(line)
    return "\n".join(out) + "\n"


def xdotool(env: dict, *args: str, timeout: float = 10.0) -> str:
    return subprocess.check_output(["xdotool", *args], env=env, text=True,
                                   timeout=timeout, stderr=subprocess.DEVNULL).strip()


def describe_window(env: dict, wid: str) -> dict:
    info: dict = {"id": wid}
    try:
        info["name"] = xdotool(env, "getwindowname", wid, timeout=5)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        info["name"] = "?"
    try:
        geo = xdotool(env, "getwindowgeometry", "--shell", wid, timeout=5)
        for line in geo.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                info[key.lower()] = value
        info["area"] = int(info.get("width", 0)) * int(info.get("height", 0))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        info["area"] = 0
    try:
        info["class"] = subprocess.check_output(
            ["xprop", "-id", wid, "WM_CLASS"], env=env, text=True, timeout=2,
            stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        info["class"] = ""
    return info


def find_eden_window(env: dict, pid: int) -> tuple[str | None, list[dict]]:
    ids: list[str] = []
    try:
        ids += xdotool(env, "search", "--pid", str(pid), timeout=10).split()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    if not ids:
        for cls in ("eden", "eden-cli", "Eden"):
            try:
                ids += xdotool(env, "search", "--class", cls, timeout=10).split()
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
    details = [describe_window(env, wid) for wid in dict.fromkeys(ids)]
    details.sort(key=lambda item: item.get("area", 0), reverse=True)
    return (details[0]["id"] if details else None), details


def screenshot(path: Path, env: dict, window: str | None) -> bool:
    return subprocess.run(["import", "-window", window or "root", str(path)], env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=30).returncode == 0


def send(env: dict, style: str, window: str, keysym: str, action: str) -> None:
    args = ["keydown" if action == "down" else "keyup"]
    if style == "synthetic":
        args += ["--window", window]
    args.append(keysym)
    subprocess.run(["xdotool", *args], env=env, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=5, check=False)


def press(env: dict, style: str, window: str, keysym: str, hold: float = 0.2) -> None:
    send(env, style, window, keysym, "down")
    time.sleep(hold)
    send(env, style, window, keysym, "up")


def engine_ready(engine_log: Path) -> bool:
    if not engine_log.exists():
        return False
    try:
        return "rendered in" in engine_log.read_text(errors="replace")
    except OSError:
        return False


def wait_for_frame(engine_log: Path, frame: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    needle = f"frame {frame} rendered"
    while time.monotonic() < deadline:
        try:
            if needle in engine_log.read_text(errors="replace"):
                return True
        except OSError:
            pass
        time.sleep(1)
    return False


def wav_stats(path: Path) -> dict | None:
    """RMS/peak of a 16-bit WAV, sampled every 4th value for speed."""
    import array
    import math
    import wave
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            channels = handle.getnchannels()
            rate = handle.getframerate()
            width = handle.getsampwidth()
            raw = handle.readframes(frames)
    except (OSError, wave.Error):
        return None
    if width != 2 or not raw:
        return {"frames": frames, "bytes": len(raw)}
    samples = array.array("h")
    samples.frombytes(raw)
    sampled = samples[::4]
    peak = max(abs(value) for value in sampled)
    rms = math.sqrt(sum(value * value for value in sampled) / len(sampled))
    return {"frames": frames, "channels": channels, "rate": rate,
            "seconds": round(frames / rate, 2) if rate else None,
            "peak": peak, "rms": round(rms, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eden", type=Path, required=True, help="Eden AppImage")
    ap.add_argument("--nro", type=Path, required=True, help="Switch NRO to boot")
    ap.add_argument("--rom", type=Path, required=True, help="GoldenEye USA .z64 or .zip")
    ap.add_argument("--data-dir", type=Path, required=True,
                    help="guest data/ directory with ge007.ini, pcmodels-*, pccg-*")
    ap.add_argument("--config-template", type=Path, default=Path.home() / ".config/eden/sdl2-config.ini",
                    help="sdl2-config.ini to copy into the isolated profile")
    ap.add_argument("--out", type=Path, default=Path("eden-input-evidence"))
    ap.add_argument("--display", default=os.environ.get("DISPLAY"),
                    help="X display (default: $DISPLAY; Xvfb when unset)")
    ap.add_argument("--style", choices=("xtest", "synthetic"), default="xtest",
                    help="xtest = real server input (default); synthetic = XSendEvent")
    ap.add_argument("--sequence", choices=("watch-move", "none"), default="watch-move")
    ap.add_argument("--msaa", type=int, default=2, help="[Video] MSAA written to ge007.ini")
    ap.add_argument("--aspect-mode", type=int, help="[Video] AspectMode written to ge007.ini")
    ap.add_argument("--window", help="[Window] WidthxHeight written to ge007.ini")
    ap.add_argument("--frame-dump", help="[Debug] FrameDump range, e.g. 500-520:10")
    ap.add_argument("--wait-frame", type=int, default=600,
                    help="wait for this engine frame before injecting input (0 = act immediately)")
    ap.add_argument("--boot-timeout", type=float, default=100.0)
    ap.add_argument("--host-audio", action="store_true",
                    help="let Eden use the host audio sink instead of the SDL dummy driver")
    ap.add_argument("--audio-sink",
                    help="PulseAudio/PipeWire sink name exported as PULSE_SINK")
    ap.add_argument("--audio-record", type=Path,
                    help="record the sink monitor to this WAV for the whole run")
    args = ap.parse_args()

    for path in (args.eden, args.nro, args.rom, args.config_template):
        if not path.expanduser().is_file():
            ap.error(f"file not found: {path}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = (args.out.expanduser().resolve() / f"run-{stamp}-{args.style}")
    out.mkdir(parents=True)
    home = out / "home"
    guest = home / ".local/share/eden/sdmc" / SD_REL
    (guest / "data").mkdir(parents=True)
    (home / ".config/eden").mkdir(parents=True)
    (home / ".cache/eden").mkdir(parents=True)

    rom = validate_rom(read_rom(args.rom.expanduser()))
    (guest / "baserom.u.z64").write_bytes(read_rom(args.rom.expanduser()))
    for item in args.data_dir.expanduser().iterdir():
        dst = guest / "data" / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)

    ini = f"[Video]\nMSAA={args.msaa}\n"
    if args.aspect_mode is not None:
        ini += f"AspectMode={args.aspect_mode}\n"
    if args.window:
        width, height = args.window.lower().split("x")
        ini += f"[Window]\nWidth={width}\nHeight={height}\n"
    if args.frame_dump:
        ini += f"[Debug]\nFrameDump={args.frame_dump}\n"
    (guest / "data/ge007.ini").write_text(ini)
    (home / ".config/eden/sdl2-config.ini").write_text(
        patch_config(args.config_template.expanduser(), home))

    display = args.display
    xvfb = None
    if display is None:
        display = next((f":{n}" for n in range(210, 260)
                        if not Path(f"/tmp/.X11-unix/X{n}").exists()), None)
        if display is None:
            raise SystemExit("no spare display for Xvfb")
        xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", "1400x1000x24",
                                 "+extension", "XTEST", "+render", "-noreset"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if Path(f"/tmp/.X11-unix/X{display[1:]}").exists():
                break
            time.sleep(0.2)

    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "DISPLAY": display,
        "QT_QPA_PLATFORM": "xcb",
    })
    if not args.host_audio and not args.audio_record:
        env["SDL_AUDIODRIVER"] = "dummy"
    if args.audio_sink:
        env["PULSE_SINK"] = args.audio_sink
    eden_log_path = home / ".local/share/eden/log/eden_log.txt"
    engine_log = guest / "engine.log"
    result: dict = {"style": args.style, "sequence": args.sequence, "rom": rom,
                    "msaa": args.msaa, "frame_dump": args.frame_dump, "events": []}
    recorder = None
    audio_path = None
    if args.audio_record:
        audio_path = args.audio_record.expanduser().resolve()
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        device = f"{args.audio_sink}.monitor" if args.audio_sink else "@DEFAULT_MONITOR@"
        recorder = subprocess.Popen(
            ["parecord", "--device", device, "--channels=2", "--rate=48000",
             "--format=s16le", "--file-format=wav", str(audio_path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log_handle = (out / "eden-stdout.log").open("wb")
    proc = subprocess.Popen([str(args.eden.expanduser().resolve()), "eden-cli",
                             "-g", str(args.nro.expanduser().resolve())],
                            cwd=str(out), env=env, stdout=log_handle,
                            stderr=subprocess.STDOUT, start_new_session=True)
    start = time.monotonic()
    try:
        deadline = start + args.boot_timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                result["early_exit"] = proc.returncode
                break
            if engine_ready(engine_log):
                result["ready"] = True
                break
            time.sleep(1)
        if result.get("ready"):
            time.sleep(2)
            if args.wait_frame > 0:
                result["waited_for_frame"] = wait_for_frame(
                    engine_log, args.wait_frame, max(10.0, args.boot_timeout - 2))
            window, details = find_eden_window(env, proc.pid)
            for _ in range(4):
                if window is not None:
                    break
                time.sleep(3)
                window, details = find_eden_window(env, proc.pid)
            result["windows"] = details
            result["window"] = window
            if window is None:
                result["error"] = "no Eden window found; input not sent"
            else:
                try:
                    xdotool(env, "windowfocus", "--sync", window)
                    xdotool(env, "windowraise", window)
                    result["focus"] = xdotool(env, "getwindowfocus")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    result["focus"] = None
                time.sleep(1)
                shots = []
                screenshot(out / "00_before.png", env, window)
                shots.append("00_before.png")
                if args.sequence == "watch-move":
                    press(env, args.style, window, "m", 0.2)
                    result["events"].append({"key": "m", "action": "open-watch"})
                    time.sleep(2)
                    screenshot(out / "01_watch.png", env, window)
                    shots.append("01_watch.png")
                    press(env, args.style, window, "m", 0.2)
                    result["events"].append({"key": "m", "action": "close-watch"})
                    time.sleep(1.5)
                    send(env, args.style, window, "Up", "down")
                    time.sleep(4)
                    screenshot(out / "02_up_held.png", env, window)
                    shots.append("02_up_held.png")
                    send(env, args.style, window, "Up", "up")
                    result["events"].append({"key": "Up", "action": "hold-4s"})
                    time.sleep(1)
                    screenshot(out / "03_after_move.png", env, window)
                    shots.append("03_after_move.png")
                else:
                    time.sleep(5)
                    screenshot(out / "01_idle_5s.png", env, window)
                    shots.append("01_idle_5s.png")
                result["screenshots"] = shots
                result["nro_sha256"] = hashlib.sha256(args.nro.expanduser().read_bytes()).hexdigest()
    finally:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=8)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        log_handle.close()
        if recorder is not None and recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
            try:
                recorder.wait(timeout=5)
            except subprocess.TimeoutExpired:
                recorder.kill()
        if xvfb is not None:
            xvfb.terminate()
            try:
                xvfb.wait(timeout=3)
            except subprocess.TimeoutExpired:
                xvfb.kill()

    if engine_log.exists():
        shutil.copy2(engine_log, out / "engine.log")
        text = engine_log.read_text(errors="replace")
        result["engine_frames"] = [line for line in text.splitlines() if "rendered in" in line][-4:]
        result["engine_input"] = [line for line in text.splitlines() if "input:" in line][:8]
    if eden_log_path.exists():
        shutil.copy2(eden_log_path, out / "eden_log.txt")
    ppm = guest / "ppm"
    if ppm.is_dir():
        (out / "ppm").mkdir(exist_ok=True)
        for item in ppm.iterdir():
            shutil.copy2(item, out / "ppm" / item.name)
    if audio_path is not None:
        result["audio_file"] = str(audio_path)
        result["audio"] = wav_stats(audio_path)
    (out / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result.get("ready") else 1


if __name__ == "__main__":
    sys.exit(main())
