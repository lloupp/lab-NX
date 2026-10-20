"""Synthetic-only import descriptor and thunk mapping tests."""
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nxlab.import_contracts import ImportAnalysisError, inspect, parse_export_table
from test_lzx_image import synthetic_xbox_pe


def fixture():
    pe=bytearray(synthetic_xbox_pe())
    nt=0xF0
    opt=nt+24
    struct.pack_into("<H",pe,nt+6,2)
    s=opt+224+40
    struct.pack_into("<8sIIIIIIHHI",pe,s,
                     b".rdata\0\0",0x200,0x1000,0x200,0x600,0,0,0,0,0x40000040)
    pe[0x1000:0x1004]=(0x190).to_bytes(4,"big")
    pe[0x600:0x604]=(0xFFFFFFFF).to_bytes(4,"big")  # poison raw PE offset
    xex=bytearray(0x700)
    xex[:4]=b"XEX2"
    xex[8:12]=(0x700).to_bytes(4,"big")
    xex[20:24]=(1).to_bytes(4,"big")
    xex[24:28]=(0x103FF).to_bytes(4,"big")
    xex[28:32]=(0x300).to_bytes(4,"big")
    table=0x300
    names=b"xam.xex\0"
    xex[table:table+4]=(68).to_bytes(4,"big")
    xex[table+4:table+8]=(len(names)).to_bytes(4,"big")
    xex[table+8:table+12]=(1).to_bytes(4,"big")
    xex[table+12:table+20]=names
    rec=table+20
    xex[rec:rec+4]=(48).to_bytes(4,"big")
    xex[rec+38:rec+40]=(2).to_bytes(2,"big")
    xex[rec+40:rec+44]=(0x82001000).to_bytes(4,"big")
    xex[rec+44:rec+48]=(0x82005000).to_bytes(4,"big")
    return bytes(xex),bytes(pe)


class ImportTests(unittest.TestCase):
    def scan(self,xex,pe,lookup=None):
        with TemporaryDirectory() as td:
            root=Path(td)
            a,b=root/"fake.xex",root/"fake.pe"
            a.write_bytes(xex)
            b.write_bytes(pe)
            return inspect(a,b,lookup)

    def test_data_descriptor_distinct_from_thunk(self):
        xex,pe=fixture()
        out=self.scan(xex,pe)
        self.assertEqual(out["total_slots"],2)
        self.assertEqual(out["unique_ordinal_symbols"],1)
        lib=out["libraries"][0]
        self.assertEqual(lib["thunk_slots"],1)
        self.assertEqual(lib["symbols"][0]["ordinal"],0x190)
        self.assertFalse(out["original_game_code_executed"])

    def test_optional_public_name_lookup(self):
        table=parse_export_table(
            "XE_EXPORT(xam, 0x00000190, XamInputGetCapabilities, kFunction),")
        xex,pe=fixture()
        out=self.scan(xex,pe,{"xam.xex":table})
        self.assertEqual(out["libraries"][0]["symbols"][0]["name"],
                         "XamInputGetCapabilities")

    def test_reject_bad_import_address(self):
        xex,pe=fixture()
        data=bytearray(xex)
        data[0x314+40:0x314+44]=(0x99000000).to_bytes(4,"big")
        with self.assertRaises(ImportAnalysisError):
            self.scan(data,pe)

    def test_no_import_directory(self):
        xex,pe=fixture()
        data=bytearray(xex)
        data[24:28]=(0x3FF).to_bytes(4,"big")
        with self.assertRaises(ImportAnalysisError):
            self.scan(data,pe)


if __name__=="__main__":
    unittest.main()
