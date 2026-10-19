"""Create a PRIVATE ELF32/PowerPC analysis wrapper for an Xbox PE .text section.

This is for disassembly and investigation only. It is not a playable port
or a full PE loader and never embeds a game binary into the public repo.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import struct
from .xex_lzx_preflight import LzxPreflightError


def wrap_text(pe_path, elf_path):
    src=Path(pe_path)
    dest=Path(elf_path).expanduser().resolve()
    if dest.exists():
        raise FileExistsError("Refusing to overwrite existing ELF")
    if any((p/".git").exists() for p in (dest.parent,*dest.parents)):
        raise LzxPreflightError("Analysis ELF must stay outside Git")
    data=src.read_bytes()
    if len(data)<512 or data[:2]!=b"MZ":
        raise LzxPreflightError("Not a PE image")
    nt=struct.unpack_from("<I",data,0x3C)[0]
    if nt<64 or nt+24>len(data) or data[nt:nt+4]!=b"PE\0\0":
        raise LzxPreflightError("Invalid PE header")
    machine,section_count=struct.unpack_from("<HH",data,nt+4)
    size_opt=struct.unpack_from("<H",data,nt+20)[0]
    opt=nt+24
    if (machine!=0x01F2 or not 1<=section_count<=64 or
            opt+size_opt+40*section_count>len(data) or size_opt<72):
        raise LzxPreflightError("Expected Xbox PowerPC PE with sections")
    base=struct.unpack_from("<I",data,opt+28)[0]
    entry_rva=struct.unpack_from("<I",data,opt+16)[0]
    section=None
    for i in range(section_count):
        at=opt+size_opt+i*40
        name,virt_sz,rva,raw_sz,raw_off,_,_,_,_,flags=struct.unpack_from(
            "<8sIIIIIIHHI",data,at)
        if name.rstrip(b"\0")==b".text" and flags & 0x20000000:
            if section is not None:
                raise LzxPreflightError("Ambiguous executable .text sections")
            if not raw_sz or raw_off+raw_sz>len(data):
                raise LzxPreflightError("Invalid .text file range")
            if not rva<=entry_rva<rva+max(virt_sz,raw_sz):
                raise LzxPreflightError("Game entry point outside .text")
            section=(base+rva,data[raw_off:raw_off+raw_sz])
    if section is None:
        raise LzxPreflightError("Executable .text section missing")
    addr,raw=section
    names=b"\0.text\0.shstrtab\0"
    text_off=0x100
    names_off=text_off+len(raw)
    sh_off=(names_off+len(names)+3)&~3
    ident=b"\x7fELF\x01\x02\x01"+bytes(9)
    eh=struct.pack(">16sHHIIIIIHHHHHH",ident,2,20,1,base+entry_rva,
                   0,sh_off,0,52,0,0,40,3,2)
    sh=[
        bytes(40),
        struct.pack(">IIIIIIIIII",1,1,6,addr,text_off,len(raw),0,0,4,0),
        struct.pack(">IIIIIIIIII",7,3,0,0,names_off,len(names),0,0,1,0),
    ]
    dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    try:
        with dest.open("xb") as out:
            out.write(eh.ljust(text_off,b"\0"))
            out.write(raw)
            out.write(names)
            out.write(bytes(sh_off-names_off-len(names)))
            out.write(b"".join(sh))
        dest.chmod(0o600)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return {
        "format":"ELF32 PowerPC big-endian",
        "text_virtual_address":f"0x{addr:08X}",
        "text_bytes":len(raw),
        "entry_point":f"0x{base+entry_rva:08X}",
        "generated_privately":True,
        "code_recompiled":False,
        "code_executed":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Wrap Xbox PowerPC PE code in private ELF")
    p.add_argument("pe",type=Path)
    p.add_argument("elf",type=Path)
    args=p.parse_args(argv)
    try:
        print(json.dumps(wrap_text(args.pe,args.elf),indent=2))
        return 0
    except (OSError,LzxPreflightError) as e:
        print("PE-to-ELF analysis failed:",e)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
