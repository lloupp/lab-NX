"""Replay safe Xbox keyboard-controller actions against an existing X11 game window.

This is an **operator-initiated** test. It never claims a game is playable
based solely on a changed image. The application, assets and screenshot PNGs
remain in a private workspace outside the source repository.

Requirements: python-xlib, Pillow, and an X11 server with XTEST support.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

KEYS = {
    "start": "Return", "confirm": "space", "back": "BackSpace",
    "left": "a", "right": "d", "up": "w", "down": "s",
    "x": "l", "y": "p", "left_trigger": "q", "right_trigger": "e",
}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
DISPLAY_RE = re.compile(r"^:[0-9]{1,3}(?:\.[0-9]+)?$")


class InputProbeError(ValueError):
    pass


def check_private(path):
    target = Path(path).expanduser().resolve()
    if target.exists():
        raise InputProbeError("Use a new report directory, never overwrite screenshots")
    if any((p / ".git").exists() for p in (target, *target.parents)):
        raise InputProbeError("Snapshots must be stored outside Git")
    return target


def validate_actions(actions):
    if not isinstance(actions, list) or not 1 <= len(actions) <= 20:
        raise InputProbeError("Expected 1 to 20 explicit input actions")
    total_seconds = 0.0
    validated = []
    for entry in actions:
        if not isinstance(entry, dict) or set(entry) != {"name", "button", "hold_ms", "wait_ms"}:
            raise InputProbeError("Each action must define name/button/hold_ms/wait_ms")
        name, button = entry["name"], entry["button"]
        hold, wait = entry["hold_ms"], entry["wait_ms"]
        if (not isinstance(name, str) or not NAME_RE.fullmatch(name)
                or not isinstance(button, str) or button not in KEYS
                or type(hold) is not int or not 50 <= hold <= 5000
                or type(wait) is not int or not 0 <= wait <= 15000):
            raise InputProbeError("Unsupported action, key, or timing")
        total_seconds += (hold + wait) / 1000
        validated.append(entry.copy())
    if total_seconds > 180:
        raise InputProbeError("Replay time exceeds 180 seconds")
    return validated


def load_plan(file):
    path = Path(file)
    if path.stat().st_size > 16384:
        raise InputProbeError("Replay plan too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"schema", "actions"} or data["schema"] != 1:
        raise InputProbeError("Invalid replay plan schema")
    return validate_actions(data["actions"])


def find_window(dpy, name_contains):
    from Xlib import X
    root = dpy.screen().root
    found = []
    for window in root.query_tree().children:
        try:
            title = window.get_wm_name() or ""
            if (name_contains.lower() in title.lower()
                    and window.get_attributes().map_state == X.IsViewable):
                found.append(window)
        except Exception:
            pass
    if len(found) != 1:
        raise InputProbeError(f"Expected exactly one visible matching window, found {len(found)}")
    return found[0]


def run(display, workdir, actions, window_name="castlecrashers"):
    if not DISPLAY_RE.fullmatch(display):
        raise InputProbeError("Only a local X11 display such as :125 is supported")
    if not window_name or len(window_name) > 80:
        raise InputProbeError("A specific window name must be provided")
    actions = validate_actions(actions)
    out = check_private(workdir)
    try:
        from Xlib import display as xdisplay, X, XK
        from Xlib.ext import xtest
        from PIL import ImageGrab
    except ImportError as exc:
        raise InputProbeError("Install optional python-xlib and Pillow dependencies") from exc
    dpy = xdisplay.Display(display)
    try:
        window = find_window(dpy, window_name)
        if not dpy.has_extension("XTEST"):
            raise InputProbeError("X11 server lacks XTEST input extension")
        keys = {}
        for name, key_name in KEYS.items():
            code = dpy.keysym_to_keycode(XK.string_to_keysym(key_name))
            if not code:
                raise InputProbeError(f"Unmapped keyboard key for {name}")
            keys[name] = code
        out.mkdir(parents=True, exist_ok=False, mode=0o700)
        evidence = {
            "schema": 1,
            "window_match": window_name,
            "backend": "X11/XTEST",
            "actions": [],
            "automatic_gameplay_verdict": "not_evaluated",
            "human_frame_review_required": True,
            "switch_hardware_tested": False,
        }
        def shot(name):
            path = out / (name + ".png")
            im = ImageGrab.grab(xdisplay=display).convert("RGB")
            im.save(path)
            return {"file": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "width": im.width, "height": im.height}
        evidence["initial_frame"] = shot("initial")
        for index, act in enumerate(actions, 1):
            dpy.set_input_focus(window, X.RevertToPointerRoot, X.CurrentTime)
            dpy.sync()
            key = keys[act["button"]]
            xtest.fake_input(dpy, X.KeyPress, key)
            dpy.sync()
            try:
                time.sleep(act["hold_ms"] / 1000)
            finally:
                xtest.fake_input(dpy, X.KeyRelease, key)
                dpy.sync()
            time.sleep(act["wait_ms"] / 1000)
            frame = shot(f"{index:02d}_{act['name']}")
            evidence["actions"].append({
                "name": act["name"], "button": act["button"],
                "hold_ms": act["hold_ms"], "wait_ms": act["wait_ms"],
                "capture": frame,
                "image_hash_changed": frame["sha256"] !=
                (evidence["actions"][-1]["capture"]["sha256"] if evidence["actions"]
                 else evidence["initial_frame"]["sha256"]),
            })
        (out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n",
                                            encoding="utf-8")
        return evidence
    finally:
        dpy.close()


def main(argv=None):
    p = argparse.ArgumentParser(description="Private X11 game-controller replay")
    p.add_argument("--display", required=True)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--window-name", default="castlecrashers")
    args = p.parse_args(argv)
    try:
        result = run(args.display, args.workspace, load_plan(args.plan), args.window_name)
        print(json.dumps({"actions_sent": len(result["actions"]),
                          "frame_changes_observed": sum(s["image_hash_changed"] for s in result["actions"]),
                          "gameplay_verdict": result["automatic_gameplay_verdict"],
                          "output": str(args.workspace / "evidence.json")}, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        p.exit(2, f"X11 input probe: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
