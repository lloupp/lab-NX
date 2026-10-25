#!/usr/bin/env python3
"""Build the complete pinned game as a Switch NRO. Experimental, not gameplay proof.
No ROM or generated sidecars are accepted, fetched or bundled by this script.
"""
import argparse
import io
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
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
            members = stream.getmembers()
            for member in members:
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError(f"unsafe archive path: {member.name}")
                if not (member.isfile() or member.isdir()):
                    raise ValueError(f"unsupported archive entry: {member.name}")
            if hasattr(tarfile, "data_filter"):
                stream.extractall(source, members=members, filter="data")
            else:
                stream.extractall(source, members=members)
    else:
        run("git", "clone", "--no-checkout", "https://github.com/jkdansereau/goldeneye-pc-port", source)
        run("git", "-C", source, "checkout", "--detach", PIN)
    run("git", "apply", "--check", ROOT / "patches/goldeneye-pc-port/switch-platform.patch", cwd=source)
    run("git", "apply", ROOT / "patches/goldeneye-pc-port/switch-platform.patch", cwd=source)
    msaa_patch = ROOT / "patches/goldeneye-pc-port/switch-msaa-default.patch"
    run("git", "apply", "--check", msaa_patch, cwd=source)
    run("git", "apply", msaa_patch, cwd=source)
    trace_patch = ROOT / "patches/goldeneye-pc-port/fast3d-runtime-trace.patch"
    run("git", "apply", "--check", trace_patch, cwd=source)
    run("git", "apply", trace_patch, cwd=source)
    adapter_patch = ROOT / "patches/goldeneye-pc-port/fast3d-adapter-bridge.patch"
    run("git", "apply", "--check", adapter_patch, cwd=source)
    run("git", "apply", adapter_patch, cwd=source)
    for name in ("ge_switch_vm.c", "ge_switch_vm.h", "ge_engine_switch_runtime.c"):
        shutil.copy2(ROOT / "nxlab/switch_engine_runtime" / name, source / "port/src" / name)
    shutil.copy2(ROOT / "nxlab/native/goldeneye_fast3d_bridge.c", source / "port/src/goldeneye_fast3d_bridge.c")
    for name in ("goldeneye_fast3d_bridge.h", "goldeneye_gfx_subset.h", "goldeneye_gfx_subset.cpp"):
        shutil.copy2(ROOT / "nxlab/native" / name if name == "goldeneye_fast3d_bridge.h"
                     else ROOT / "nxlab/engine_adapter" / name,
                     source / "port/fast3d" / name)
    shutil.copy2(ROOT / "nxlab/native/goldeneye_fast3d_bridge.h", source / "port/src/goldeneye_fast3d_bridge.h")
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
                "renderer": "Fast3D/Mesa/nouveau", "fast3d_trace_enabled": True,
                "fast3d_adapter_bridge_observer_enabled": True,
                "deko3d_backend_enabled": False, "gameplay_verified": False,
                "compiler": subprocess.check_output([str(dkp / "devkitA64/bin/aarch64-none-elf-gcc"), "--version"], text=True).splitlines()[0]}
    (work / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Experimental full-engine NRO: {work / 'goldeneye-native-engine.nro'}")
    print("Uses Fast3D + Switch Mesa/nouveau. Full deko3d backend and gameplay remain unverified.")


if __name__ == "__main__":
    main()
