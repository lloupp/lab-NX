"""Synthetic-only tests. No retail keys, games, or generated game code in CI."""
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nxlab.lzx_image import make_cab, validate_xbox_pe, LzxPreflightError
from nxlab.pe_elf import wrap_text


def synthetic_xbox_pe():
    data=bytearray(0x6000)
    data[:2]=b"MZ"
    struct.pack_into("<I",data,0x3C,0xF0)
    data[0xF0:0xF4]=b"PE\0\0"
    struct.pack_into("<HHIIIHH",data,0xF4,0x1F2,1,0,0,0,224,0x102)
    opt=0xF0+24
    struct.pack_into("<H",data,opt,0x10B)
    struct.pack_into("<I",data,opt+16,0x5000)
    struct.pack_into("<I",data,opt+28,0x82000000)
    struct.pack_into("<H",data,opt+68,14)
    section=opt+224
    struct.pack_into("<8sIIIIIIHHI",data,section,
                     b".text\0\0\0",0x200,0x5000,0x200,0x400,0,0,0,0,0x60000020)
    data[0x5000:0x5004]=b"\x38\x60\x00\x01"  # PPC li r3,1
    data[0x400:0x404]=b"\x48\x00\x00\x00"  # fake disk PE raw pointer to reject\n    return bytes(data)


class LzxImageTests(unittest.TestCase):
    def test_cab_wrap_frame_geometry(self):
        cab=make_cab([b"fake-compressed-frame"],32768,32768)
        self.assertEqual(cab[:4],b"MSCF")
        self.assertEqual(int.from_bytes(cab[8:12],"little"),len(cab))
        self.assertIn(b"image.pe\0",cab)

    def test_no_wrong_number_of_frames(self):
        with self.assertRaises(LzxPreflightError):
            make_cab([b"frame"],65536,32768)
        with self.assertRaises(LzxPreflightError):
            make_cab([b"frame"],32768,1234)

    def test_pe_verified_and_wrong_base_rejected(self):
        with TemporaryDirectory() as t:
            pe=Path(t)/"test.pe"
            pe.write_bytes(synthetic_xbox_pe())
            result=validate_xbox_pe(pe,len(synthetic_xbox_pe()),0x82000000,0x82005000)
            self.assertEqual(result["entry_point"],"0x82005000")
            with self.assertRaises(LzxPreflightError):
                validate_xbox_pe(pe,4096,0x81000000,0x82005000)

    def test_elf_wrapper_preserves_ppc_instruction_and_entry(self):
        with TemporaryDirectory() as t:
            pe,elf=Path(t)/"source.pe",Path(t)/"private.elf"
            pe.write_bytes(synthetic_xbox_pe())
            info=wrap_text(pe,elf)
            data=elf.read_bytes()
            self.assertEqual(data[:4],b"\x7fELF")
            self.assertEqual(data[4:7],b"\x01\x02\x01")
            self.assertEqual(int.from_bytes(data[18:20],"big"),20)
            self.assertEqual(int.from_bytes(data[24:28],"big"),0x82005000)
            self.assertEqual(data[256:260],b"\x38\x60\x00\x01")
            self.assertFalse(info["code_executed"])
            with self.assertRaises(FileExistsError):
                wrap_text(pe,elf)

    def test_invalid_code_section_rejected(self):
        with TemporaryDirectory() as t:
            raw=bytearray(synthetic_xbox_pe())
            raw[0x5000:0x5004]=b"MZ\0\0"  # not enough to change PE structure
            opt=0xF0+24
            # Strip executable flag from .text.
            struct.pack_into("<I",raw,opt+224+36,0x40000040)
            pe=Path(t)/"bad.pe"
            pe.write_bytes(raw)
            with self.assertRaises(LzxPreflightError):
                wrap_text(pe,Path(t)/"out.elf")


if __name__=="__main__":
    unittest.main()
