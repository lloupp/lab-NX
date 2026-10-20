"""Bounded emulator comparison without commercial game files or keys.

Summed process-group VmRSS includes shared memory counted per process; it is
a trend/safety metric, not exact private physical RAM. VmSize is not RSS.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def group_pids(pgid):
    result = []
    for item in os.listdir("/proc"):
        if not item.isdecimal():
            continue
        try:
            if os.getpgid(int(item)) == pgid:
                result.append(int(item))
        except (ProcessLookupError, PermissionError):
            pass
    return result


def usage_kib(pid):
    rss = virtual = pss = 0
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1])
                elif line.startswith("VmSize:"):
                    virtual = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    try:
        with open(f"/proc/{pid}/smaps_rollup", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Pss:"):
                    pss = int(line.split()[1])
                    break
    except (OSError, ValueError, IndexError):
        pass
    return rss, virtual, pss


def screenshot(path):
    try:
        p = subprocess.run(["import", "-window", "root", str(path)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=8, check=False)
        return p.returncode == 0 and path.is_file()
    except (OSError, subprocess.TimeoutExpired):
        return False


def dismiss_initial_dialog():
    """Choose NO for Eden's optional request to install unknown decryption keys."""
    try:
        result = subprocess.run(["xdotool", "key", "--clearmodifiers", "Right", "Return"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=3, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def measure(command, dest, seconds=25.0, limit_mb=2800, every=0.5,
            dismiss_eden_keys=False):
    if not command or not 2 <= seconds <= 120 or not 128 <= limit_mb <= 10000:
        raise ValueError("Invalid command, duration or memory ceiling")
    dest = Path(dest)
    dest.mkdir(mode=0o700, parents=True, exist_ok=False)
    samples = []
    shots = []
    reason = "unknown"
    dismissals = []
    prompts_at = [3.0, 7.0] if dismiss_eden_keys else []
    return_code = None
    with (dest / "emulator.log").open("wb") as output:
        proc = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        pgid = os.getpgid(proc.pid)
        start = time.monotonic()
        checkpoints = [5.0, 12.0, 20.0, 40.0, 60.0]
        try:
            while True:
                elapsed = time.monotonic() - start
                pids = group_pids(pgid)
                measurements = [usage_kib(pid) for pid in pids]
                rss_kib = sum(m[0] for m in measurements)
                virtual_kib = sum(m[1] for m in measurements)
                pss_kib = sum(m[2] for m in measurements)
                samples.append({"time_s": round(elapsed, 2),
                                "rss_mib": round(rss_kib / 1024, 2),
                                "pss_mib": round(pss_kib / 1024, 2),
                                "virtual_mib": round(virtual_kib / 1024, 2),
                                "processes": len(pids)})
                if prompts_at and elapsed >= prompts_at[0]:
                    when = prompts_at.pop(0)
                    dismissals.append({"at_s": when,
                                      "sent_no_response": dismiss_initial_dialog()})
                if checkpoints and elapsed >= checkpoints[0]:
                    t = checkpoints.pop(0)
                    image = dest / f"screen-{int(t)}s.png"
                    if screenshot(image):
                        shots.append(image.name)
                if rss_kib >= limit_mb * 1024:
                    reason = "memory_safety_limit"
                    break
                if elapsed >= seconds:
                    reason = "time_limit"
                    break
                if proc.poll() is not None and len(pids) < 2:
                    reason = "process_exit"
                    return_code = proc.returncode
                    break
                time.sleep(every)
        finally:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=3)
    report = {
        "schema": 1, "termination": reason, "process_exit_code": return_code,
        "peak_rss_mib": max((s["rss_mib"] for s in samples), default=0),
        "peak_pss_mib": max((s["pss_mib"] for s in samples), default=0),
        "samples": samples, "screenshots": shots,
        "optional_dialog_responses": dismissals,
        "guest_execution_verified": False, "castle_rendering_verified": False,
        "rss_limit_is_not_switch_guest_ram": True,
        "note": "VmRSS sums can double-count shared pages; PSS distributes shared-page cost among processes, but may omit external GPU allocations. VmSize is virtual address space, not RAM."
    }
    (dest / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    p = argparse.ArgumentParser(description="Bounded Linux emulator RAM comparison")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seconds", type=float, default=25)
    p.add_argument("--limit-mb", type=int, default=2800)
    p.add_argument("--dismiss-eden-keys", action="store_true")
    p.add_argument("command", nargs=argparse.REMAINDER)
    opts = p.parse_args()
    command = opts.command[1:] if opts.command and opts.command[0] == "--" else opts.command
    if not command:
        p.error("Missing command after --")
    print(json.dumps(measure(command, opts.output, opts.seconds, opts.limit_mb,
                             dismiss_eden_keys=opts.dismiss_eden_keys), indent=2))


if __name__ == "__main__":
    main()
