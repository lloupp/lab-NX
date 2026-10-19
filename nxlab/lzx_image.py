"""Recover an authorized XEX2 LZX image into a PRIVATE Xbox PowerPC PE file.

Reusable method: XEX2 AES preflight + SHA-1 block chain + in-memory CAB
wrapper for the system libarchive LZX decoder. No key, assets, or executable
output is bundled with lab-NX. Does not execute PPC or create a Switch NRO.
"""
from __future__ import annotations
import argparse
import ctypes as c
import ctypes.util
import hashlib
import json
import math
from pathlib import Path
import struct

from .xex_lzx_preflight import (
    inspect_xex, _decrypt_normal, be32, LzxPreflightError, read_local_wrapping_key
)

FRAME = 32768
MAX_CAB_BYTES = 128 * 1024 * 1024


def verified_lzx_chunks(path, key):
    meta = inspect_xex(path, key)  # Validates every block hash and boundary.
    raw = Path(path).read_bytes()
    opts = dict(struct.unpack_from(">II", raw, 24+i*8) for i in range(be32(raw,20)))
    ff, sec = opts[0x3FF], be32(raw,16)
    encrypted = raw[be32(raw,8):]
    plain = (_decrypt_normal(encrypted,raw[sec+0x150:sec+0x160],key)
             if meta["encryption_type"] == 1 else encrypted)
    size = be32(raw,ff+12)
    digest = raw[ff+16:ff+36]
    pos = 0
    chunks = []
    while size:
        block = memoryview(plain)[pos:pos+size]
        if hashlib.sha1(block).digest() != digest:
            raise LzxPreflightError("LZX block checksum changed")
        next_size, next_digest = int.from_bytes(block[:4],"big"), bytes(block[4:24])
        at = 24
        while True:
            chunk_size = int.from_bytes(block[at:at+2],"big")
            at += 2
            if not chunk_size:
                break
            chunks.append(bytes(block[at:at+chunk_size]))
            at += chunk_size
        pos += size
        size, digest = next_size, next_digest
    image_size = meta["declared_image_bytes"]
    if len(chunks) != math.ceil(image_size/FRAME):
        raise LzxPreflightError("LZX frame count does not match image size")
    return chunks, image_size, meta["lzx_window_bytes"], opts.get(0x10201), opts.get(0x10100)


def make_cab(chunks, image_size, window):
    """An in-memory CAB with one 32 KiB-output CFDATA entry per XEX LZX chunk."""
    if not chunks or len(chunks)>65535 or not 0 < image_size<=512*1024*1024:
        raise LzxPreflightError("Invalid CAB geometry")
    if window<32768 or window>2097152 or (window & (window-1)):
        raise LzxPreflightError("Unsupported LZX window")
    if len(chunks)!=math.ceil(image_size/FRAME):
        raise LzxPreflightError("Wrong LZX frame count")
    name=b"image.pe\0"
    data=bytearray()
    for i,chunk in enumerate(chunks):
        if not 0 < len(chunk) <=65535:
            raise LzxPreflightError("Invalid compressed frame size")
        decompressed=min(FRAME,image_size-i*FRAME)
        data+=struct.pack("<IHH",0,len(chunk),decompressed)+chunk
        if len(data)>MAX_CAB_BYTES:
            raise LzxPreflightError("CAB exceeds memory limit")
    start=36+8+16+len(name)
    size=start+len(data)
    header=(struct.pack("<4sIIIII",b"MSCF",0,size,0,44,0)+
            struct.pack("<BBHHHHH",3,1,1,1,0,0,0))
    folder=struct.pack("<IHH",start,len(chunks),((window.bit_length()-1)<<8)|3)
    entry=struct.pack("<IIHHHH",image_size,0,0,0,0,0x20)+name
    cab=header+folder+entry+data
    if len(cab)!=size:
        raise LzxPreflightError("Internal CAB size mismatch")
    return cab


def _libarchive():
    name=c.util.find_library("archive")
    if not name:
        raise LzxPreflightError("System libarchive not available")
    lib=c.CDLL(name)
    lib.archive_read_new.restype=c.c_void_p
    lib.archive_read_support_format_all.argtypes=[c.c_void_p]
    lib.archive_read_support_filter_all.argtypes=[c.c_void_p]
    lib.archive_read_open_memory.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t]
    lib.archive_read_next_header.argtypes=[c.c_void_p,c.POINTER(c.c_void_p)]
    lib.archive_entry_size.argtypes=[c.c_void_p]
    lib.archive_entry_size.restype=c.c_int64
    lib.archive_read_data.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t]
    lib.archive_read_data.restype=c.c_ssize_t
    lib.archive_read_free.argtypes=[c.c_void_p]
    return lib


def validate_xbox_pe(path, image_size, base_expected=None, entry_expected=None):
    with Path(path).open("rb") as f:
        data=f.read(8192)
    if len(data)<512 or data[:2]!=b"MZ":
        raise LzxPreflightError("Decoded image missing MZ signature")
    pe=struct.unpack_from("<I",data,0x3C)[0]
    if pe<64 or pe+24>len(data) or data[pe:pe+4]!=b"PE\0\0":
        raise LzxPreflightError("Decoded image missing PE signature")
    machine, count=struct.unpack_from("<HH",data,pe+4)
    opt_size=struct.unpack_from("<H",data,pe+20)[0]
    opt=pe+24
    if machine!=0x01F2 or not 1<=count<=64 or opt+opt_size>len(data):
        raise LzxPreflightError("Expected Xbox PowerPC PE executable")
    if struct.unpack_from("<H",data,opt)[0]!=0x10B:
        raise LzxPreflightError("Expected PE32 optional header")
    rva=struct.unpack_from("<I",data,opt+16)[0]
    base=struct.unpack_from("<I",data,opt+28)[0]
    subsystem=struct.unpack_from("<H",data,opt+68)[0]
    if (subsystem!=14 or (base_expected is not None and base!=base_expected) or
            (entry_expected is not None and base+rva!=entry_expected)):
        raise LzxPreflightError("Xbox PE address or subsystem mismatch")
    return {"image_bytes": image_size, "machine": "PowerPC BE (0x01F2)",
            "pe_sections": count, "image_base": f"0x{base:08X}",
            "entry_point": f"0x{base+rva:08X}", "xbox_subsystem": True}


def decode_private(xex_path, out_path, key):
    out=Path(out_path).expanduser().resolve()
    if out.exists():
        raise FileExistsError("Refusing to overwrite an executable")
    if any((p/".git").exists() for p in (out.parent,*out.parents)):
        raise LzxPreflightError("Decoded PE must stay outside Git checkout")
    chunks, image_size, window, base, entry=verified_lzx_chunks(xex_path,key)
    cab=make_cab(chunks,image_size,window)
    lib=_libarchive()
    reader=lib.archive_read_new()
    if not reader:
        raise LzxPreflightError("Cannot allocate CAB reader")
    # Keep this allocated buffer alive until archive_read_free().
    mem=c.create_string_buffer(cab)
    out.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    try:
        if (lib.archive_read_support_format_all(reader)<0 or
                lib.archive_read_support_filter_all(reader)<0):
            raise LzxPreflightError("CAB support unavailable")
        if lib.archive_read_open_memory(reader,mem,len(cab))!=0:
            raise LzxPreflightError("Cannot open in-memory CAB")
        member=c.c_void_p()
        if (lib.archive_read_next_header(reader,c.byref(member))!=0 or
                lib.archive_entry_size(member)!=image_size):
            raise LzxPreflightError("CAB output geometry mismatch")
        digest=hashlib.sha256()
        count=0
        block=c.create_string_buffer(65536)
        with out.open("xb") as f:
            while count < image_size:
                n=lib.archive_read_data(reader,block,min(len(block),image_size-count))
                if n<=0:
                    raise LzxPreflightError("LZX stream incomplete")
                chunk=block.raw[:n]
                f.write(chunk)
                digest.update(chunk)
                count+=n
        out.chmod(0o600)
        metadata=validate_xbox_pe(out,image_size,base,entry)
        return {
            "verified":True, "lzx_frames":len(chunks),
            "lzx_window_bytes":window,"decoded_image_sha256":digest.hexdigest(),
            **metadata,"powerpc_executed":False,"nro_built":False,
        }
    except BaseException:
        out.unlink(missing_ok=True)
        raise
    finally:
        lib.archive_read_free(reader)


def main(argv=None):
    p=argparse.ArgumentParser(description="Decode user-supplied XEX2 to private PE")
    p.add_argument("xex",type=Path)
    p.add_argument("out",type=Path)
    p.add_argument("--wrapping-key-file",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        key=read_local_wrapping_key(args.wrapping_key_file)
        result=decode_private(args.xex,args.out,key)
        print(json.dumps(result,indent=2))
        return 0
    except (OSError,LzxPreflightError) as error:
        print("XEX image recovery failed:",error)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
