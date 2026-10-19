"""Synthetic integration tests. Never store commercial game data in CI."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from nxlab.auto import run
from test_m2 import fixture


class AutoTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.xex=self.root/'synthetic.xex'
        self.xex.write_bytes(fixture())
        self.work=self.root/'private'

    def test_xex_inspection(self):
        report,location,code=run(self.xex,self.work)
        self.assertEqual(code,0)
        self.assertTrue(report['completed'])
        self.assertEqual(report['xex']['imports'][0]['name'],'xam.xex')
        self.assertFalse(report['switch_nro_built'])
        self.assertNotIn(str(self.root),(location/'report.json').read_text())

    def test_missing_rexglue_explicit_block(self):
        report,location,code=run(self.xex,self.work,codegen=True,
                            rexglue='nxlab-missing-binary-123')
        self.assertEqual(code,3)
        self.assertEqual(report['steps'][-1]['status'],'blocked')
        self.assertFalse(report['completed'])

    def test_bad_magic(self):
        self.xex.write_bytes(b'fake')
        report,_,code=run(self.xex,self.work)
        self.assertEqual(code,2)
        self.assertEqual(report['steps'][-1]['status'],'failed')

    def test_disallow_git_workspace(self):
        (self.root/'repo'/'.git').mkdir(parents=True)
        with self.assertRaises(ValueError):
            run(self.xex,self.root/'repo'/'build')

    def test_mock_sdk_only_proves_orchestration(self):
        mock=self.root/'fake-rexglue'
        mock.write_text("""#!/usr/bin/env python3
import sys
from pathlib import Path
a=sys.argv[1:]
if a==['init','--help']:
 print('--project-name --xex-path --project-root')
elif a and a[0]=='init':
 p=Path(a[a.index('--project-root')+1])
 p.mkdir(parents=True)
 (p/'test_manifest.toml').write_text('[project]\\nname="test"\\n')
elif a and a[0]=='codegen':
 p=Path.cwd()/'generated'
 p.mkdir(exist_ok=True)
 (p/'stub.cpp').write_text('int fake(){return 0;}\\n')
else: sys.exit(5)
""")
        mock.chmod(0o700)
        result,location,code=run(self.xex,self.work,codegen=True,rexglue=str(mock))
        self.assertEqual(code,0)
        self.assertEqual(result['rexglue']['cpp_files'],1)
        self.assertFalse(result['powerpc_executed'])
        self.assertFalse(result['switch_nro_built'])
        self.assertTrue((location/'rexglue-project'/'generated'/'stub.cpp').exists())

    def test_old_cli_blocked(self):
        old=self.root/'fake-old-rexglue'
        old.write_text('#!/bin/sh\necho "--app_root --app_name"\n')
        old.chmod(0o700)
        result,_,code=run(self.xex,self.work,codegen=True,rexglue=str(old))
        self.assertEqual(code,3)
        self.assertEqual(result['rexglue']['status'],'blocked')


if __name__=='__main__':
    unittest.main()
