"""M2: bounded read-only XEX2 preflight; no decryption or game bytes output.

Format references: Xenia xex2_info.h and user_module.cc.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import struct
import sys

FILE_FORMAT = 0x3FF
ENTRY = 0x10100
IMAGE_BASE = 0x10201
IMPORTS = 0x103FF
EXECUTION = 0x40006
STATIC_LIBS = 0x200FF
ENCRYPTION = {0: 'none', 1: 'normal'}
COMPRESSION = {0: 'none', 1: 'basic', 2: 'normal_lzx', 3: 'delta'}


class XexM2Error(ValueError):
    pass


class Reader:
    def __init__(self, path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        if self.size > 256 * 1024 * 1024:
            raise XexM2Error('File exceeds inspection limit')
        self.file = self.path.open('rb')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.file.close()

    def get(self, pos, n):
        if pos < 0 or n < 0 or pos > self.size or n > self.size - pos:
            raise XexM2Error('Out-of-range metadata read')
        self.file.seek(pos)
        data = self.file.read(n)
        if len(data) != n:
            raise XexM2Error('Truncated XEX2')
        return data

    def u16(self, pos):
        return int.from_bytes(self.get(pos, 2), 'big')

    def u32(self, pos):
        return int.from_bytes(self.get(pos, 4), 'big')


def file_format(r, pos, limit):
    size = r.u32(pos)
    if size < 8 or pos + size > limit:
        raise XexM2Error('Invalid file format information')
    enc, comp = r.u16(pos+4), r.u16(pos+6)
    result = {'encryption': ENCRYPTION.get(enc, f'unknown({enc})'),
              'compression': COMPRESSION.get(comp, f'unknown({comp})'),
              'encryption_id': enc, 'compression_id': comp}
    if comp == 2:
        if size < 36:
            raise XexM2Error('Truncated LZX compression descriptor')
        result['lzx_window_size'] = r.u32(pos+8)
        result['first_block_bytes'] = r.u32(pos+12)
    elif comp == 1:
        if (size - 8) % 8:
            raise XexM2Error('Malformed basic compression descriptors')
        result['basic_block_count'] = (size - 8) // 8
    return result


def import_libraries(r, pos, limit):
    size = r.u32(pos)
    if size < 12 or size > limit-pos:
        raise XexM2Error('Invalid import directory')
    string_size, num_strings = r.u32(pos+4), r.u32(pos+8)
    if string_size > size-12 or num_strings > 1024:
        raise XexM2Error('Invalid import string table')
    raw = r.get(pos+12, string_size)
    strings = []
    cursor = 0
    for _ in range(num_strings):
        if cursor >= len(raw):
            raise XexM2Error('Truncated import names')
        stop = raw.find(b'\0', cursor)
        if stop == -1:
            raise XexM2Error('Unterminated library name')
        name = raw[cursor:stop].decode('ascii')
        if not name or any(ord(c) < 32 for c in name):
            raise XexM2Error('Invalid library name')
        strings.append(name)
        cursor = (stop+4) & ~3
    cursor = pos+12+string_size
    out = []
    while cursor < pos+size:
        if len(out) >= 256:
            raise XexM2Error('Too many import libraries')
        length = r.u32(cursor)
        if length == 0:
            if r.get(cursor, pos+size-cursor).strip(b'\0'):
                raise XexM2Error('Invalid import padding')
            break
        if length < 40 or length > pos+size-cursor:
            raise XexM2Error('Invalid import library record')
        name_index = r.u16(cursor+36) & 255
        count = r.u16(cursor+38)
        if name_index >= len(strings) or 40+4*count > length:
            raise XexM2Error('Invalid import count or string index')
        out.append({'name': strings[name_index], 'import_slots': count,
                    'library_record_bytes': length})
        cursor += length
    return out


def inspect(path):
    with Reader(path) as r:
        head = r.get(0, 24)
        if head[:4] != b'XEX2':
            raise XexM2Error('Not an XEX2 executable')
        flags, pe_start, reserved, security_start, count = struct.unpack('>5I', head[4:])
        if count > 1024 or 24+8*count > r.size:
            raise XexM2Error('Invalid XEX2 optional header table')
        if pe_start < 24+8*count or pe_start > r.size:
            raise XexM2Error('Invalid payload offset')
        if security_start < 24+8*count or security_start+0x184 > pe_start:
            raise XexM2Error('Invalid security header offset')
        options = {}
        for i in range(count):
            key, value = struct.unpack('>II', r.get(24+8*i, 8))
            if key in options:
                raise XexM2Error('Duplicate optional header key')
            options[key] = value
        if FILE_FORMAT not in options:
            raise XexM2Error('File format information missing')
        fmt = file_format(r, options[FILE_FORMAT], pe_start)

        execution = None
        if EXECUTION in options:
            values = struct.unpack('>4I4BI', r.get(options[EXECUTION], 24))
            execution = {'media_id': f'{values[0]:08X}', 'title_id': f'{values[3]:08X}',
                         'version_raw': f'{values[1]:08X}',
                         'base_version_raw': f'{values[2]:08X}',
                         'platform_id': values[4],
                         'disc_number': values[6], 'disc_count': values[7]}

        sec_size = r.u32(security_start)
        if sec_size < 0x184 or sec_size+security_start > pe_start:
            raise XexM2Error('Invalid security header size')
        image_size = r.u32(security_start+4)
        if not 0 < image_size <= 2*1024*1024*1024:
            raise XexM2Error('Invalid XEX image size')
        security = {
            'image_size_bytes': image_size,
            'load_address': f'0x{r.u32(security_start+0x110):08X}',
            'image_flags': f'0x{r.u32(security_start+0x10c):08X}',
            'import_table_count': r.u32(security_start+0x128),
            'page_descriptor_count': r.u32(security_start+0x180),
        }
        if 0x184+security['page_descriptor_count']*24 > sec_size:
            raise XexM2Error('Invalid page descriptors')

        imports = import_libraries(r, options[IMPORTS], pe_start) if IMPORTS in options else []
        statics = []
        if STATIC_LIBS in options:
            p = options[STATIC_LIBS]
            size = r.u32(p)
            if size < 4 or (size-4) % 16 or size+p > pe_start:
                raise XexM2Error('Invalid static library list')
            for i in range((size-4)//16):
                statics.append(r.get(p+4+16*i, 8).rstrip(b'\0').decode('ascii', 'replace'))
        return {
            'format': 'XEX2', 'size_bytes': r.size,
            'module_flags': f'0x{flags:08X}',
            'encrypted_payload_start': pe_start, 'reserved_header_word': reserved,
            'optional_header_count': count,
            'image_base': f'0x{options[IMAGE_BASE]:08X}' if IMAGE_BASE in options else None,
            'entry_point': f'0x{options[ENTRY]:08X}' if ENTRY in options else None,
            'file_format': fmt, 'execution': execution, 'security': security,
            'imports': imports,
            'import_slots_total': sum(item['import_slots'] for item in imports),
            'static_libraries': statics,
            'readiness': {
                'header_parsed': True,
                'powerpc_image_extracted': False, 'imports_resolved': False,
                'code_recompiled': False, 'native_execution_tested': False,
                'rexglue_cli_detected': shutil.which('rexglue') is not None
            }
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only Xbox 360 XEX2 M2 analyzer')
    parser.add_argument('xex', type=Path)
    parser.add_argument('--report', type=Path, help='Write JSON to new private file')
    args = parser.parse_args(argv)
    try:
        data = inspect(args.xex)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open('x', encoding='utf-8') as stream:
                json.dump(data, stream, indent=2, ensure_ascii=False)
                stream.write('\n')
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    except (OSError, XexM2Error, UnicodeError) as exc:
        print(f'XEX M2: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
