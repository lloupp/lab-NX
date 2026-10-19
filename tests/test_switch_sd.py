"""Only synthetic XEX bytes; never push commercial game files."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from nxlab.switch_sd import prepare
from test_m2 import fixture, put32


class SwitchSdTests(unittest.TestCase):
    def test_copies_valid_castle_xex_once(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"synthetic.xex"
            src.write_bytes(fixture())
            sd=root/"sdmc"
            sd.mkdir()
            result=prepare(src,sd)
            self.assertEqual(result["title_id"],"584108B7")
            self.assertFalse(result["game_playable"])
            self.assertEqual((sd/"switch/labnx/castle/default.xex").read_bytes(),src.read_bytes())
            with self.assertRaises(FileExistsError):
                prepare(src,sd)

    def test_reject_non_original_ppc_before_copy(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"synthetic.xex"
            src.write_bytes(fixture())
            fake_pe=root/"fake-decoded.pe"
            fake_pe.write_bytes(b"MZ"+bytes(2_949_118))
            sd=root/"sdmc"
            sd.mkdir()
            with self.assertRaises(ValueError):
                prepare(src,sd,decoded_pe=fake_pe)
            self.assertFalse((sd/"switch/labnx/castle/default.xex").exists())
            self.assertFalse((sd/"switch/labnx/castle/decoded-powerpc.bin").exists())

    def test_wrong_title_refused(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            buf=fixture()
            put32(buf,0x58c,0xdeadbeef)
            src=root/"wrong.xex"
            src.write_bytes(buf)
            sd=root/"sdmc"
            sd.mkdir()
            with self.assertRaises(ValueError):
                prepare(src,sd)
            self.assertFalse((sd/"switch/labnx/castle/default.xex").exists())


if __name__=="__main__":
    unittest.main()
