"""Only synthetic data; no game assets or game executables in CI."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nxlab.m2 import XexM2Error, inspect


def put32(buf, at, value):
    buf[at:at+4] = value.to_bytes(4, 'big')


def put16(buf, at, value):
    buf[at:at+2] = value.to_bytes(2, 'big')


def fixture():
    buf = bytearray(0x1100)
    buf[:4] = b'XEX2'
    put32(buf, 4, 1)
    put32(buf, 8, 0x1000)
    put32(buf, 16, 0x100)
    entries = [(0x3FF, 0x500), (0x10100, 0x82010100),
               (0x10201, 0x82000000), (0x103FF, 0x600),
               (0x40006, 0x580)]
    put32(buf, 20, len(entries))
    for i, (key, val) in enumerate(entries):
        put32(buf, 24+8*i, key)
        put32(buf, 28+8*i, val)
    put32(buf, 0x100, 0x184)
    put32(buf, 0x104, 0x400000)
    put32(buf, 0x100+0x110, 0x82000000)
    put32(buf, 0x100+0x180, 0)
    put32(buf, 0x500, 36)
    put16(buf, 0x504, 1)
    put16(buf, 0x506, 2)
    put32(buf, 0x508, 0x8000)
    put32(buf, 0x50c, 0x2000)
    put32(buf, 0x58c, 0x584108B7)
    raw = b'xam.xex\0'
    put32(buf, 0x600, 12+len(raw)+44)
    put32(buf, 0x604, len(raw))
    put32(buf, 0x608, 1)
    buf[0x60c:0x614] = raw
    put32(buf, 0x614, 44)
    put16(buf, 0x614+36, 0)
    put16(buf, 0x614+38, 1)
    put32(buf, 0x614+40, 0x82001000)
    return buf


class M2Tests(unittest.TestCase):
    def parse(self, data):
        with TemporaryDirectory() as folder:
            file = Path(folder)/'synthetic.xex'
            file.write_bytes(data)
            return inspect(file)

    def test_metadata_imports_compression(self):
        result = self.parse(fixture())
        self.assertEqual(result['execution']['title_id'], '584108B7')
        self.assertEqual(result['file_format']['compression'], 'normal_lzx')
        self.assertEqual(result['file_format']['encryption'], 'normal')
        self.assertEqual(result['image_base'], '0x82000000')
        self.assertEqual(result['import_slots_total'], 1)
        self.assertEqual(result['imports'][0]['name'], 'xam.xex')
        self.assertFalse(result['readiness']['code_recompiled'])

    def test_bad_payload_offset(self):
        data = fixture()
        put32(data, 8, 0x2000)
        with self.assertRaises(XexM2Error):
            self.parse(data)

    def test_overlarge_import_count(self):
        data = fixture()
        put16(data, 0x614+38, 3)
        with self.assertRaises(XexM2Error):
            self.parse(data)

    def test_short_security(self):
        data = fixture()
        put32(data, 0x100, 0x180)
        with self.assertRaises(XexM2Error):
            self.parse(data)

    def test_unterminated_library_name(self):
        data = fixture()
        data[0x60c:0x614] = b'badname!'
        with self.assertRaises(XexM2Error):
            self.parse(data)

    def test_wrong_magic(self):
        data = fixture()
        data[:4] = b'XXXX'
        with self.assertRaises(XexM2Error):
            self.parse(data)


if __name__ == '__main__':
    unittest.main()
