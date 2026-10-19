"""Private XEX2 AES/LZX block-chain preflight. Never exports decrypted bytes.

The XEX2 normal-compression layout follows Xenia's xex_module.cc:
one encrypted payload; the compressed block chain contains next-block
size/SHA-1 descriptor and 16-bit BE chunk framing. This tool verifies
block integrity only; it does NOT decompress LZX or execute PowerPC.

No retail/development keys are shipped, stored in reports or hardcoded.
Requires optional dependency: cryptography.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct

class LzxPreflightError(ValueError):
    pass

MAX_XEX = 256 * 1024 * 1024
MAX_BLOCKS = 8192
MAX_IMAGE = 512 * 1024 * 1024
SHA1_LENGTH = 20


def be32(data, offset):
    if offset < 0 or offset + 4 > len(data):
        raise LzxPreflightError("XEX metadata is truncated")
    return struct.unpack_from(">I", data, offset)[0]


def read_local_wrapping_key(path):
    """Read 16-byte key from private file, rejecting symlinks and broad UNIX mode."""
    path = Path(path)
    if path.is_symlink():
        raise LzxPreflightError("Key path must not be a symlink")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode):
        raise LzxPreflightError("Key path must be a regular file")
    if os.name == "posix" and st.st_mode & 0o077:
        raise LzxPreflightError("Private key file must have chmod 600 permissions")
    key = path.read_bytes()
    if len(key) != 16:
        raise LzxPreflightError("Key file must contain exactly 16 raw bytes")
    return key


def _decrypt_normal(blob: bytes, wrapped: bytes, wrapping_key: bytes):
    if len(wrapping_key) != 16 or len(wrapped) != 16:
        raise LzxPreflightError("Invalid AES wrapping key material")
    if len(blob) % 16:
        raise LzxPreflightError("Encrypted XEX image length is not AES aligned")
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as error:
        raise LzxPreflightError("Install optional dependency cryptography") from error
    unwrap = Cipher(algorithms.AES(wrapping_key), modes.ECB()).decryptor()
    session_key = unwrap.update(wrapped) + unwrap.finalize()
    decrypt = Cipher(algorithms.AES(session_key), modes.CBC(b"\0" * 16)).decryptor()
    return decrypt.update(blob) + decrypt.finalize()


def inspect_chain(data: bytes, first_size: int, first_digest: bytes):
    """Validate normal-compression block boundaries and every SHA-1 digest.

    Returns safe counts only; never serializes game bytes or decoded data.
    SHA-1 is a *format checksum*, not proof of publisher authenticity.
    """
    if first_size < 26 or len(first_digest) != SHA1_LENGTH:
        raise LzxPreflightError("Invalid first LZX block descriptor")
    at, size, digest = 0, first_size, first_digest
    blocks = 0
    chunks = 0
    stream_bytes = 0
    while size:
        if blocks >= MAX_BLOCKS:
            raise LzxPreflightError("Too many LZX blocks")
        if size < 26 or at + size > len(data):
            raise LzxPreflightError("LZX block exceeds payload")
        block = memoryview(data)[at:at+size]
        if hashlib.sha1(block).digest() != digest:
            raise LzxPreflightError("LZX block SHA-1 mismatch")
        next_size = int.from_bytes(block[:4], "big")
        next_digest = bytes(block[4:24])
        if next_size and (next_size < 26 or at + size + next_size > len(data)):
            raise LzxPreflightError("Invalid next block descriptor")
        pos = 24
        while True:
            if pos + 2 > len(block):
                raise LzxPreflightError("Truncated LZX chunk length")
            length = int.from_bytes(block[pos:pos+2], "big")
            pos += 2
            if length == 0:
                break
            if pos + length > len(block):
                raise LzxPreflightError("LZX chunk exceeds block")
            pos += length
            chunks += 1
            stream_bytes += length
        if pos > len(block):
            raise LzxPreflightError("Invalid LZX framing")
        at += size
        blocks += 1
        size, digest = next_size, next_digest
    if at != len(data):
        raise LzxPreflightError("Unaccounted XEX payload bytes")
    return {
        "lzx_blocks_verified": blocks,
        "lzx_chunks": chunks,
        "lzx_compressed_stream_bytes": stream_bytes,
        "payload_bytes_verified": at,
        "all_block_sha1_matched": True,
        "image_decompressed": False,
        "powerpc_executed": False,
    }


def inspect_xex(path, wrapping_key=None):
    path = Path(path)
    if path.stat().st_size > MAX_XEX:
        raise LzxPreflightError("XEX file size exceeds limit")
    data = path.read_bytes()
    if len(data) < 24 or data[:4] != b"XEX2":
        raise LzxPreflightError("Expected XEX2")
    payload_offset, security_offset, count = (be32(data,8), be32(data,16), be32(data,20))
    if count > 1024 or 24 + count * 8 > len(data):
        raise LzxPreflightError("Invalid optional header count")
    if payload_offset >= len(data) or payload_offset < 24 + count * 8:
        raise LzxPreflightError("Invalid payload offset")
    if security_offset < 24 + count * 8 or security_offset+0x160 > payload_offset:
        raise LzxPreflightError("Invalid security offset")
    options = {}
    for i in range(count):
        key, value = struct.unpack_from(">II", data, 24 + i * 8)
        if key in options:
            raise LzxPreflightError("Duplicate optional header")
        options[key] = value
    if 0x3FF not in options:
        raise LzxPreflightError("Missing file format information")
    fmt = options[0x3FF]
    if fmt < 24+count*8 or fmt+36 > payload_offset or be32(data,fmt) < 36:
        raise LzxPreflightError("Invalid LZX file format information")
    enc, comp = struct.unpack_from(">HH", data,fmt+4)
    if comp != 2 or enc not in (0, 1):
        raise LzxPreflightError("Requires XEX2 normal LZX compression, encryption 0 or 1")
    image_size = be32(data,security_offset+4)
    if not 0 < image_size <= MAX_IMAGE:
        raise LzxPreflightError("Invalid declared decoded image size")
    window = be32(data,fmt+8)
    if window < 32768 or window > 2097152 or window & (window-1):
        raise LzxPreflightError("Unsupported LZX window size")
    initial_size = be32(data,fmt+12)
    initial_digest = data[fmt+16:fmt+36]
    payload = data[payload_offset:]
    if enc == 1:
        if wrapping_key is None:
            raise LzxPreflightError("Encrypted XEX needs a locally supplied AES key file")
        payload = _decrypt_normal(
            payload, data[security_offset+0x150:security_offset+0x160], wrapping_key)
    result = inspect_chain(payload, initial_size, initial_digest)
    return {"format":"XEX2", "declared_image_bytes":image_size,
            "lzx_window_bytes":window, "encryption_type":enc,
            **result}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify XEX2 AES/LZX block integrity privately")
    parser.add_argument("xex", type=Path)
    parser.add_argument("--wrapping-key-file", type=Path,
                        help="Local private file with 16 raw key bytes; never included in output")
    parser.add_argument("--report", type=Path,
                        help="Write metadata-only report to a new private file")
    args = parser.parse_args(argv)
    try:
        key = read_local_wrapping_key(args.wrapping_key_file) if args.wrapping_key_file else None
        result = inspect_xex(args.xex, key)
        if args.report:
            out = args.report.resolve()
            if any((parent / ".git").exists() for parent in (out.parent,*out.parents)):
                raise LzxPreflightError("Report must be outside any Git checkout")
            out.parent.mkdir(parents=True,exist_ok=True)
            with out.open("x",encoding="utf-8") as stream:
                json.dump(result,stream,indent=2)
                stream.write("\n")
        print(json.dumps(result,indent=2))
        return 0
    except (OSError,LzxPreflightError) as error:
        print("XEX LZX preflight failed:",error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
