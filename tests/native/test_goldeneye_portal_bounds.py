#!/usr/bin/env python3
"""Exercise the actual patched portal scanner with nonadjacent host symbols."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PIN = 'fda76b69837e6c5aae436e0d3e798989e49b06d2'


def function(text, name):
    start = text.index('void ' + name + '(void)')
    brace = text.index('{', start)
    # Conditional host/N64 loop endings contain alternative closing braces.
    end = text.index('\n}', brace) + 2
    return text[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    args = parser.parse_args()
    original = subprocess.check_output(['git', '-C', str(args.upstream), 'show', PIN + ':src/game/bg.c'], text=True)
    with tempfile.TemporaryDirectory(prefix='ge-portal-') as directory:
        work = Path(directory)
        path = work / 'src/game/bg.c'
        path.parent.mkdir(parents=True)
        path.write_text(original)
        subprocess.run(['git', 'apply', '--include=src/game/bg.c', str(ROOT / 'patches/goldeneye-pc-port/switch-platform.patch')], cwd=work, check=True)
        text = path.read_text()
        a = text.index('u8 specialportalarray[] = {')
        table = text[a:text.index('};', a) + 2]
        scanner = function(text, 'sub_GAME_7F0B37EC')
        driver = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef int32_t s32;
#define PORT 1
#define PORTALFLAG_SPECIAL 2
static struct { u8 prefix[10]; u8 controlbytes1; u8 suffix[5]; } g_BgPortals[256];
static int levelentry_index;
/* A host linker is allowed to place the next symbol arbitrarily far away.
 * It cannot define the bounds of this independent array. No dereference here. */
#define g_BgCurrentRoom (*(s32 *)(specialportalarray + sizeof specialportalarray + 4096))
'''
        checks = r'''
static void check(int level, unsigned count) {
    memset(g_BgPortals, 0, sizeof g_BgPortals);
    for (unsigned i=0;i<256;++i) g_BgPortals[i].controlbytes1=0x40;
    levelentry_index=level;
    sub_GAME_7F0B37EC();
    unsigned actual=0;
    for (unsigned i=0;i<256;++i) {
        assert(g_BgPortals[i].controlbytes1 & 0x40);
        actual += !!(g_BgPortals[i].controlbytes1 & PORTALFLAG_SPECIAL);
    }
    assert(actual==count);
}
int main(void) {
    check(14,0); /* no authored special-portal record */
    check(3,32);
    assert(g_BgPortals[0x2c].controlbytes1 & 2);
    assert(!(g_BgPortals[0x2f].controlbytes1 & 2));
    check(17,59);
    assert(g_BgPortals[0x3a].controlbytes1 & 2);
    assert(!(g_BgPortals[0x3b].controlbytes1 & 2));
    return 0;
}
'''
        def compile_run(name, body):
            source = work / (name + '.c')
            source.write_text(driver + table + '\n' + body + '\n' + checks)
            binary = work / name
            subprocess.run(['cc', '-std=c11', '-O1', '-g', '-fsanitize=address,undefined',
                            '-fno-omit-frame-pointer', str(source), '-o', str(binary)], check=True)
            # Leak scanning needs /proc task access unavailable in the Work sandbox.
            # Address/UB sanitizers remain enabled; this test allocates no heap.
            env = dict(os.environ)
            env['ASAN_OPTIONS'] = env.get('ASAN_OPTIONS', '') + ':detect_leaks=0'
            return subprocess.run([str(binary)], capture_output=True, text=True, timeout=3, env=env)
        patched = compile_run('patched', scanner)
        if patched.returncode:
            raise RuntimeError(patched.stderr)
        old = scanner.replace('end = specialportalarray + sizeof specialportalarray;', 'end = (u8 *)&g_BgCurrentRoom;')
        assert old != scanner
        regression = compile_run('adjacency', old)
        assert regression.returncode != 0 and 'global-buffer-overflow' in regression.stderr
        print('Actual portal scanner: 3 level cases pass; old symbol-adjacency boundary reproduces ASan overflow.')


if __name__ == '__main__':
    main()
