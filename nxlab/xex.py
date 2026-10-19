"""Read-only XEX2 metadata reader; no executable decryption or recompilation."""
from pathlib import Path

class XexError(ValueError):
    pass

def inspect(path):
    p=Path(path)
    size=p.stat().st_size
    with p.open('rb') as f:
        h=f.read(24)
        if len(h)!=24 or h[:4]!=b'XEX2':
            raise XexError('Not XEX2')
        be=lambda b: int.from_bytes(b,'big')
        flags, pe_offset, security_offset, count = be(h[4:8]),be(h[8:12]),be(h[16:20]),be(h[20:24])
        if count>1024 or 24+8*count>size or pe_offset>=size or security_offset>=size:
            raise XexError('Invalid XEX2 header offsets or optional header count')
        headers=[]
        for _ in range(count):
            v=f.read(8)
            headers.append({'key':v[:4].hex().upper(),'value':v[4:].hex().upper()})
    return {'format':'XEX2','size_bytes':size,'module_flags':f'{flags:08X}',
            'pe_data_offset':pe_offset,'security_info_offset':security_offset,
            'optional_header_count':count,'optional_headers':headers,
            'code_decrypted':False,'code_recompiled':False}
