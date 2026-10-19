"""GoldenEye 007 (USA) offline IPS translation-patch utility.

ROM and patch remain private to the user. This tool does not ship or download
game code/assets and does not change the game's control scheme.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
import zlib
from pathlib import Path

EXPECTED_SIZE = 12 * 1024 * 1024
EXPECTED_SHA1 = "abe01e4aeb033b6c0836819f549c791b26cfde83"
EXPECTED_CRC32 = 0xB6330846
MAX_ROM_BYTES = 64 * 1024 * 1024
MAX_PATCH_BYTES = 32 * 1024 * 1024

class PatchError(ValueError):
    pass

def read_source(path: Path, extensions: set[str], limit: int) -> bytes:
    if path.suffix.lower() != ".zip":
        if path.suffix.lower() not in extensions or path.stat().st_size > limit:
            raise PatchError("Arquivo ou tamanho nao permitido")
        return path.read_bytes()
    with zipfile.ZipFile(path) as z:
        matches = [i for i in z.infolist() if not i.is_dir()
                   and Path(i.filename).suffix.lower() in extensions]
        if len(matches) != 1:
            raise PatchError("ZIP deve conter exatamente um arquivo de formato valido")
        if matches[0].file_size > limit:
            raise PatchError("Arquivo compactado excede limite")
        with z.open(matches[0]) as fd:
            raw = fd.read(limit + 1)
        if len(raw) > limit:
            raise PatchError("Limite de descompactacao excedido")
        return raw

def rom_info(data: bytes) -> dict:
    sha1 = hashlib.sha1(data).hexdigest()
    crc32 = zlib.crc32(data)
    valid = len(data) == EXPECTED_SIZE and sha1 == EXPECTED_SHA1 and crc32 == EXPECTED_CRC32 and data[:4] == bytes.fromhex("80371240")
    return {"size": len(data), "sha1": sha1, "crc32": f"{crc32:08X}",
            "magic": data[:4].hex().upper(), "goldeneye_usa_original": valid}

def require_original(data: bytes) -> None:
    if not rom_info(data)["goldeneye_usa_original"]:
        raise PatchError("ROM incorreta; esperado GoldenEye N64 USA, CRC32 B6330846")

def apply_ips(rom: bytes, ips: bytes) -> tuple[bytes, int]:
    if not ips.startswith(b"PATCH"):
        raise PatchError("Cabecalho IPS ausente")
    out = bytearray(rom)
    idx = 5
    count = 0
    while True:
        if idx + 3 > len(ips):
            raise PatchError("IPS truncado ou EOF ausente")
        if ips[idx:idx+3] == b"EOF":
            idx += 3
            if len(ips) - idx == 3:
                new_size = int.from_bytes(ips[idx:idx+3], "big")
                if new_size < 0x101000 or new_size > MAX_ROM_BYTES:
                    raise PatchError("Tamanho final IPS invalido")
                if new_size > len(out):
                    out.extend(b"\x00" * (new_size - len(out)))
                else:
                    del out[new_size:]
                idx += 3
            if idx != len(ips):
                raise PatchError("Bytes extras apos EOF")
            return bytes(out), count
        offset = int.from_bytes(ips[idx:idx+3], "big")
        idx += 3
        if idx + 2 > len(ips):
            raise PatchError("IPS truncado no comprimento")
        size = int.from_bytes(ips[idx:idx+2], "big")
        idx += 2
        if size:
            if idx + size > len(ips):
                raise PatchError("IPS truncado no conteudo")
            data = ips[idx:idx+size]
            idx += size
        else:
            if idx + 3 > len(ips):
                raise PatchError("IPS RLE truncado")
            repeat = int.from_bytes(ips[idx:idx+2], "big")
            data = ips[idx+2:idx+3] * repeat
            idx += 3
        end = offset + len(data)
        if end > MAX_ROM_BYTES:
            raise PatchError("IPS ultrapassa limite de ROM")
        if end > len(out):
            out.extend(b"\x00" * (end - len(out)))
        out[offset:end] = data
        count += 1

def calc_n64_crc6102(rom: bytes) -> tuple[int, int]:
    """N64 CIC-6102 CRC1/CRC2 used by original US GoldenEye."""
    if len(rom) < 0x101000:
        raise PatchError("ROM muito pequena")
    boot_crc = zlib.crc32(rom[0x40:0x1000])
    if boot_crc != 0x90BB6CB5:
        raise PatchError(f"Bootcode/CIC inesperado ({boot_crc:08X})")
    mask = 0xFFFFFFFF
    t1 = t2 = t3 = t4 = t5 = t6 = 0xF8CA4DDC
    for off in range(0x1000, 0x101000, 4):
        d = struct.unpack_from(">I", rom, off)[0]
        previous = t6
        t6 = (t6 + d) & mask
        if t6 < previous:
            t4 = (t4 + 1) & mask
        t3 ^= d
        rotate = d & 31
        r = ((d << rotate) | (d >> (32 - rotate))) & mask if rotate else d
        t5 = (t5 + r) & mask
        t2 ^= r if t2 > d else (t6 ^ d)
        t1 = (t1 + (t5 ^ d)) & mask
    return (t6 ^ t4 ^ t3) & mask, (t5 ^ t2 ^ t1) & mask

def repair_header(rom: bytes) -> tuple[bytes, bool]:
    expected = struct.pack(">II", *calc_n64_crc6102(rom))
    return (rom[:0x10] + expected + rom[0x18:], True) if rom[0x10:0x18] != expected else (rom, False)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GoldenEye USA -> PT-BR via patch IPS fornecido pelo usuario")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("rom", type=Path)
    apply = commands.add_parser("apply")
    apply.add_argument("rom", type=Path)
    apply.add_argument("ips", type=Path)
    apply.add_argument("--out", type=Path, required=True)
    apply.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        rom = read_source(args.rom, {".z64"}, MAX_ROM_BYTES)
        info = rom_info(rom)
        if args.command == "inspect":
            print(json.dumps(info, indent=2))
            return 0 if info["goldeneye_usa_original"] else 2
        require_original(rom)
        if args.out.suffix.lower() != ".z64" or args.out.resolve() == args.rom.resolve():
            raise PatchError("Saida deve ser uma nova ROM .z64")
        if args.out.exists() and not args.force:
            raise PatchError("Arquivo de saida existente; use --force somente se necessario")
        patch = read_source(args.ips, {".ips"}, MAX_PATCH_BYTES)
        output, records = apply_ips(rom, patch)
        output, fixed = repair_header(output)
        if output == rom:
            raise PatchError("IPS nao alterou a ROM")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(output)
        print(json.dumps({
            "status": "patch aplicado; nao validado em jogo",
            "records": records, "header_checksum_fixed": fixed,
            "patch_sha256": hashlib.sha256(patch).hexdigest(),
            "output": str(args.out), "output_sha1": hashlib.sha1(output).hexdigest(),
            "tested_on_switch": False
        }, ensure_ascii=False, indent=2))
        return 0
    except (PatchError, OSError, zipfile.BadZipFile) as err:
        print(f"ERRO: {err}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
