#!/usr/bin/env python3
"""Recompile the user's original SOTC USA boot ELF via pinned Celosia tools.

Writes game-derived binary/C++ only to --work (keep this directory private).
Dependencies: Python 3.10+, Celosia checkout, compiled ps2_recomp executable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

SECTOR = 2048
NEEDED = {'SCUS_974.72', 'KERNEL.XFF'}


def extract_boot_components(iso: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    size = iso.stat().st_size
    if size < 18 * SECTOR or size % SECTOR:
        raise ValueError('invalid sector count')
    found = {}
    with iso.open('rb') as stream:
        stream.seek(16 * SECTOR)
        pvd = stream.read(SECTOR)
        if pvd[:7] != b'\x01CD001\x01':
            raise ValueError('not ISO9660 PVD')
        root = pvd[156:190]
        root_lba = int.from_bytes(root[2:6], 'little')
        root_len = int.from_bytes(root[10:14], 'little')
        if not root_len or root_len > 1024*1024 or root_lba * SECTOR + root_len > size:
            raise ValueError('invalid root directory')
        stream.seek(root_lba * SECTOR)
        data = stream.read(root_len)
        i = 0
        while i < len(data):
            rec_len = data[i]
            if rec_len == 0:
                i = ((i // SECTOR) + 1) * SECTOR
                continue
            if rec_len < 34 or i + rec_len > len(data) or rec_len > SECTOR - i % SECTOR:
                raise ValueError('malformed ISO directory entry')
            rec = data[i:i + rec_len]
            i += rec_len
            name_len = rec[32]
            if 33 + name_len > rec_len or rec[25] & 2:
                continue
            name = rec[33:33+name_len].split(b';', 1)[0].decode('ascii', 'replace').upper()
            if name not in NEEDED:
                continue
            offset = int.from_bytes(rec[2:6], 'little') * SECTOR
            length = int.from_bytes(rec[10:14], 'little')
            if length == 0 or offset > size or length > size-offset:
                raise ValueError('invalid game file extent')
            stream.seek(offset)
            blob = stream.read(length)
            if len(blob) != length:
                raise ValueError('short game file read')
            if name == 'SCUS_974.72' and (len(blob) < 52 or blob[:4] != b'\x7fELF'
                                         or blob[4:6] != b'\x01\x01'
                                         or int.from_bytes(blob[18:20], 'little') != 8):
                raise ValueError('not PS2 MIPS ELF')
            if name == 'KERNEL.XFF' and blob[:4] != b'xff2':
                raise ValueError('not SOTC xff2 module')
            (dest / name).write_bytes(blob)
            found[name] = {'bytes': length, 'sha256': hashlib.sha256(blob).hexdigest()}
            stream.seek(root_lba * SECTOR)
            data = stream.read(root_len)
    if set(found) != NEEDED:
        raise ValueError(f'missing disc components: {sorted(NEEDED-set(found))}')
    return found


def run(args):
    iso = args.iso.resolve()
    work = args.work.resolve()
    upstream = args.celosia.resolve()
    exe = args.recompiler.resolve()
    if not exe.is_file():
        raise ValueError('missing PS2Recomp compiler executable')
    for src in ('tools/xff.py', 'tools/elfmini.py', 'tools/funcmap_elf.py', 'game/scus.toml'):
        if not (upstream / src).is_file():
            raise ValueError(f'missing upstream source: {src}')
    work.mkdir(parents=True, exist_ok=True)
    disc = work / 'disc'
    files = extract_boot_components(iso, disc)
    sys.path.insert(0, str(upstream / 'tools'))
    from xff import Xff, SHN_ABS
    from funcmap_elf import main as make_funcmap
    xff = Xff(str(disc / 'KERNEL.XFF'))
    symbols = sorted({(s.value, s.name) for s in xff.symbols
                      if s.shndx == SHN_ABS and s.name})
    symbols_file = work / 'scus_symbols.txt'
    symbols_file.write_text(''.join(f'{addr:08x} {name}\n' for addr, name in symbols))
    recomp = work / 'recomp' / 'scus'
    recomp.mkdir(parents=True, exist_ok=True)
    make_funcmap(str(disc / 'SCUS_974.72'), str(symbols_file), str(recomp / 'functions.csv'))
    cfg = (upstream / 'game/scus.toml').read_text()
    path = str((disc / 'SCUS_974.72').resolve()).replace('\\', '\\\\')
    cfg, replacements = re.subn(r'(?m)^input\s*=.*$', 'input = "' + path + '"', cfg, count=1)
    if replacements != 1:
        raise ValueError('upstream config unexpectedly lacks input entry')
    (recomp / 'config.toml').write_text(cfg)
    proc = subprocess.run([str(exe), 'config.toml'], cwd=recomp,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (recomp / 'recompile.log').write_text(proc.stdout)
    if proc.returncode:
        raise RuntimeError(f'PS2Recomp exited {proc.returncode}; see private recompile.log')
    def metric(pattern):
        match = re.search(pattern, proc.stdout)
        if match is None:
            raise ValueError('missing official recompilation summary: ' + pattern)
        return int(match.group(1))
    result = {
        'boot': 'SCUS_974.72', 'private_input_files': files,
        'named_absolute_imports': len(symbols),
        'functions_discovered': metric(r'Functions discovered:\s*(\d+)'),
        'functions_recompiled': metric(r'recompiled:\s*(\d+)'),
        'stubs': metric(r'stubs:\s*(\d+)'),
        'decode_failures': metric(r'decode failures:\s*(\d+)'),
        'errors': metric(r'Warnings:\s*\d+, errors:\s*(\d+)'),
        'output_cpp_files': len(list((recomp / 'output').glob('*.cpp'))),
        'celosia_source': str(upstream),
    }
    (work / 'stage1_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k,v in result.items()
                      if k not in ('private_input_files', 'celosia_source')}, indent=2))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iso', type=Path, required=True, help='original private PS2 ISO')
    p.add_argument('--celosia', type=Path, required=True, help='pinned Celosia checkout')
    p.add_argument('--recompiler', type=Path, required=True, help='compiled upstream ps2_recomp')
    p.add_argument('--work', type=Path, required=True, help='private output directory')
    args = p.parse_args()
    try:
        return run(args)
    except (OSError, ValueError, RuntimeError) as exc:
        p.exit(2, f'stage 1 failed: {exc}\n')

if __name__ == '__main__':
    raise SystemExit(main())
