"""Synthetic AES/LZX metadata tests; no console keys and no copyrighted binaries."""
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nxlab.xex_lzx_preflight import (
    LzxPreflightError, inspect_chain, inspect_xex, read_local_wrapping_key
)

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    CRYPTO = True
except ImportError:
    CRYPTO = False


def fixture():
    block = bytearray(48)
    block[24:26] = (8).to_bytes(2, "big")
    block[26:34] = b'LZXTEST!'
    # Remaining zero bytes include the terminating u16 length at 34.
    header = bytearray(0x300)
    header[:4] = b"XEX2"
    header[8:12] = (0x300).to_bytes(4,"big")
    header[16:20] = (0x100).to_bytes(4,"big")
    header[20:24] = (1).to_bytes(4,"big")
    header[24:28] = (0x3FF).to_bytes(4,"big")
    header[28:32] = (0x280).to_bytes(4,"big")
    header[0x100:0x104] = (0x184).to_bytes(4,"big")
    header[0x104:0x108] = (2*1024*1024).to_bytes(4,"big")
    header[0x280:0x284] = (36).to_bytes(4,"big")
    header[0x284:0x286] = (1).to_bytes(2,"big")
    header[0x286:0x288] = (2).to_bytes(2,"big")
    header[0x288:0x28c] = (32768).to_bytes(4,"big")
    header[0x28c:0x290] = len(block).to_bytes(4,"big")
    header[0x290:0x2a4] = hashlib.sha1(block).digest()
    return header,bytes(block)


class ChainTests(unittest.TestCase):
    def test_valid_synthetic_chain(self):
        _,block = fixture()
        stats=inspect_chain(block,len(block),hashlib.sha1(block).digest())
        self.assertTrue(stats["all_block_sha1_matched"])
        self.assertEqual(stats["lzx_chunks"],1)
        self.assertEqual(stats["lzx_compressed_stream_bytes"],8)
        self.assertFalse(stats["image_decompressed"])
        self.assertFalse(stats["powerpc_executed"])

    def test_corrupt_hash_rejected(self):
        _,block = fixture()
        with self.assertRaises(LzxPreflightError):
            inspect_chain(block,48,b"x"*20)

    def test_short_and_extra_bytes_rejected(self):
        _,block = fixture()
        with self.assertRaises(LzxPreflightError):
            inspect_chain(block[:23],48,hashlib.sha1(block).digest())
        with self.assertRaises(LzxPreflightError):
            inspect_chain(block+b"extra",48,hashlib.sha1(block).digest())

    def test_block_size_boundary(self):
        _,block = fixture()
        with self.assertRaises(LzxPreflightError):
            inspect_chain(block,49,hashlib.sha1(block).digest())

    def test_key_file_privacy(self):
        with TemporaryDirectory() as temp:
            p = Path(temp)/"private-key"
            p.write_bytes(b"z"*16)
            p.chmod(0o600)
            self.assertEqual(read_local_wrapping_key(p),b"z"*16)
            if os.name=="posix":
                p.chmod(0o644)
                with self.assertRaises(LzxPreflightError):
                    read_local_wrapping_key(p)
                p.chmod(0o600)
            link=Path(temp)/"link"
            link.symlink_to(p)
            with self.assertRaises(LzxPreflightError):
                read_local_wrapping_key(link)


@unittest.skipUnless(CRYPTO,"cryptography not installed")
class CryptoTests(unittest.TestCase):
    def make_xex(self):
        header, block = fixture()
        synthetic_wrapping_key=bytes(range(16))
        session_key=bytes([0x43]*16)
        e=Cipher(algorithms.AES(synthetic_wrapping_key),modes.ECB()).encryptor()
        header[0x250:0x260]=e.update(session_key)+e.finalize()
        e=Cipher(algorithms.AES(session_key),modes.CBC(bytes(16))).encryptor()
        return bytes(header)+e.update(block)+e.finalize(),synthetic_wrapping_key

    def test_encrypted_xex_block_roundtrip(self):
        data,key=self.make_xex()
        with TemporaryDirectory() as temp:
            p=Path(temp)/"synthetic.xex"
            p.write_bytes(data)
            result=inspect_xex(p,key)
            self.assertEqual(result["lzx_blocks_verified"],1)
            self.assertEqual(result["declared_image_bytes"],2097152)
            self.assertEqual(result["encryption_type"],1)

    def test_missing_key_and_wrong_key(self):
        data,key=self.make_xex()
        with TemporaryDirectory() as temp:
            p=Path(temp)/"synthetic.xex"
            p.write_bytes(data)
            with self.assertRaises(LzxPreflightError):
                inspect_xex(p)
            with self.assertRaises(LzxPreflightError):
                inspect_xex(p,b"X"*16)


if __name__=="__main__":
    unittest.main()
