"""Private, evidence-gated ReXGlue XEX -> C++ -> host executable pipeline.

Never uploads a game, keys, decompiled code or the generated executable.
The output directory MUST be outside every Git worktree.
A host binary is NOT a Nintendo Switch NRO nor evidence of gameplay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import uuid


class NativeBuildError(ValueError):
    pass


def private_workspace(path: Path) -> Path:
    root = Path(path).expanduser().resolve()
    if root.is_file() or any((p / ".git").exists() for p in (root, *root.parents)):
        raise NativeBuildError("Workspace must be a directory outside Git")
    return root


def install_hints(manifest: Path, hints: Path) -> None:
    """Copy a validated functions-only TOML include into generated private project."""
    content = Path(hints).read_bytes()
    if len(content) > 65536:
        raise NativeBuildError("Hints TOML is too large")
    try:
        data = tomllib.loads(content.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise NativeBuildError("Hints TOML is invalid") from exc
    if set(data) != {"functions"} or not isinstance(data["functions"], dict):
        raise NativeBuildError("Only [functions] is allowed in this hints file")
    for address, options in data["functions"].items():
        if not re.fullmatch(r"0x[0-9a-fA-F]{8}", address) or not isinstance(options, dict):
            raise NativeBuildError("Unexpected function hint")
        if set(options) - {"size"}:
            raise NativeBuildError("Unsupported function hint option")
        if "size" in options and (type(options["size"]) is not int
                                  or not 4 <= options["size"] <= 0x100000
                                  or options["size"] % 4):
            raise NativeBuildError("Invalid explicit function size")
    original = manifest.read_text(encoding="utf-8")
    if original.count("includes = []") != 1:
        raise NativeBuildError("Unrecognized ReXGlue manifest include field")
    filename = "nxlab_functions.toml"
    destination = manifest.parent / filename
    with destination.open("xb") as stream:
        stream.write(content)
    manifest.write_text(original.replace("includes = []",
                     f'includes = ["{filename}"]', 1), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_process(args: list[str], cwd: Path, log: Path, timeout: int) -> int:
    """No shell, bounded execution and private logs."""
    try:
        with log.open("xb") as stream:
            result = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL,
                                    stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
        return result.returncode
    except subprocess.TimeoutExpired:
        with log.open("ab") as stream:
            stream.write(b"\n[timeout]\n")
        return 124
    except OSError as exc:
        raise NativeBuildError(f"Cannot launch {Path(args[0]).name}: {type(exc).__name__}") from exc


def build_private(xex: Path, workspace: Path, sdk_prefix: Path,
                  hints: Path | None = None, project: str = "castle_crashers",
                  compiler: str = "clang++", parallel: int = 2,
                  timeout: int = 300, build: bool = True):
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,48}", project):
        raise NativeBuildError("Invalid project name")
    if not 1 <= parallel <= 8 or not 10 <= timeout <= 1800:
        raise NativeBuildError("Invalid build limits")
    xex = Path(xex).expanduser().resolve(strict=True)
    if not xex.is_file() or xex.stat().st_size > 256 * 1024 * 1024:
        raise NativeBuildError("Expected a bounded XEX file")
    with xex.open("rb") as src:
        if src.read(4) != b"XEX2":
            raise NativeBuildError("Input is not XEX2")
    workspace = private_workspace(workspace)
    sdk = Path(sdk_prefix).expanduser().resolve()
    binary = sdk / "bin" / "rexglue"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise NativeBuildError("Missing executable in SDK prefix: bin/rexglue")
    if build:
        cc = shutil.which(compiler) if "/" not in compiler else str(Path(compiler).resolve())
        if not cc or not Path(cc).is_file():
            raise NativeBuildError("C++ compiler is not installed")
        if not shutil.which("cmake") or not shutil.which("ninja"):
            raise NativeBuildError("CMake and Ninja are required for native linking")

    run_dir = workspace / "runs" / uuid.uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    report = {
        "schema": 1, "project": project, "sdk_binary_sha256": sha256(binary),
        "source_xex_sha256": sha256(xex), "steps": [],
        "game_playable": False, "switch_nro_built": False,
        "game_frame_verified": False, "native_guest_behavior_verified": False
    }
    def record(step, status, detail):
        report["steps"].append({"name": step, "status": status, "detail": detail})

    code = 2
    try:
        version_log = run_dir / "rexglue-version.log"
        if run_process([str(binary), "--version"], run_dir, version_log, 20):
            raise NativeBuildError("Cannot read SDK version")
        version = version_log.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        report["sdk_version"] = version[0][:120] if version else "unknown"
        root = run_dir / "project"
        init_rc = run_process([
            str(binary), "init", "--project-name", project,
            "--xex-path", str(xex), "--project-root", str(root)
        ], run_dir, run_dir / "rexglue-init.log", min(120, timeout))
        if init_rc:
            record("sdk_init", "failed", f"SDK init returned {init_rc}")
        else:
            manifests = list(root.glob("*_manifest.toml"))
            if len(manifests) != 1:
                raise NativeBuildError("Expected exactly one initialized manifest")
            if hints is not None:
                install_hints(manifests[0], hints)
            record("sdk_init", "passed", "Private ReXGlue project initialized")
            rc = run_process([str(binary), "codegen", manifests[0].name],
                             root, run_dir / "rexglue-codegen.log", timeout)
            if rc:
                record("ppc_codegen", "failed", f"ReXGlue exited with {rc}; see private log")
            else:
                cpp = list((root / "generated").rglob("*_recomp.*.cpp"))
                if not cpp:
                    raise NativeBuildError("Codegen returned zero but emitted no recompilation units")
                report["recompiled_cpp_units"] = len(cpp)
                report["generated_cpp_bytes"] = sum(f.stat().st_size for f in
                    (root / "generated").rglob("*.cpp"))
                record("ppc_codegen", "passed", "Original XEX translated into private C++ units")
                if not build:
                    record("host_link", "skipped", "Build was not requested")
                    code = 0
                else:
                    builddir = root / "out" / "build" / "labnx-host"
                    conf = [
                        "cmake", "-S", str(root), "-B", str(builddir), "-G", "Ninja",
                        "-DCMAKE_BUILD_TYPE=Release",
                        "-DCMAKE_CXX_COMPILER=" + cc,
                        "-DCMAKE_CXX_FLAGS_RELEASE=-O0 -DNDEBUG",
                        "-DREXGLUE_RECOMP_DEBUG_INFO=none",
                        "-DCMAKE_PREFIX_PATH=" + str(sdk)
                    ]
                    rc = run_process(conf, root, run_dir / "cmake-configure.log", min(120, timeout))
                    if rc:
                        record("host_link", "failed", f"CMake configure returned {rc}")
                    else:
                        rc = run_process([
                            "cmake", "--build", str(builddir),
                            "--parallel", str(parallel)
                        ], root, run_dir / "host-build.log", timeout)
                        exe = builddir / project.replace("_", "")
                        if rc or not exe.is_file():
                            record("host_link", "failed", f"Host build returned {rc}; see private log")
                        else:
                            with exe.open("rb") as stream:
                                head = stream.read(20)
                            if (head[:4] != b"\x7fELF" or len(head) < 20
                                    or int.from_bytes(head[18:20], "little") != 62):
                                raise NativeBuildError("Linked result is not x86-64 ELF")
                            report["host_elf_size_bytes"] = exe.stat().st_size
                            report["host_elf_sha256"] = sha256(exe)
                            record("host_link", "passed", "ELF64 x86-64 linked; gameplay not verified")
                            code = 0
    except (OSError, ValueError) as exc:
        record("pipeline", "failed", f"{type(exc).__name__}: {exc}")
        code = 2
    finally:
        report["exit_code"] = code
        (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n",
                                             encoding="utf-8")
    return report, run_dir, code


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private ReXGlue host compilation")
    parser.add_argument("--xex", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--sdk-prefix", type=Path, required=True)
    parser.add_argument("--hints", type=Path)
    parser.add_argument("--project", default="castle_crashers")
    parser.add_argument("--compiler", default="clang++")
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    try:
        result, folder, exit_code = build_private(
            args.xex, args.workspace, args.sdk_prefix, args.hints,
            args.project, args.compiler, args.parallel, args.timeout,
            build=not args.no_build)
        print(json.dumps({"report": str(folder / "report.json"),
                          "steps": result["steps"], "exit_code": exit_code},
                         indent=2, ensure_ascii=False))
        return exit_code
    except (OSError, ValueError) as exc:
        print(f"NX-Lab ReXGlue: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
