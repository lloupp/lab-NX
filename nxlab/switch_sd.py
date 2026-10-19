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


def prepare(xex, sdmc_root):
    original=Path(xex).expanduser().resolve(strict=True)
    root=Path(sdmc_root).expanduser().resolve()
    if not original.is_file() or not root.is_dir():
        raise ValueError("Input XEX must be a file; target sdmc root must exist")
    for path in (original, root):
        if any((parent / ".git").exists() for parent in (path,*path.parents)):
            raise ValueError("Game files must remain outside Git")
    info=inspect(original)
    if info.get("execution",{}).get("title_id")!="584108B7":
        raise ValueError("XEX is not Castle Crashers Title ID 584108B7")
    output=root/"switch"/"labnx"/"castle"/"default.xex"
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
        return {"status":"ready","title_id":"584108B7",
                "destination":str(output),"sha256":digest.hexdigest(),
                "bytes":output.stat().st_size,"game_playable":False}
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description="Copy an authorized Castle Crashers XEX to emulated SD")
    p.add_argument("--xex",type=Path,required=True)
    p.add_argument("--sdmc-root",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        print(json.dumps(prepare(args.xex,args.sdmc_root),indent=2))
        return 0
    except (OSError,ValueError) as err:
        print(f"SD import refused: {err}")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
