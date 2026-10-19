"""Synthetic test for local prebuilt SDK path propagation."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from nxlab.goal_manager import run


class SdkForwardingTest(unittest.TestCase):
    def test_goal_manager_forwards_pinned_sdk_to_supervisor(self):
        with TemporaryDirectory() as folder:
            input_file = Path(folder) / 'synthetic.xex'
            input_file.write_bytes(b'XEX2')
            with patch('nxlab.supervisor.observe', return_value={
                'state': 'unchanged_input',
                'action': {'kind': 'stopped'}}) as observe:
                result = run(input_file, Path(folder)/'private',
                             codegen=True, rexglue='/private/sdk/bin/rexglue')
            self.assertFalse(result['playable'])
            self.assertEqual(observe.call_args.kwargs['rexglue'],
                             '/private/sdk/bin/rexglue')
            self.assertTrue(observe.call_args.kwargs['codegen'])


if __name__ == '__main__':
    unittest.main()
