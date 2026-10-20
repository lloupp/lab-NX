"""Map verified private Xbox PowerPC XEX imports to ordinals and optional Xenia names.

No code, keys, dumps or private paths are placed in the inventory JSON.
The XEX import table contains both data descriptors and executable thunks;
the decoded PE section flags distinguish them. Decoded XEX inputs are
mapped memory images and their import descriptors live at RVA offsets.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import struct

class ImportAnalysisError(ValueError):
    pass


def be32(data,at):
    if at<0 or at+4>len(data):
        raise ImportAnalysisError("Out-of-bounds XEX value")
    return struct.unpack_from(">I",data,at)[0]


def be16(data,at):
    if at<0 or at+2>len(data):
        raise ImportAnalysisError("Out-of-bounds XEX value")
    return struct.unpack_from(">H",data,at)[0]


def pe_mapping(pe):
    if len(pe)<512 or pe[:2]!=b"MZ":
        raise ImportAnalysisError("Missing MZ signature")
    nt=struct.unpack_from("<I",pe,0x3C)[0]
    if nt<64 or nt+24>len(pe) or pe[nt:nt+4]!=b"PE\0\0":
        raise ImportAnalysisError("Invalid PE signature")
    count=struct.unpack_from("<H",pe,nt+6)[0]
    optsize=struct.unpack_from("<H",pe,nt+20)[0]
    opt=nt+24
    if (not 1<=count<=64 or opt+optsize+count*40>len(pe)
            or struct.unpack_from("<H",pe,nt+4)[0]!=0x01F2):
        raise ImportAnalysisError("Expected Xbox PowerPC PE")
    base=struct.unpack_from("<I",pe,opt+28)[0]
    sections=[]
    for i in range(count):
        at=opt+optsize+i*40
        name,_,rva,raw_size,raw_offset,_,_,_,_,flags=struct.unpack_from(
            "<8sIIIIIIHHI",pe,at)
        if rva+raw_size>len(pe):
            raise ImportAnalysisError("PE section outside file")
        sections.append((name.rstrip(b"\0").decode("latin-1"),
                         rva,raw_size,rva,bool(flags&0x20000000)))
    return base,sections


def slot_value(pe,base,sections,addr):
    rva=addr-base
    for name,va,size,offset,executable in sections:
        if va<=rva<va+size and rva-va+4<=size:
            return name,executable,be32(pe,offset+rva-va)
    raise ImportAnalysisError("Import address cannot be mapped to PE data")


def parse_export_table(text):
    """Parse optional public Xenia .inc export tables supplied by the operator."""
    result={}
    for ordinal,name,kind in re.findall(
            r"XE_EXPORT\(\w+,\s*0x([0-9a-fA-F]+),\s*(\w+),\s*k(\w+)\)",text):
        result[int(ordinal,16)]={"name":name,"type":kind}
    return result


def inspect(xex_path,pe_path,export_tables=None):
    xex=Path(xex_path).read_bytes()
    pe=Path(pe_path).read_bytes()
    if (len(xex)<24 or xex[:4]!=b"XEX2" or be32(xex,20)>1024
            or 24+be32(xex,20)*8>len(xex)):
        raise ImportAnalysisError("Expected bounded XEX2 optional headers")
    headers={be32(xex,24+i*8):be32(xex,28+i*8)
             for i in range(be32(xex,20))}
    if 0x103FF not in headers:
        raise ImportAnalysisError("XEX import directory missing")
    start=headers[0x103FF]
    size=be32(xex,start)
    end=start+size
    if size<12 or end>len(xex) or end>be32(xex,8):
        raise ImportAnalysisError("Invalid XEX import directory")
    names_size=be32(xex,start+4)
    name_count=be32(xex,start+8)
    if names_size>size-12 or name_count>256:
        raise ImportAnalysisError("Invalid XEX import name table")
    try:
        names=[name.decode("ascii") for name in
               xex[start+12:start+12+names_size].split(b"\0") if name]
    except UnicodeError as error:
        raise ImportAnalysisError("Invalid library name encoding") from error
    if len(names)!=name_count:
        raise ImportAnalysisError("XEX import library count mismatch")
    base,sections=pe_mapping(pe)
    libraries=[]
    pos=start+12+names_size
    while pos<end:
        entry_size=be32(xex,pos)
        if entry_size==0:
            if xex[pos:end].strip(b"\0"):
                raise ImportAnalysisError("Non-zero directory padding")
            break
        if entry_size<40 or pos+entry_size>end:
            raise ImportAnalysisError("Invalid library entry size")
        index,count=be16(xex,pos+36),be16(xex,pos+38)
        if index>=len(names) or 40+count*4>entry_size:
            raise ImportAnalysisError("Invalid library name index or slot count")
        name=names[index]
        table=(export_tables or {}).get(name,{})
        symbols={}
        thunks=0
        for i in range(count):
            addr=be32(xex,pos+40+i*4)
            section,executable,value=slot_value(pe,base,sections,addr)
            if executable:
                thunks+=1
                continue
            if value>>24:
                raise ImportAnalysisError("Unexpected data descriptor type")
            ordinal=value&0xFFFF
            metadata=table.get(ordinal,{})
            symbols[ordinal]={"ordinal":ordinal,
                              "name":metadata.get("name"),
                              "type":metadata.get("type")}
        ordered=[symbols[k] for k in sorted(symbols)]
        libraries.append({
            "library":name, "import_slots":count,
            "unique_ordinals":len(ordered),
            "descriptor_slots":count-thunks,"thunk_slots":thunks,
            "names_resolved":sum(bool(r["name"]) for r in ordered),
            "symbols":ordered,
        })
        pos+=entry_size
    return {
        "format":"XEX2 imports mapped into Xbox PowerPC PE",
        "libraries":libraries,
        "total_slots":sum(lib["import_slots"] for lib in libraries),
        "unique_ordinal_symbols":sum(lib["unique_ordinals"] for lib in libraries),
        "original_game_code_executed":False,
        "includes_game_bytes":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Inspect Xbox XEX runtime imports privately")
    p.add_argument("xex",type=Path)
    p.add_argument("pe",type=Path)
    p.add_argument("--xam-table",type=Path)
    p.add_argument("--kernel-table",type=Path)
    p.add_argument("--report",type=Path)
    args=p.parse_args(argv)
    try:
        tables={}
        for name,path in (("xam.xex",args.xam_table),
                          ("xboxkrnl.exe",args.kernel_table)):
            if path:
                tables[name]=parse_export_table(path.read_text(encoding="utf-8"))
        result=inspect(args.xex,args.pe,tables)
        text=json.dumps(result,indent=2)+"\n"
        if args.report:
            out=args.report.expanduser().resolve()
            if any((q/".git").exists() for q in (out.parent,*out.parents)):
                raise ImportAnalysisError("Report must be outside Git checkout")
            out.parent.mkdir(parents=True,exist_ok=True)
            with out.open("x",encoding="utf-8") as file:
                file.write(text)
        print(text)
        return 0
    except (OSError,ImportAnalysisError) as error:
        print("Xbox import analysis failed:",error)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
