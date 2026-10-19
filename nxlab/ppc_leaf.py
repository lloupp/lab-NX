"""Experimental restricted PowerPC -> native C++ lifter for private game PE snippets.

Only basic integer instructions and a terminal BLR. No Xbox runtime, memory,
branches, or graphics. Never includes protected binary bytes in source control.
Generated C++ is derived from the provided PE and MUST stay outside Git.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

class LiftError(ValueError):
    pass


def _sections(data):
    if len(data) < 512 or data[:2] != b'MZ':
        raise LiftError('Not a PE file')
    nt = int.from_bytes(data[0x3C:0x40], 'little')
    if nt < 64 or nt+24 >= len(data) or data[nt:nt+4] != b'PE\0\0':
        raise LiftError('Invalid PE header')
    machine = int.from_bytes(data[nt+4:nt+6], 'little')
    count = int.from_bytes(data[nt+6:nt+8], 'little')
    opt_size = int.from_bytes(data[nt+20:nt+22], 'little')
    opt = nt+24
    if machine != 0x01F2 or not 1 <= count <= 64 or opt_size < 32 or opt+opt_size+40*count > len(data):
        raise LiftError('Expected Xbox PowerPC PE')
    base = int.from_bytes(data[opt+28:opt+32], 'little')
    sections=[]
    for i in range(count):
        p = opt+opt_size+40*i
        name = data[p:p+8].split(b'\0',1)[0]
        rva = int.from_bytes(data[p+12:p+16], 'little')
        raw_size = int.from_bytes(data[p+16:p+20], 'little')
        offset = int.from_bytes(data[p+20:p+24], 'little')
        flags = int.from_bytes(data[p+36:p+40], 'little')
        if offset + raw_size > len(data):
            raise LiftError('Invalid PE section')
        if flags & 0x20000000:
            sections.append((name,base+rva,raw_size,offset))
    return sections


def fetch_words(path, address, count):
    if count < 2 or count > 64 or address & 3:
        raise LiftError('Expected aligned 2..64 instructions')
    data = Path(path).read_bytes()
    if len(data) > 512*1024*1024:
        raise LiftError('PE too large')
    for name,start,size,offset in _sections(data):
        if start <= address and address+count*4 <= start+size:
            at = offset+address-start
            return [int.from_bytes(data[p:p+4], 'big') for p in range(at,at+count*4,4)]
    raise LiftError('Snippet must fit entirely within an executable PE section')


def _signed16(n):
    n &= 0xffff
    return n - 0x10000 if n & 0x8000 else n


def decode(words):
    """Compile-time fail closed for unsupported PPC instructions."""
    operations=[]
    for i,word in enumerate(words):
        if word == 0x4e800020:  # blr
            if i != len(words)-1:
                raise LiftError('BLR must terminate the snippet')
            operations.append(('blr',))
            continue
        op = word >> 26
        rd,ra,imm = (word >> 21)&31, (word >> 16)&31, word&0xffff
        if op == 14:
            operations.append(('addi',rd,ra,_signed16(imm)))
        elif op == 15:
            operations.append(('addis',rd,ra,_signed16(imm)))
        elif op == 24:
            operations.append(('ori',ra,rd,imm))
        elif op == 26:
            operations.append(('xori',ra,rd,imm))
        else:
            raise LiftError(f'Unsupported PowerPC opcode at instruction {i}: primary={op}')
    if not operations or operations[-1][0] != 'blr':
        raise LiftError('Snippet does not end with BLR')
    return operations


def interpret(operations, seed):
    regs = [0]*32
    regs[3] = seed & 0xffffffff
    for op in operations:
        kind = op[0]
        if kind == 'blr':
            break
        dest,source,value = op[1:]
        base = 0 if source == 0 and kind in ('addi','addis') else regs[source]
        if kind == 'addi':
            regs[dest] = (base+value) & 0xffffffff
        elif kind == 'addis':
            regs[dest] = (base+(value<<16)) & 0xffffffff
        elif kind == 'ori':
            regs[dest] = base | value
        elif kind == 'xori':
            regs[dest] = base ^ value
    return regs[3]


def generate_cpp(operations):
    statements=[]
    for op in operations:
        kind=op[0]
        if kind == 'blr':
            statements.append('return r[3];')
            break
        dest,source,value=op[1:]
        base = '0u' if source == 0 and kind in ('addi','addis') else f'r[{source}]'
        if kind == 'addi':
            expr=f'({base} + uint32_t(int32_t({value})))'
        elif kind == 'addis':
            expr=f'({base} + (uint32_t(int32_t({value})) << 16))'
        elif kind == 'ori':
            expr=f'({base} | uint32_t({value}))'
        elif kind == 'xori':
            expr=f'({base} ^ uint32_t({value}))'
        statements.append(f'r[{dest}] = {expr};')
    return ('#include <cstdint>\n#include <cstdlib>\n#include <iostream>\n'
            'uint32_t run(uint32_t seed) { uint32_t r[32] = {}; r[3] = seed;\n'
            + '\n'.join(statements) + '\n}\n'
            'int main(int argc, char** argv) { if (argc != 2) return 2; '
            'char* end=nullptr; unsigned long x=std::strtoul(argv[1], &end, 0); '
            'if (*end) return 3; std::cout << run(uint32_t(x)) << "\\n"; }\n')


def lift_and_test(pe, address, count, workspace, seeds=(0,1,17,65535,4294967295), compiler='c++'):
    work = Path(workspace).expanduser().resolve()
    if any((p/'.git').exists() for p in (work,*work.parents)):
        raise LiftError('Private workspace must be outside Git')
    words = fetch_words(pe,address,count)
    operations = decode(words)
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise LiftError('Workspace must start empty; never overwrite previous evidence')
    cpp = work/'guest_lift.cpp'
    exe = work/'guest_lift'
    cpp.write_text(generate_cpp(operations), encoding='utf-8')
    compile_result=subprocess.run([compiler,'-O2','-std=c++17','-Wall','-Wextra',str(cpp),'-o',str(exe)],
                                  capture_output=True,text=True,timeout=45,check=False)
    if compile_result.returncode:
        raise LiftError('Native compiler rejected PPC lifter: '+compile_result.stderr[:400])
    runs=[]
    for seed in seeds:
        expected=interpret(operations,seed)
        proc=subprocess.run([str(exe),str(seed)],capture_output=True,text=True,timeout=5,check=False)
        if proc.returncode or proc.stdout.strip()!=str(expected):
            raise LiftError(f'Native result disagrees for input {seed}')
        runs.append({'input_r3':seed,'expected_r3':expected,'native_r3':int(proc.stdout.strip()),'matched':True})
    report={'kind':'PPC opcode-subset static lifting test','address':f'0x{address:08X}',
            'instructions':len(words),'opcodes':[op[0] for op in operations],
            'snippet_sha256':hashlib.sha256(b''.join(w.to_bytes(4,'big') for w in words)).hexdigest(),
            'native_cpp_sha256':hashlib.sha256(cpp.read_bytes()).hexdigest(),
            'results':runs,'all_matches':True,'host_compiled':True,
            'rexglue_used':False,'function_boundary_proven':False,
            'full_game_playable':False,'switch_nro_built':False}
    (work/'evidence.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description='Lift a bounded real PowerPC game snippet to host C++ privately')
    parser.add_argument('private_pe',type=Path)
    parser.add_argument('--address',required=True,type=lambda v:int(v,0))
    parser.add_argument('--instructions',required=True,type=int)
    parser.add_argument('--workspace',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        print(json.dumps(lift_and_test(args.private_pe,args.address,args.instructions,args.workspace),indent=2))
        return 0
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        print('PPC native test:',exc)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
