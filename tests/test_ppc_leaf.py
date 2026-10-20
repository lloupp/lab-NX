"""All generated source in these tests is synthetic, not commercial game code."""
import struct
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from nxlab.ppc_leaf import LiftError, decode, generate_cpp, interpret, fetch_words, lift_and_test


def make_pe(program):
    data=bytearray(0x6000)
    data[:2]=b'MZ'
    struct.pack_into('<I',data,0x3c,0xf0)
    data[0xf0:0xf4]=b'PE\0\0'
    struct.pack_into('<HHIIIHH',data,0xf4,0x1f2,1,0,0,0,224,0x102)
    opt=0xf0+24
    struct.pack_into('<H',data,opt,0x10b)
    struct.pack_into('<I',data,opt+16,0x5000)
    struct.pack_into('<I',data,opt+28,0x82000000)
    section=opt+224
    struct.pack_into('<8sIIIIIIHHI',data,section,b'.text\0\0\0',0x200,0x5000,0x200,0x400,0,0,0,0,0x60000020)
    data[0x400:0x404]=b'\x48\x00\x00\x00'  # poison conventional disk PE offset
    for n,word in enumerate(program):
        data[0x5000+4*n:0x5004+4*n]=word.to_bytes(4,'big')
    return bytes(data)


class LiftTests(unittest.TestCase):
    def test_return_constant_addis_ori_blr(self):
        ops=decode([0x3c608000,0x60634005,0x4e800020])
        self.assertEqual([o[0] for o in ops],['addis','ori','blr'])
        for seed in (0,1,0xffffffff):
            self.assertEqual(interpret(ops,seed),0x80004005)
        self.assertIn('return r[3]',generate_cpp(ops))

    def test_relative_addi(self):
        ops=decode([0x3863fffe,0x4e800020])
        self.assertEqual(interpret(ops,0),0xfffffffe)
        self.assertEqual(interpret(ops,5),3)

    def test_ori_xori(self):
        ops=decode([0x6063000f,0x68630003,0x4e800020])
        self.assertEqual(interpret(ops,0),0xc)

    def test_fail_closed(self):
        for words in ([0x60000000], [0x48000004,0x4e800020],
                      [0x4e800020,0x38600002], [0x38600002,0x38600003]):
            with self.assertRaises(LiftError): decode(words)

    def test_section_read_and_bad_address(self):
        with TemporaryDirectory() as td:
            source=Path(td)/'s.pe'
            source.write_bytes(make_pe([0x38600017,0x4e800020]))
            self.assertEqual(fetch_words(source,0x82005000,2),[0x38600017,0x4e800020])
            with self.assertRaises(LiftError):fetch_words(source,0x82006000,2)

    def test_synthetic_native_host_compile_and_execute(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source=root/'source.pe'
            source.write_bytes(make_pe([0x3c608000,0x60634005,0x4e800020]))
            report=lift_and_test(source,0x82005000,3,root/'private')
            self.assertTrue(report['all_matches'])
            self.assertFalse(report['rexglue_used'])
            self.assertFalse(report['function_boundary_proven'])
            with self.assertRaises(LiftError):
                lift_and_test(source,0x82005000,3,root/'private')


    @unittest.skipUnless(shutil.which('clang++'), 'Clang target cross-compiler missing')
    def test_synthetic_arm64_object(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source=root/'s.pe'
            source.write_bytes(make_pe([0x38630068,0x4e800020]))
            report=lift_and_test(source,0x82005000,2,root/'private',arm64=True)
            self.assertEqual(report['arm64_cross_compile']['kind'],
                             'ELF64 AArch64 relocatable')
            self.assertFalse(report['arm64_cross_compile']['switch_nro'])
            self.assertFalse(report['arm64_cross_compile']['arm64_executed'])
            self.assertEqual(int.from_bytes((root/'private'/'guest_arm64.o').read_bytes()[18:20],
                                            'little'),183)

if __name__=='__main__':unittest.main()
