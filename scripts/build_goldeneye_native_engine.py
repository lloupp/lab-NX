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
    parser.add_argument("--deko3d", action="store_true",
                        help="build the deko3d backend instead of Fast3D/Mesa/OpenGL")
    parser.add_argument("--deko-lib", type=Path,
                        help="patched libdeko3d.a (MME upload fix); required for Eden")
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
    msaa_patch = ROOT / "patches/goldeneye-pc-port/switch-msaa-resolve.patch"
    run("git", "apply", "--check", msaa_patch, cwd=source)
    run("git", "apply", msaa_patch, cwd=source)
    trace_patch = ROOT / "patches/goldeneye-pc-port/fast3d-runtime-trace.patch"
    run("git", "apply", "--check", trace_patch, cwd=source)
    run("git", "apply", trace_patch, cwd=source)
    adapter_patch = ROOT / "patches/goldeneye-pc-port/fast3d-adapter-bridge.patch"
    run("git", "apply", "--check", adapter_patch, cwd=source)
    run("git", "apply", adapter_patch, cwd=source)
    if args.deko3d:
        deko_patch = ROOT / "patches/goldeneye-pc-port/deko3d-backend.patch"
        run("git", "apply", "--check", deko_patch, cwd=source)
        run("git", "apply", deko_patch, cwd=source)
    for name in ("ge_switch_vm.c", "ge_switch_vm.h", "ge_engine_switch_runtime.c"):
        shutil.copy2(ROOT / "nxlab/switch_engine_runtime" / name, source / "port/src" / name)
    shutil.copy2(ROOT / "nxlab/native/goldeneye_fast3d_bridge.c", source / "port/src/goldeneye_fast3d_bridge.c")
    for name in ("goldeneye_fast3d_bridge.h", "goldeneye_gfx_subset.h", "goldeneye_gfx_subset.cpp"):
        shutil.copy2(ROOT / "nxlab/native" / name if name == "goldeneye_fast3d_bridge.h"
                     else ROOT / "nxlab/engine_adapter" / name,
                     source / "port/fast3d" / name)
    shutil.copy2(ROOT / "nxlab/native/goldeneye_fast3d_bridge.h", source / "port/src/goldeneye_fast3d_bridge.h")
    if args.deko3d:
        for name in ("gfx_deko3d.cpp", "gfx_deko3d.h"):
            shutil.copy2(ROOT / "nxlab/deko_backend" / name, source / "port/fast3d" / name)
        shader_dir = work / "deko-shaders"
        shader_dir.mkdir()
        uam = dkp / "tools/bin/uam"
        run(uam, "-s", "vert", "-o", shader_dir / "triangle_vsh.dksh",
            ROOT / "nxlab/deko_backend/shaders/triangle_vsh.glsl")
        run(uam, "-s", "frag", "-o", shader_dir / "color_fsh.dksh",
            ROOT / "nxlab/deko_backend/shaders/color_fsh.glsl")
        run(uam, "-s", "vert", "-o", shader_dir / "fogtex_vsh.dksh",
            ROOT / "nxlab/deko_backend/shaders/fogtex_vsh.glsl")
        run(uam, "-s", "frag", "-o", shader_dir / "fogtex_fsh.dksh",
            ROOT / "nxlab/deko_backend/shaders/fogtex_fsh.glsl")
        run(uam, "-s", "vert", "-o", shader_dir / "env2tex_vsh.dksh",
            ROOT / "nxlab/deko_backend/shaders/env2tex_vsh.glsl")
        run(uam, "-s", "frag", "-o", shader_dir / "env2tex_fsh.dksh",
            ROOT / "nxlab/deko_backend/shaders/env2tex_fsh.glsl")
        run(uam, "-s", "frag", "-o", shader_dir / "env2tex_alpha_fsh.dksh",
            ROOT / "nxlab/deko_backend/shaders/env2tex_alpha_fsh.glsl")
        run(uam, "-s", "vert", "-o", shader_dir / "flat_vsh.dksh",
            ROOT / "nxlab/deko_backend/shaders/flat_vsh.glsl")
        run(uam, "-s", "frag", "-o", shader_dir / "flat_fsh.dksh",
            ROOT / "nxlab/deko_backend/shaders/flat_fsh.glsl")

        def emit(name: str, path: Path) -> str:
            data = path.read_bytes()
            values = ",".join(str(byte) for byte in data)
            return (f"static const unsigned char {name}[] = {{{values}}};\n"
                    f"static const unsigned int {name}_len = {len(data)}u;\n")

        header = ("#pragma once\n"
                  + emit("deko_triangle_vsh", shader_dir / "triangle_vsh.dksh")
                  + emit("deko_color_fsh", shader_dir / "color_fsh.dksh")
                  + emit("deko_fogtex_vsh", shader_dir / "fogtex_vsh.dksh")
                  + emit("deko_fogtex_fsh", shader_dir / "fogtex_fsh.dksh")
                  + emit("deko_env2tex_vsh", shader_dir / "env2tex_vsh.dksh")
                  + emit("deko_env2tex_fsh", shader_dir / "env2tex_fsh.dksh")
                  + emit("deko_env2tex_alpha_fsh", shader_dir / "env2tex_alpha_fsh.dksh")
                  + emit("deko_flat_vsh", shader_dir / "flat_vsh.dksh")
                  + emit("deko_flat_fsh", shader_dir / "flat_fsh.dksh"))
        (source / "port/fast3d/deko_shader_bytes.h").write_text(header)
    # The original CMake source lists and all NTSC-U definitions remain authoritative.
    libs = dkp / "portlibs/switch"
    build = work / "build"
    run("cmake", "-G", "Ninja", "-S", source, "-B", build,
        f"-DCMAKE_TOOLCHAIN_FILE={ROOT / 'cmake/goldeneye-switch.cmake'}",
        f"-DSDL2_INCLUDE_DIR={libs / 'include/SDL2'}", f"-DSDL2_LIBRARY={libs / 'lib/libSDL2.a'}",
        f"-DZLIB_INCLUDE_DIR={libs / 'include'}", f"-DZLIB_LIBRARY={libs / 'lib/libz.a'}",
        "-DGL_LIBRARY=EGL", "-DEXTRA_LIBRARIES=glapi;stdc++;m;drm_nouveau;nx;pthread",
        *(["-DGE_DEKO3D=ON"] if args.deko3d else []),
        *([f"-DGE_DEKO3D_LIBRARY={args.deko_lib.resolve()}"] if args.deko_lib else []))
    run("cmake", "--build", build, "-j", args.jobs)
    run(dkp / "tools/bin/nacptool", "--create", "GoldenEye native engine experiment", "lab-NX", "0.2.0", work / "engine.nacp")
    nro_name = "goldeneye-native-engine-deko.nro" if args.deko3d else "goldeneye-native-engine.nro"
    run(dkp / "tools/bin/elf2nro", build / "ge007.aarch64", work / nro_name,
        f"--nacp={work / 'engine.nacp'}")
    nro = work / nro_name
    manifest = {"upstream_commit": PIN, "sha256": hashlib.sha256(nro.read_bytes()).hexdigest(),
                "nro_bytes": nro.stat().st_size, "architecture": "AArch64", "rom_bundled": False,
                "renderer": "deko3d" if args.deko3d else "Fast3D/Mesa/nouveau",
                "fast3d_trace_enabled": True,
                "fast3d_adapter_bridge_observer_enabled": True,
                "deko3d_backend_enabled": bool(args.deko3d), "gameplay_verified": False,
                "compiler": subprocess.check_output([str(dkp / "devkitA64/bin/aarch64-none-elf-gcc"), "--version"], text=True).splitlines()[0]}
    (work / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Experimental full-engine NRO: {nro}")
    if args.deko3d:
        print("deko3d backend stage 1: swapchain/queue + SHADE/fogtex draws; textures not sampled.")
        if not args.deko_lib:
            print("WARNING: stock libdeko3d.a hits the Eden dkQueueCreate bug; pass --deko-lib.")
        else:
            print(f"deko3d library: {args.deko_lib.resolve()}")
    else:
        print("Uses Fast3D + Switch Mesa/nouveau. Full deko3d backend and gameplay remain unverified.")


if __name__ == "__main__":
    main()
