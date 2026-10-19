"""Extract a unique STFS payload from .7z/.zip with system libarchive.

Archive-provided member paths are ignored for output. Commercial bytes are
stored only in explicitly chosen private directories, never returned.
"""
from __future__ import annotations
import ctypes as c
import ctypes.util
from pathlib import Path

MAGICS = {b'7z\xbc\xaf\x27\x1c': '7z', b'PK\x03\x04': 'zip'}
MAX_ARCHIVE_SIZE = 2 * 1024**3
MAX_STFS_SIZE = 1024**3
MAX_ENTRIES = 100000
CHUNK = 64 * 1024


class ArchiveError(ValueError):
    pass


def detect(path):
    with Path(path).open('rb') as stream:
        magic = stream.read(6)
    return next((v for k, v in MAGICS.items() if magic.startswith(k)), None)


def _library():
    name = c.util.find_library('archive')
    if not name:
        raise ArchiveError('libarchive unavailable: install a compatible system library')
    lib = c.CDLL(name)
    lib.archive_read_new.restype = c.c_void_p
    lib.archive_read_support_filter_all.argtypes = [c.c_void_p]
    lib.archive_read_support_format_all.argtypes = [c.c_void_p]
    lib.archive_read_open_filename.argtypes = [c.c_void_p, c.c_char_p, c.c_size_t]
    lib.archive_read_next_header.argtypes = [c.c_void_p, c.POINTER(c.c_void_p)]
    lib.archive_entry_filetype.argtypes = [c.c_void_p]
    lib.archive_entry_filetype.restype = c.c_uint
    lib.archive_entry_size.argtypes = [c.c_void_p]
    lib.archive_entry_size.restype = c.c_int64
    lib.archive_read_data.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
    lib.archive_read_data.restype = c.c_ssize_t
    lib.archive_read_free.argtypes = [c.c_void_p]
    return lib


def extract_single_stfs(archive_path, target):
    """Extract one regular LIVE/CON/PIRS entry to a new controlled path."""
    archive_path, target = Path(archive_path), Path(target)
    fmt = detect(archive_path)
    if not fmt:
        raise ArchiveError('Expected 7z or zip signature')
    if archive_path.stat().st_size > MAX_ARCHIVE_SIZE:
        raise ArchiveError('Archive too large')
    if target.exists():
        raise FileExistsError('Refusing to overwrite existing extraction')
    lib = _library()
    reader = lib.archive_read_new()
    if not reader:
        raise ArchiveError('Failed to create archive reader')
    written = False
    files_seen = 0
    total = 0
    matches = 0
    try:
        if lib.archive_read_support_filter_all(reader) < 0 or lib.archive_read_support_format_all(reader) < 0:
            raise ArchiveError('Cannot initialize libarchive')
        if lib.archive_read_open_filename(reader, str(archive_path).encode(), 16384) < 0:
            raise ArchiveError('Cannot open input archive')
        entry = c.c_void_p()
        block = c.create_string_buffer(CHUNK)
        while True:
            ret = lib.archive_read_next_header(reader, c.byref(entry))
            if ret == 1:
                break
            if ret != 0:
                raise ArchiveError('Malformed or unreadable archive entry')
            files_seen += 1
            if files_seen > MAX_ENTRIES:
                raise ArchiveError('Archive entry limit exceeded')
            if lib.archive_entry_filetype(entry) != 0o100000:
                continue
            size = lib.archive_entry_size(entry)
            if size < 4 or size > MAX_STFS_SIZE:
                continue
            first = c.create_string_buffer(4)
            if lib.archive_read_data(reader, first, 4) != 4:
                raise ArchiveError('Truncated archive member')
            if first.raw not in (b'LIVE', b'PIRS', b'CON '):
                continue
            matches += 1
            if matches > 1:
                raise ArchiveError('Multiple STFS entries in archive (ambiguous)')
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open('xb') as output:
                output.write(first.raw)
                copied = 4
                while copied < size:
                    n = lib.archive_read_data(reader, block, min(CHUNK, size-copied))
                    if n <= 0:
                        raise ArchiveError('Truncated STFS member')
                    output.write(block.raw[:n])
                    copied += n
            written = True
            total = size
        if matches != 1 or not written:
            raise ArchiveError('No unique STFS payload in archive')
        target.chmod(0o600)
        return {'format': fmt, 'stfs_bytes': total,
                'archive_entries_scanned': files_seen, 'stfs_candidates': matches}
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    finally:
        lib.archive_read_free(reader)
