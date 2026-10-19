import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from nxlab.supervisor import observe


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'synthetic.xex'
        self.source.write_bytes(b'XEX2' + bytes(64))
        self.workspace = self.root / 'private'

    def fake_run(self, src, work, **kwargs):
        target = self.workspace / 'runs' / 'run001'
        target.mkdir(parents=True, exist_ok=True)
        (target / 'report.json').write_text('{}')
        return {'steps': [{'name': 'stfs', 'status': 'skipped'},
                          {'name': 'xex_metadata', 'status': 'passed'}]}, target, 0

    def test_one_attempt_then_stop_unchanged(self):
        with patch('nxlab.auto.run', side_effect=self.fake_run) as runner:
            first = observe(self.source, self.workspace)
            second = observe(self.source, self.workspace)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(first['evaluation']['next_stage'], 'ppc_codegen')
        self.assertEqual(second['state'], 'unchanged_input')
        ledger = self.workspace / 'supervisor' / 'castle-crashers' / 'history.jsonl'
        self.assertEqual(len(ledger.read_text().splitlines()), 1)

    def test_force_explicitly_retries(self):
        with patch('nxlab.auto.run', side_effect=self.fake_run) as runner:
            observe(self.source, self.workspace)
            observe(self.source, self.workspace, force=True)
        self.assertEqual(runner.call_count, 2)

    def test_unimplemented_ps3_never_invokes_xbox_pipeline(self):
        with patch('nxlab.auto.run') as runner:
            result = observe(self.source, self.workspace, profile='demons-souls')
        self.assertEqual(result['state'], 'unsupported_backend')
        runner.assert_not_called()

    def test_disallow_output_within_git(self):
        (self.root / 'repo' / '.git').mkdir(parents=True)
        with self.assertRaises(ValueError):
            observe(self.source, self.root / 'repo' / 'build')


if __name__ == '__main__':
    unittest.main()
