"""Synthetic tests only; do not ship game files or copyright material."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from nxlab.vulkan_probe import VulkanError, api_version, stage_deb, probe


class VulkanDoctorTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(api_version((1 << 22) | (3 << 12) | 7), (1, 3, 7))

    def test_checksum_blocks_non_mesa_payload(self):
        with TemporaryDirectory() as root:
            directory = Path(root)
            test_deb = directory / "fake.deb"
            test_deb.write_bytes(b"fake game? no, invalid package")
            output = directory / "private-driver"
            with self.assertRaises(VulkanError):
                stage_deb(test_deb, output)
            self.assertFalse(output.exists())

    def test_requires_new_private_workspace(self):
        with TemporaryDirectory() as root:
            target = Path(root) / "private"
            (Path(root) / ".git").mkdir()
            fake = Path(root) / "test.deb"
            fake.write_bytes(b"not a package")
            with self.assertRaises(VulkanError):
                stage_deb(fake, target)
            self.assertFalse(target.exists())

    def test_invalid_icd_rejected(self):
        with TemporaryDirectory() as root:
            file = Path(root) / "fake.json"
            file.write_text(json.dumps({"foo":"bar"}))
            with self.assertRaises(VulkanError):
                probe(file)


if __name__ == "__main__":
    unittest.main()
