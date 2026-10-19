"""Prepare an isolated emulated Switch SD card from the user's OWN XEX.

The copied commercial XEX stays outside Git and is never included in CI or
release artifacts. This does not make the Xbox game run on Switch.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from .m2 import inspect


# Exact SHA-256 of the privately recovered, authorized Castle Crashers PE.
# This is metadata only; game bytes and key material are never embedded.
CASTLE_PPC_PE_SHA256 = "964aa6b9d993beb8ad9a986d0555e47c36b4b5716b0b8377c6631ae8b39c03ab"
CASTLE_PPC_PE_BYTES = 2_949_120


def sha256_file(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


def prepare(xex, sdmc_root, decoded_pe=None):
    original=Path(xex).expanduser().resolve(strict=True)
    root=Path(sdmc_root).expanduser().resolve()
    if not original.is_file() or not root.is_dir():
        raise ValueError("Input XEX must be a file; target sdmc root must exist")
    for path in (original, root):
        if any((parent / ".git").exists() for parent in (path,*path.parents)):
            raise ValueError("Game files must remain outside Git")
    info=inspect(original)
    if (info.get("execution") or {}).get("title_id")!="584108B7":
        raise ValueError("XEX is not Castle Crashers Title ID 584108B7")
    decoded = None
    if decoded_pe is not None:
        decoded = Path(decoded_pe).expanduser().resolve(strict=True)
        if any((directory / ".git").exists() for directory in
               (decoded.parent, *decoded.parents)):
            raise ValueError("Private decoded PE must stay outside Git")
        if (not decoded.is_file() or decoded.stat().st_size != CASTLE_PPC_PE_BYTES
                or sha256_file(decoded) != CASTLE_PPC_PE_SHA256):
            raise ValueError("Decoded PE does not match the verified original Castle Crashers image")
    output=root/"switch"/"labnx"/"castle"/"default.xex"
    guest_output=output.parent/"decoded-powerpc.bin"
    if decoded is not None and (guest_output.exists() or guest_output.is_symlink()):
        raise FileExistsError("Never overwrite decoded PE on SD card")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Never overwrite existing XEX on SD card")
    output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    digest=hashlib.sha256()
    try:
        with original.open("rb") as data, output.open("xb") as target:
            target.chmod(0o600)
            for block in iter(lambda:data.read(65536),b""):
                target.write(block)
                digest.update(block)
        if decoded is not None:
            with decoded.open("rb") as data, guest_output.open("xb") as target:
                target.chmod(0o600)
                shutil.copyfileobj(data, target, 65536)
        return {"status":"ready","title_id":"584108B7",
                "guest_pe_verified":decoded is not None,
                "destination":str(output),"sha256":digest.hexdigest(),
                "bytes":output.stat().st_size,"game_playable":False}
    except BaseException:
        output.unlink(missing_ok=True)
        if decoded is not None:
            guest_output.unlink(missing_ok=True)
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description="Copy an authorized Castle Crashers XEX to emulated SD")
    p.add_argument("--xex",type=Path,required=True)
    p.add_argument("--sdmc-root",type=Path,required=True)
    p.add_argument("--decoded-pe",type=Path,help="Private verified decoded Castle PPC PE")
    args=p.parse_args(argv)
    try:
        print(json.dumps(prepare(args.xex,args.sdmc_root,args.decoded_pe),indent=2))
        return 0
    except (OSError,ValueError) as err:
        print(f"SD import refused: {err}")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
