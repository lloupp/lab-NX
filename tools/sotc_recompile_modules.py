#!/usr/bin/env python3
"""Rebuild a private Celosia combined ELF from real loaded XFF RAM captures.

USAGE:
  python tools/sotc_recompile_modules.py --celosia ../celosia \
    --disc /private/sotc/disc --work /private/sotc/stages/kernel \
    --recompiler /private/bin/ps2_recomp --kernel-ram /private/kernel.bin

Add --manager-ram and then --gamecore-ram as each new stage is captured.
Never commit generated ELF, RAM dumps, compiled game or C++ output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

EXPECTED_ELF_SHA1 = "b715b3496aad6f7601a0ab8495acd1d151a1ff7b"
MODULES = ("KERNEL", "MANAGER", "GAMECORE")


def run_cmd(argv, cwd=None, log=None):
    if log:
        with open(log, "w", encoding="utf-8") as fd:
            result = subprocess.run(argv, cwd=cwd, stdout=fd,
                                    stderr=subprocess.STDOUT, check=False)
    else:
        result = subprocess.run(argv, cwd=cwd, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {argv[0]} ({log})")


def execute(args):
    upstream = args.celosia.resolve()
    disc = args.disc.resolve()
    work = args.work.resolve()
    compiler = args.recompiler.resolve()
    elf = disc / "SCUS_974.72"
    actual = hashlib.sha1(elf.read_bytes()).hexdigest()
    if actual != EXPECTED_ELF_SHA1:
        raise ValueError(f"not expected USA game ELF (SHA1 {actual})")
    if not compiler.is_file():
        raise ValueError(f"missing recompiler: {compiler}")

    captures = [args.kernel_ram, args.manager_ram, args.gamecore_ram]
    first_missing = next((i for i, x in enumerate(captures) if x is None), 3)
    if first_missing < 3 and any(x is not None for x in captures[first_missing + 1:]):
        raise ValueError("captures must be provided in KERNEL -> MANAGER -> GAMECORE order")
    if first_missing == 0:
        raise ValueError("at least --kernel-ram is required")

    tools = upstream / "tools"
    for required in ("build_elf.py", "gen_config.py", "xff.py", "elfmini.py",
                     "funcmap_elf.py"):
        if not (tools / required).is_file():
            raise ValueError(f"missing Celosia helper: {required}")
    for module in MODULES[:first_missing]:
        binary = disc / f"{module}.XFF"
        if not binary.is_file() or binary.open("rb").read(4) != b"xff2":
            raise ValueError(f"missing XFF2 module: {binary}")
    work.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(tools))
    from xff import Xff, SHN_ABS

    symbols = sorted({(s.value, s.name) for s in Xff(str(disc / "KERNEL.XFF")).symbols
                      if s.shndx == SHN_ABS and s.name})
    symbol_file = work / "boot_symbols.txt"
    symbol_file.write_text("".join(f"{address:08x} {name}\n" for address, name in symbols))
    specs = []
    for name, ram in zip(MODULES[:first_missing], captures):
        ram = ram.resolve()
        if not ram.is_file() or ram.stat().st_size != 32 * 1024 * 1024:
            raise ValueError(f"expected real 32 MiB guest RAM capture: {ram}")
        specs.append(f"{disc / (name + '.XFF')}@auto@{ram}")

    run_cmd([sys.executable, str(tools / "build_elf.py"), str(work),
             str(elf), str(symbol_file), *specs], log=work / "build_elf.log")
    run_cmd([sys.executable, str(tools / "gen_config.py"), str(work),
             str(upstream / "game" / "scus.toml")], log=work / "config.log")
    run_cmd([str(compiler), "config.toml"], cwd=work, log=work / "recompile.log")

    output = work / "output"
    if not (output / "register_functions.cpp").is_file():
        raise RuntimeError("PS2Recomp did not generate the guest dispatch table")
    log = (work / "recompile.log").read_text(errors="replace")
    def extract(pattern):
        match = re.search(pattern, log)
        return int(match.group(1)) if match else None
    result = {
        "stage": MODULES[first_missing-1].lower(),
        "private": True,
        "functions_discovered": extract(r"Functions discovered:\s*(\d+)"),
        "recompiled": extract(r"recompiled:\s*(\d+)"),
        "stubs": extract(r"stubs:\s*(\d+)"),
        "decode_failures": extract(r"decode failures:\s*(\d+)"),
        "errors": extract(r"Warnings:\s*\d+, errors:\s*(\d+)"),
        "cpp_files": len(list(output.glob("*.cpp"))),
        "linked_elf_bytes": (work / "SOTC.elf").stat().st_size,
    }
    if result["decode_failures"] != 0 or result["errors"] != 0:
        raise RuntimeError(f"recompilation not clean; check private logs: {result}")
    (work / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--celosia", type=Path, required=True)
    p.add_argument("--disc", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--recompiler", type=Path, required=True)
    p.add_argument("--kernel-ram", type=Path)
    p.add_argument("--manager-ram", type=Path)
    p.add_argument("--gamecore-ram", type=Path)
    try:
        execute(p.parse_args())
    except (OSError, ValueError, RuntimeError) as exc:
        p.exit(2, f"ERROR: {exc}\n")
