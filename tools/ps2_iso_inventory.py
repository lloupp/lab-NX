#!/usr/bin/env python3
"""Non-extracting ISO 9660 / PS2 inventory; emits metadata only.

Usage: python tools/ps2_iso_inventory.py /private/path/game.iso --json
No game or asset bytes are copied into the output.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

SECTOR = 2048
BOOT_RE = re.compile(rb"(?im)^\s*BOOT2?\s*=\s*cdrom0:\\([^;\r\n]+)")


class InvalidISO(ValueError):
    pass


def parse_record(buf):
    if not buf or len(buf) < 34 or buf[0] < 34 or buf[0] > len(buf):
        raise InvalidISO("invalid ISO9660 directory record")
    extent = int.from_bytes(buf[2:6], "little")
    length = int.from_bytes(buf[10:14], "little")
    n = buf[32]
    if n < 1 or 33 + n > buf[0]:
        raise InvalidISO("invalid directory entry name")
    name = buf[33:33 + n].decode("ascii", "replace")
    return {"name": name.split(";")[0], "extent": extent,
            "bytes": length, "directory": bool(buf[25] & 2)}


def inventory(path, hash_iso=False):
    path = Path(path)
    size = path.stat().st_size
    if size < 18 * SECTOR or size % SECTOR:
        raise InvalidISO("file is not a sector-aligned ISO image")

    with path.open("rb") as source:
        source.seek(16 * SECTOR)
        pvd = source.read(SECTOR)
        if pvd[:7] != b"\x01CD001\x01":
            raise InvalidISO("missing ISO9660 primary volume descriptor")
        root_len = pvd[156]
        root = parse_record(pvd[156:156 + root_len])
        if not root["directory"]:
            raise InvalidISO("root is not a directory")
        entries = []
        visited = set()

        def read_extent(item, max_bytes=None):
            start = item["extent"] * SECTOR
            length = item["bytes"] if max_bytes is None else min(item["bytes"], max_bytes)
            if start > size or item["bytes"] > size - start:
                raise InvalidISO("directory entry outside ISO")
            source.seek(start)
            return source.read(length)

        def visit(item, parent, depth):
            if depth > 20 or len(entries) > 200000:
                raise InvalidISO("directory nesting / entry limit exceeded")
            where = (item["extent"], item["bytes"])
            if where in visited:
                return
            visited.add(where)
            if item["bytes"] > 128 * 1024 * 1024:
                raise InvalidISO("directory too large")
            data = read_extent(item)
            offset = 0
            while offset < len(data):
                rec_size = data[offset]
                if rec_size == 0:
                    offset = ((offset // SECTOR) + 1) * SECTOR
                    continue
                if offset + rec_size > len(data) or rec_size > SECTOR - offset % SECTOR:
                    raise InvalidISO("directory record exceeds sector")
                rec = parse_record(data[offset:offset + rec_size]); offset += rec_size
                if rec["name"] in ("\x00", "\x01", ".", ".."):
                    continue
                if "/" in rec["name"] or "\\" in rec["name"]:
                    raise InvalidISO("invalid path component")
                rec["path"] = parent + "/" + rec["name"]
                if rec["extent"] * SECTOR > size or rec["bytes"] > size - rec["extent"] * SECTOR:
                    raise InvalidISO("file extends past ISO image")
                entries.append(rec)
                if rec["directory"]:
                    visit(rec, rec["path"], depth + 1)

        visit(root, "", 0)
        files = {e["path"].upper(): e for e in entries if not e["directory"]}
        system = files.get("/SYSTEM.CNF")
        if not system:
            raise InvalidISO("PS2 SYSTEM.CNF not found")
        match = BOOT_RE.search(read_extent(system, 4096))
        if not match:
            raise InvalidISO("BOOT2 executable not identified")
        boot_name = match.group(1).decode("ascii", "replace").upper()
        boot = files.get("/" + boot_name)
        if boot is None:
            raise InvalidISO("boot executable is absent")
        head = read_extent(boot, 52)
        if (len(head) < 52 or head[:4] != b"\x7fELF" or
                head[4] != 1 or head[5] != 1 or
                struct.unpack_from("<H", head, 18)[0] != 8):
            raise InvalidISO("boot executable is not a 32-bit little-endian MIPS ELF")
        elf_entry = struct.unpack_from("<I", head, 24)[0]
        digest = hashlib.sha256()
        source.seek(boot["extent"] * SECTOR)
        remaining = boot["bytes"]
        while remaining:
            chunk = source.read(min(1048576, remaining))
            if not chunk:
                raise InvalidISO("short boot ELF read")
            digest.update(chunk); remaining -= len(chunk)
        required = ["/KERNEL.XFF", "/MANAGER.XFF", "/GAMECORE.XFF", "/NICO.DAT"]
        missing = [name for name in required if name not in files]
        report = {
            "format": "iso9660/ps2", "iso_bytes": size,
            "volume_id": pvd[40:72].decode("ascii", "replace").strip(),
            "boot": boot_name, "boot_bytes": boot["bytes"],
            "boot_sha256": digest.hexdigest(), "elf_machine": "MIPS",
            "elf_entry": f"0x{elf_entry:08x}",
            "serial": boot_name.replace("_", "-").replace(".", ""),
            "expected_modules_present": not missing,
            "missing_required": missing,
            "files": [{"path": item["path"], "bytes": item["bytes"], "directory": item["directory"]}
                      for item in entries],
        }
        if hash_iso:
            digest = hashlib.sha256()
            source.seek(0)
            for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
            report["iso_sha256"] = digest.hexdigest()
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path, help="private disc image; never commit")
    parser.add_argument("--json", action="store_true", help="machine-readable metadata")
    parser.add_argument("--hash-iso", action="store_true", help="also compute full-disc SHA256")
    args = parser.parse_args()
    try:
        result = inventory(args.iso, hash_iso=args.hash_iso)
    except (InvalidISO, OSError) as exc:
        parser.exit(2, f"invalid source: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else
          f"PS2 {result['serial']} | ELF {result['elf_entry']} | "
          f"{result['iso_bytes']} bytes | modules: "
          f"{'complete' if result['expected_modules_present'] else 'incomplete'}")


if __name__ == "__main__":
    main()
