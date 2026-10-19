"""Read-only inventory and selected extraction of Xbox 360 STFS packages.

M1 supports the validated LIVE block layout and contiguous entries. It does
not decrypt XEX binaries, verify signatures or extract fragmented chains.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import Counter
from pathlib import Path, PurePosixPath
import hashlib

BLOCK = 4096

class StfsError(ValueError):
    pass

@dataclass(frozen=True)
class Entry:
    id: int
    name: str
    path: str
    is_directory: bool
    contiguous: bool
    start_block: int
    block_count: int
    byte_count: int
    parent_id: int

def offset(block: int, start: int, step: int) -> int:
    if block < 0 or block >= 0xffffff:
        raise StfsError("Invalid logical block number")
    q, overhead = block, 0
    while q >= 170:
        q //= 170
        overhead += (q + 1) * step
    return start + block * BLOCK + overhead

def read_at(f, at: int, count: int, size: int) -> bytes:
    if at < 0 or count < 0 or at + count > size:
        raise StfsError("STFS read out of bounds")
    f.seek(at)
    data = f.read(count)
    if len(data) != count:
        raise StfsError("Truncated STFS package")
    return data

class Package:
    def __init__(self, path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        with self.path.open('rb') as f:
            h = read_at(f, 0, 0xc000, self.size)
        if h[:4] not in (b'LIVE', b'PIRS', b'CON '):
            raise StfsError("Expected STFS magic LIVE, PIRS or CON")
        d = h[0x379:0x39d]
        if d[0] != 0x24:
            raise StfsError("Unsupported volume descriptor")
        self.table_blocks = int.from_bytes(d[3:5], 'little')
        self.table_start = int.from_bytes(d[5:8], 'little')
        if not 0 < self.table_blocks <= 10000:
            raise StfsError("Invalid file table block count")
        # Castle Crashers LIVE observed blockSeparation=1, start=C000.
        # Other package layouts need independent validation.
        self.data_start = 0xc000 if d[2] & 1 else 0xd000
        self.step = 0x1000 if d[2] & 1 else 0x2000
        self.header = {
            'magic': h[:4].decode('ascii'),
            'content_type': h[0x344:0x348].hex().upper(),
            'title_id': h[0x360:0x364].hex().upper(),
            'size_bytes': self.size,
            'table_start_block': self.table_start,
            'table_block_count': self.table_blocks,
            'block_separation': d[2],
        }
        self.entries = self._inventory()

    def _inventory(self):
        with self.path.open('rb') as f:
            raw = b''.join(read_at(f, offset(self.table_start+i, self.data_start, self.step),
                                   BLOCK, self.size) for i in range(self.table_blocks))
        parents = {0xffff: ''}
        entries = []
        for at in range(0, len(raw), 64):
            e = raw[at:at+64]
            n = e[40] & 63
            if n == 0:
                break
            if n > 40:
                raise StfsError('Invalid STFS name length')
            name = e[:n].decode('ascii', 'replace')
            if not name or name in ('.', '..') or '/' in name or '\\' in name:
                raise StfsError('Unsafe entry name')
            parent = int.from_bytes(e[50:52], 'big')
            if parent not in parents:
                raise StfsError('Invalid file table parent')
            directory = bool(e[40] & 0x80)
            path = parents[parent] + name
            index = at // 64
            if directory:
                parents[index] = path + '/'
            blocks = int.from_bytes(e[41:44], 'little')
            size = 0 if directory else int.from_bytes(e[52:56], 'big')
            if size > blocks * BLOCK:
                raise StfsError('Declared file exceeds allocated size')
            entries.append(Entry(index, name, path + ('/' if directory else ''),
                                 directory, bool(e[40] & 0x40),
                                 int.from_bytes(e[47:50], 'little'), blocks, size, parent))
        if not entries:
            raise StfsError('Empty file table')
        return entries

    def inventory(self):
        files = [e for e in self.entries if not e.is_directory]
        ext = Counter(PurePosixPath(e.name).suffix.lower() or '(none)' for e in files)
        return {
            'format': 'STFS', 'header': self.header,
            'entries_total': len(self.entries), 'files': len(files),
            'directories': len(self.entries) - len(files),
            'file_bytes': sum(e.byte_count for e in files),
            'extensions': dict(sorted(ext.items())),
            'executables': [asdict(e) for e in files if e.name.lower().endswith('.xex')],
        }

    def extract_xex(self, out, name='default.xex'):
        found = [e for e in self.entries if not e.is_directory and
                 (e.name.lower() == name.lower() or e.path.lower() == name.lower())]
        if len(found) != 1 or not found[0].name.lower().endswith('.xex'):
            raise StfsError('Expected exactly one named .xex file')
        e = found[0]
        if not e.contiguous:
            raise StfsError('Fragmented entry: extraction not implemented')
        dest = Path(out)
        if dest.exists():
            raise FileExistsError('Refusing to overwrite an existing XEX')
        dest.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        remaining = e.byte_count
        try:
            with self.path.open('rb') as src, dest.open('xb') as dst:
                for i in range(e.block_count):
                    if remaining == 0:
                        break
                    at = offset(e.start_block+i, self.data_start, self.step)
                    chunk = read_at(src, at, min(BLOCK,remaining),self.size)
                    h.update(chunk)
                    dst.write(chunk)
                    remaining -= len(chunk)
            if remaining:
                raise StfsError('Short extraction')
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        with dest.open('rb') as f:
            magic = f.read(4).decode('ascii','replace')
        return {'bytes':e.byte_count, 'sha256':h.hexdigest(), 'magic':magic}
