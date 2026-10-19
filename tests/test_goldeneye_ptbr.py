import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from nxlab import goldeneye_ptbr as ge

class GoldenEyeTranslationTests(unittest.TestCase):
    def test_patch_plain_and_rle(self):
        patch = (b"PATCH" + b"\x00\x00\x02" + b"\x00\x03" + b"XYZ"
                 + b"\x00\x00\x08" + b"\x00\x00\x00\x04" + b"!" + b"EOF")
        output, records = ge.apply_ips(b"0123456789", patch)
        self.assertEqual(output, b"01XYZ567!!!!")
        self.assertEqual(records, 2)

    def test_ips_invalid_or_truncated(self):
        for patch in (b"bad", b"PATCH", b"PATCH\x00\x01", b"PATCHEOF\x00"):
            with self.subTest(patch=patch), self.assertRaises(ge.PatchError):
                ge.apply_ips(b"abcdefgh", patch)

    def test_reject_wrong_rom_and_cic(self):
        with self.assertRaises(ge.PatchError):
            ge.require_original(bytes.fromhex("80371240") + b"\x00" * 32)
        with self.assertRaises(ge.PatchError):
            ge.calc_n64_crc6102(b"\x00" * 0x101000)

    def test_zip_with_one_matching_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "patch.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("translation.ips", b"PATCHEOF")
                z.writestr("readme.txt", "doc")
            self.assertEqual(ge.read_source(p, {".ips"}, 100), b"PATCHEOF")
            with zipfile.ZipFile(p, "a") as z:
                z.writestr("second.ips", b"PATCHEOF")
            with self.assertRaises(ge.PatchError):
                ge.read_source(p, {".ips"}, 100)
