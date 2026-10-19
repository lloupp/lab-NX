"""No commercial files; run end-to-end using a synthetic ZIP and XEX2."""
import ctypes.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from zipfile import ZipFile

from nxlab.archive7z import extract_single_stfs, ArchiveError, detect
from nxlab.auto import run as run_pipeline
from test_m2 import fixture as fake_xex

ARCHIVE_AVAILABLE = ctypes.util.find_library("archive") is not None


def fake_stfs():
    xex = fake_xex()
    raw = bytearray(0xF000)
    raw[:4] = b'LIVE'
    raw[0x344:0x348] = bytes.fromhex('000D0000')
    raw[0x360:0x364] = bytes.fromhex('584108B7')
    raw[0x379] = 0x24
    raw[0x37B] = 1
    raw[0x37C:0x37E] = (1).to_bytes(2, 'little')
    entry = bytearray(64)
    entry[:11] = b'default.xex'
    entry[40] = 0x40 | 11
    entry[41:44] = (2).to_bytes(3, 'little')
    entry[47:50] = (1).to_bytes(3, 'little')
    entry[50:52] = b'\xff\xff'
    entry[52:56] = len(xex).to_bytes(4, 'big')
    raw[0xC000:0xC040] = entry
    raw[0xD000:0xD000+len(xex)] = xex
    return bytes(raw)


@skipUnless(ARCHIVE_AVAILABLE, 'system libarchive unavailable')
class ArchiveTests(TestCase):
    def test_zip_private_path_and_no_traversal(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            pkg = fake_stfs()
            path = root/'game.zip'
            with ZipFile(path, 'w') as f:
                f.writestr('../../unsafe/584108B7/000D0000/file', pkg)
                f.writestr('other.txt', b'non game text')
            out = root/'private'/'payload.stfs'
            result = extract_single_stfs(path, out)
            self.assertEqual(out.read_bytes(), pkg)
            self.assertEqual(result['format'], 'zip')
            self.assertFalse((root/'unsafe').exists())
            self.assertEqual(detect(path), 'zip')

    def test_archive_to_xex2_pipeline(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'game.zip'
            with ZipFile(source, 'w') as f:
                f.writestr('game/584108B7/000D0000/longfilename', fake_stfs())
            report, location, code = run_pipeline(source, root/'private')
            self.assertEqual(code, 0)
            self.assertEqual(report['archive']['stfs_candidates'], 1)
            self.assertEqual(report['stfs']['files'], 1)
            self.assertEqual(report['xex']['import_slots_total'], 1)
            self.assertEqual(report['xex']['file_format']['compression'], 'normal_lzx')
            self.assertFalse(report['powerpc_executed'])
            self.assertFalse(report['switch_nro_built'])
            self.assertTrue((location/'private'/'default.xex').is_file())
            self.assertNotIn(str(root), (location/'report.json').read_text())

    def test_multiple_stfs_rejected_and_removed(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'two.zip'
            with ZipFile(source, 'w') as f:
                f.writestr('one', fake_stfs())
                f.writestr('two', fake_stfs())
            dest = root/'private'/'payload.stfs'
            with self.assertRaises(ArchiveError):
                extract_single_stfs(source, dest)
            self.assertFalse(dest.exists())

    def test_bad_format_and_existing_file(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'invalid.7z').write_bytes(b'not an archive')
            with self.assertRaises(ArchiveError):
                extract_single_stfs(root/'invalid.7z', root/'new')
            with ZipFile(root/'ok.zip', 'w') as f:
                f.writestr('game', fake_stfs())
            out = root/'original'
            out.write_text('keep')
            with self.assertRaises(FileExistsError):
                extract_single_stfs(root/'ok.zip', out)
            self.assertEqual(out.read_text(), 'keep')
