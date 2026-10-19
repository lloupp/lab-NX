"""Audit translated ROM byte changes against PC port asset offsets.

A preflight only: modified asset conversions and gameplay MUST be tested.
Give scripts/filelist.u.csv from the goldeneye-pc-port checkout as argument.
"""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path

def read_ranges(path: Path) -> list[tuple[int, int, str]]:
    entries = []
    with path.open(newline='', encoding='utf-8') as handle:
        for row in csv.reader(handle):
            if len(row) < 3:
                continue
            try:
                offset, size = int(row[0]), int(row[1])
            except ValueError:
                continue
            if size > 0 and offset >= 0:
                entries.append((offset, offset + size, row[2]))
    return sorted(entries)

def changed_in_range(original: bytes, translated: bytes, start: int, end: int) -> int:
    limit = min(len(original), len(translated))
    lo, hi = min(start, limit), min(end, limit)
    return sum(x != y for x, y in zip(original[lo:hi], translated[lo:hi]))

def audit(original: bytes, translated: bytes, filelist: Path) -> dict:
    ranges = read_ranges(filelist)
    counts: dict[str, int] = {}
    changed_bytes = 0
    runs = 0
    changing = False
    for left, right in zip(original, translated):
        diff = left != right
        if diff:
            changed_bytes += 1
            if not changing:
                runs += 1
        changing = diff
    for begin, end, name in ranges:
        count = changed_in_range(original, translated, begin, end)
        if count:
            counts[name] = counts.get(name, 0) + count
    # Merge ranges so overlapping sub-assets do not double-count coverage.
    merged: list[list[int]] = []
    for begin, end, _ in ranges:
        if merged and begin <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([begin, end])
    covered = sum(changed_in_range(original, translated, b, e) for b, e in merged)
    extra = abs(len(original) - len(translated))
    if extra:
        changed_bytes += extra
        runs += 1
    return {
        'original_sha1': hashlib.sha1(original).hexdigest(),
        'translated_sha1': hashlib.sha1(translated).hexdigest(),
        'same_size': len(original) == len(translated),
        'changed_bytes': changed_bytes,
        'changed_runs': runs,
        'unattributed_bytes': changed_bytes - covered,
        'affected_ranges': dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        'port_compatibility': 'NOT VERIFIED: test upstream asset converters and game',
    }

def main() -> int:
    import argparse
    from nxlab.goldeneye_ptbr import read_source, require_original, MAX_ROM_BYTES
    parser = argparse.ArgumentParser(description='Audit local PT-BR ROM vs clean game')
    parser.add_argument('clean_rom', type=Path)
    parser.add_argument('localized_rom', type=Path)
    parser.add_argument('filelist', type=Path)
    args = parser.parse_args()
    clean = read_source(args.clean_rom, {'.z64'}, MAX_ROM_BYTES)
    require_original(clean)
    localized = read_source(args.localized_rom, {'.z64'}, MAX_ROM_BYTES)
    print(json.dumps(audit(clean, localized, args.filelist), indent=2, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
