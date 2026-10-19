"""Read-only toolchain doctor for a genuine Castle Crashers port."""
import argparse
import json
import re
import shutil
import subprocess

TOOLING = ("rexglue", "clang++", "cmake", "ninja", "aarch64-none-elf-g++",
           "elf2nro", "eden-cli", "llama-server")


def _version(binary):
    try:
        process = subprocess.run([binary, "--version"], text=True, timeout=4,
                                 check=False, capture_output=True)
        return (process.stdout or process.stderr).splitlines()[0][:160]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def doctor(lookup=shutil.which, version=_version):
    result = {}
    for name in TOOLING:
        executable = lookup(name)
        result[name] = {"installed": bool(executable),
                        "version": version(executable) if executable else None}
    raw = result["clang++"]["version"] or ""
    match = re.search(r"(?:clang version|clang\+\+ version)\s+(\d+)", raw)
    clang20 = bool(match and int(match.group(1)) >= 20)
    result["clang++"]["supported_rexglue_version"] = clang20
    ready = result["rexglue"]["installed"] and clang20
    return {"tools": result, "rexglue_ready": bool(ready),
            "can_validate_switch_nro": bool(result["elf2nro"]["installed"]),
            "can_run_eden": bool(result["eden-cli"]["installed"]),
            "blocker": ("needs_real_xex_codegen_test" if ready
                        else "rexglue_or_clang20")}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check real Castle Crashers port toolchain")
    parser.parse_args(argv)
    print(json.dumps(doctor(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
