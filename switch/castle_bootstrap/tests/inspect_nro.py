#!/usr/bin/env python3
"""Validate a real Nintendo Switch NRO header; does not claim game execution."""
from pathlib import Path
import argparse
import struct
def inspect(path):
    data=Path(path).read_bytes()
    if len(data)<0x80 or data[0x10:0x14]!=b'NRO0':
        raise ValueError("Not an NRO0 header")
    version,image_size,flags=struct.unpack_from('<III',data,0x14)
    if image_size<0x80 or image_size>len(data):
        raise ValueError("Invalid NRO image size")
    sections=[]
    for name,offset in [('text',0x20),('rodata',0x28),('data',0x30)]:
        start,size=struct.unpack_from('<II',data,offset)
        if start>image_size or size>image_size-start:
            raise ValueError("Invalid NRO "+name+" section bounds")
        sections.append((name,start,size))
    return {"format":"NRO0","version":version,"image_bytes":image_size,
            "file_bytes":len(data),"flags":flags,"sections":sections,
            "game_playable":False,"game_code_linked":False}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument('nro')
    print(inspect(p.parse_args().nro))
