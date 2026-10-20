#!/usr/bin/env python3
"""Build a ROM-free ARM64 diagnostic using reproducible Eden MME uploads.

Requires devkitA64/libnx/deko3d/uam, cc/c++, meson, ninja, flex and bison.
The fresh work directory holds third-party source, tools and library builds;
no installed devkitPro library or existing checkout is modified.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "dekotools": ("https://github.com/fincs/dekotools.git", "c15523cea963c04fad77a46f23c3a96d26a86ab9"),
    "deko3d": ("https://github.com/devkitPro/deko3d.git", "373bfd43d8b2d805fa2eb7d406dbb823032df958"),
}
ENGINE = "fda76b69837e6c5aae436e0d3e798989e49b06d2"


def run(*args, **kwargs):
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True, help="fresh directory; never reused")
    parser.add_argument("--upstream", type=Path, required=True, help="pinned GoldenEye PC Port checkout")
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    # CI bind-mounts this explicitly selected checkout into a root container.
    # Scope Git's ownership exception to this read and this exact directory.
    head = subprocess.check_output(
        ["git", "-c", f"safe.directory={upstream}", "-C", str(upstream), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if head != ENGINE:
        parser.error(f"upstream must be pinned to {ENGINE}")
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    for name, (url, commit) in PINS.items():
        source = work / name
        run("git", "init", "-q", source)
        run("git", "-C", source, "remote", "add", "origin", url)
        run("git", "-C", source, "fetch", "--depth=1", "origin", commit)
        run("git", "-C", source, "checkout", "--detach", "FETCH_HEAD")
    tools = work / "tools-build"
    run("meson", "setup", tools, work / "dekotools")
    run("ninja", "-C", tools)
    env = os.environ.copy()
    env["PATH"] = str(tools) + os.pathsep + env["PATH"]
    # Generate both headers with the exact same source and input order.
    deko = work / "deko3d"
    run("make", "-C", deko, "-j2", env=env)
    original = work / "mme-original.h"
    original.write_bytes((deko / "release/mme_macros.h").read_bytes())
    run("git", "-C", work / "dekotools", "apply",
        ROOT / "patches/dekotools/eden-macro-upload.patch")
    run("ninja", "-C", tools)
    # Regenerate both release/debug headers after changing the generator.
    for variant in ("release", "debug"):
        (deko / variant / "mme_macros.h").unlink()
    run("make", "-C", deko, "-j2", env=env)
    run(sys.executable, ROOT / "scripts/check_deko_mme_upload.py",
        original, deko / "release/mme_macros.h")
    run("make", "-C", ROOT / "nxlab/switch_deko_smoke", "-j2",
        "BUILD=build-eden-mme", "TARGET=goldeneye-deko-mme",
        f"GE_UPSTREAM={upstream}", f"GE_DEKO_LIBDIR={deko / 'lib'}", env=env)
    print("Built goldeneye-deko-mme.nro: diagnostic only; no game engine or ROM.")


if __name__ == "__main__":
    main()
