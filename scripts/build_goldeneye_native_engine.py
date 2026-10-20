#!/usr/bin/env python3
"""Build the complete pinned game as a Switch NRO. Experimental, not gameplay proof.
No ROM or generated sidecars are accepted, fetched or bundled by this script.
"""
import argparse
import io
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

PIN = "fda76b69837e6c5aae436e0d3e798989e49b06d2"
ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True, help="New, empty build workspace")
    parser.add_argument("--source", type=Path, help="Existing upstream git repository; archived at the pin")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    dkp = Path(os.environ["DEVKITPRO"]).resolve()
    work = args.work_dir.resolve()
    if work.exists() and any(work.iterdir()):
        parser.error("--work-dir must be empty (existing work is never overwritten)")
    work.mkdir(parents=True, exist_ok=True)
    source = work / "source"
    if args.source:
        archive = subprocess.check_output(["git", "-C", str(args.source.resolve()), "archive", PIN])
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(source, filter="data")
    else:
        run("git", "clone", "--no-checkout", "https://github.com/jkdansereau/goldeneye-pc-port", source)
        run("git", "-C", source, "checkout", "--detach", PIN)
    run("git", "apply", "--check", ROOT / "patches/goldeneye-pc-port/switch-platform.patch", cwd=source)
    run("git", "apply", ROOT / "patches/goldeneye-pc-port/switch-platform.patch", cwd=source)
    for name in ("ge_switch_vm.c", "ge_switch_vm.h", "ge_engine_switch_runtime.c"):
        shutil.copy2(ROOT / "nxlab/switch_engine_runtime" / name, source / "port/src" / name)
    # The original CMake source lists and all NTSC-U definitions remain authoritative.
    libs = dkp / "portlibs/switch"
    build = work / "build"
    run("cmake", "-G", "Ninja", "-S", source, "-B", build,
        f"-DCMAKE_TOOLCHAIN_FILE={ROOT / 'cmake/goldeneye-switch.cmake'}",
        f"-DSDL2_INCLUDE_DIR={libs / 'include/SDL2'}", f"-DSDL2_LIBRARY={libs / 'lib/libSDL2.a'}",
        f"-DZLIB_INCLUDE_DIR={libs / 'include'}", f"-DZLIB_LIBRARY={libs / 'lib/libz.a'}",
        "-DGL_LIBRARY=EGL", "-DEXTRA_LIBRARIES=glapi;stdc++;m;drm_nouveau;nx;pthread")
    run("cmake", "--build", build, "-j", args.jobs)
    run(dkp / "tools/bin/nacptool", "--create", "GoldenEye native engine experiment", "lab-NX", "0.2.0", work / "engine.nacp")
    run(dkp / "tools/bin/elf2nro", build / "ge007.aarch64", work / "goldeneye-native-engine.nro",
        f"--nacp={work / 'engine.nacp'}")
    nro = work / "goldeneye-native-engine.nro"
    manifest = {"upstream_commit": PIN, "sha256": hashlib.sha256(nro.read_bytes()).hexdigest(),
                "nro_bytes": nro.stat().st_size, "architecture": "AArch64", "rom_bundled": False,
                "renderer": "Fast3D/Mesa/nouveau", "gameplay_verified": False,
                "compiler": subprocess.check_output([str(dkp / "devkitA64/bin/aarch64-none-elf-gcc"), "--version"], text=True).splitlines()[0]}
    (work / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Experimental full-engine NRO: {work / 'goldeneye-native-engine.nro'}")
    print("Uses Fast3D + Switch Mesa/nouveau. Full deko3d backend and gameplay remain unverified.")


if __name__ == "__main__":
    main()
