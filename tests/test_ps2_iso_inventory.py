"""Synthetic PS2 ISO fixtures only. No copyrighted game assets."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "ps2_iso_inventory.py"
spec = importlib.util.spec_from_file_location("ps2_inventory", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def record(name, sector, length, directory=False):
    raw_name = name if isinstance(name, bytes) else name.encode("ascii")
    n = 33 + len(raw_name)
    n += n % 2
    data = bytearray(n)
    data[0] = n
    data[2:6] = sector.to_bytes(4, "little")
    data[6:10] = sector.to_bytes(4, "big")
    data[10:14] = length.to_bytes(4, "little")
    data[14:18] = length.to_bytes(4, "big")
    data[25] = 2 if directory else 0
    data[28:30] = b"\x01\x00"
    data[30:32] = b"\x00\x01"
    data[32] = len(raw_name)
    data[33:33 + len(raw_name)] = raw_name
    return bytes(data)


def fake_iso(tmpdir, with_boot=True):
    iso = bytearray(40 * 2048)
    pvd = 16 * 2048
    iso[pvd:pvd + 7] = b"\x01CD001\x01"
    root = record(b"\x00", 20, 2048, True)
    iso[pvd + 156:pvd + 156 + len(root)] = root
    offset = 20 * 2048
    for name, sector, length in [
        ("SYSTEM.CNF;1", 21, 48), ("TEST_000.01;1", 22, 128),
        ("KERNEL.XFF;1", 23, 2), ("MANAGER.XFF;1", 24, 2),
        ("GAMECORE.XFF;1", 25, 2), ("NICO.DAT;1", 26, 2),
    ]:
        r = record(name, sector, length)
        iso[offset:offset+len(r)] = r; offset += len(r)
    cnf = b"BOOT2 = cdrom0:\\TEST_000.01;1\r\n"
    iso[21*2048:21*2048 + len(cnf)] = cnf
    boot = bytearray(128)
    boot[:6] = b"\x7fELF\x01\x01"
    boot[18:20] = (8).to_bytes(2, "little")
    boot[24:28] = (0x100010).to_bytes(4, "little")
    if with_boot:
        iso[22*2048:22*2048+128] = boot
    path = Path(tmpdir) / "fixture.iso"
    path.write_bytes(iso)
    return path


class ISOTests(unittest.TestCase):
    def test_valid_synthetic_image(self):
        with tempfile.TemporaryDirectory() as d:
            report = mod.inventory(fake_iso(d), hash_iso=True)
            self.assertTrue(report["expected_modules_present"])
            self.assertEqual(report["boot"], "TEST_000.01")
            self.assertEqual(report["elf_entry"], "0x00100010")
            self.assertEqual(len(report["iso_sha256"]), 64)

    def test_wrong_elf_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(mod.InvalidISO, "MIPS ELF"):
                mod.inventory(fake_iso(d, with_boot=False))

    def test_wrong_signature_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = fake_iso(d)
            raw = bytearray(path.read_bytes())
            raw[16*2048+1] = 0
            path.write_bytes(raw)
            with self.assertRaisesRegex(mod.InvalidISO, "descriptor"):
                mod.inventory(path)

    def test_truncated_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = fake_iso(d)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaisesRegex(mod.InvalidISO, "sector-aligned"):
                mod.inventory(path)


if __name__ == "__main__":
    unittest.main()
