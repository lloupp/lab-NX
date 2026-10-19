import tempfile
import unittest
from pathlib import Path
from nxlab.goldeneye_asset_audit import audit

class AssetDiffTests(unittest.TestCase):
    def test_affected_ranges_and_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'filelist.csv'
            p.write_text('2,3,assets/font.bin,0,0\n9,2,assets/music.bin,0,0\n')
            a = b'000000000000'
            b = bytearray(a)
            b[2] = 49
            b[3] = 50
            b[9] = 51
            b[0] = 52
            result = audit(a, bytes(b), p)
            self.assertEqual(result['affected_ranges']['assets/font.bin'], 2)
            self.assertEqual(result['affected_ranges']['assets/music.bin'], 1)
            self.assertEqual(result['unattributed_bytes'], 1)
            self.assertEqual(result['changed_runs'], 3)

    def test_unequal_length(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'filelist.csv'
            p.write_text('0,10,asset,0,0\n')
            out = audit(b'ABC', b'ABCD', p)
            self.assertEqual(out['changed_bytes'], 1)
            self.assertFalse(out['same_size'])

    def test_overlapping_regions_not_double_counted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'filelist.csv'
            p.write_text('0,5,asset1,0,0\n2,3,asset2,0,0\n')
            out = audit(b'000000', b'001000', p)
            self.assertEqual(out['unattributed_bytes'], 0)
            self.assertEqual(out['changed_bytes'], 1)
