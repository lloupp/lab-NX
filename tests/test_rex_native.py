"""ReXGlue stage-gate tests use mock SDK and synthetic XEX only."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nxlab.rex_native import NativeBuildError, build_private, install_hints, private_workspace


class NativeTests(unittest.TestCase):
    def test_function_hint_injection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "game_manifest.toml"
            manifest.write_text('[entrypoint]\nincludes = []\n')
            hints = root / "source_functions.toml"
            hints.write_text('[functions]\n0x820E15E8 = {}\n0x82112BC0 = { size = 988 }\n')
            install_hints(manifest, hints)
            self.assertIn('includes = ["nxlab_functions.toml"]', manifest.read_text())
            self.assertEqual((root / "nxlab_functions.toml").read_text(), hints.read_text())
            with self.assertRaises(NativeBuildError):
                install_hints(manifest, hints)

    def test_reject_untrusted_hints(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.toml"
            manifest.write_text('includes = []')
            hints = root / "hints.toml"
            for invalid in [
                '[project]\nname = "x"\n',
                '[functions]\n0x820E15E8 = { size = -1 }\n',
                '[functions]\n0x820E15E8 = { invalid = 3 }\n',
            ]:
                hints.write_text(invalid)
                with self.assertRaises(NativeBuildError):
                    install_hints(manifest, hints)
            self.assertEqual(manifest.read_text(), 'includes = []')

    def test_reject_git_workspace(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "checkout" / ".git").mkdir(parents=True)
            with self.assertRaises(NativeBuildError):
                private_workspace(root / "checkout" / "private")
            self.assertEqual(private_workspace(root / "standalone"), root / "standalone")

    def test_mock_sdk_proves_only_automation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "sdk" / "bin"
            sdk.mkdir(parents=True)
            script = sdk / "rexglue"
            script.write_text("""#!/usr/bin/env python3
import pathlib,sys
args=sys.argv[1:]
if args==['--version']:
 print('mock-rexglue 0.0')
elif args[0]=='init':
 target=pathlib.Path(args[args.index('--project-root')+1])
 target.mkdir(parents=True)
 (target/'test_manifest.toml').write_text('[entrypoint]\\nincludes = []\\n')
elif args[0]=='codegen':
 out=pathlib.Path.cwd()/'generated'/'default'
 out.mkdir(parents=True)
 (out/'test_recomp.0.cpp').write_text('int synthetic_not_game_code() {return 0;}\\n')
else:
 sys.exit(9)
""")
            script.chmod(0o700)
            source = root / "synthetic.xex"
            source.write_bytes(b"XEX2" + bytes(44))
            hints = root / "valid_functions.toml"
            hints.write_text('[functions]\n0x820E15E8 = {}\n')
            report, work, result = build_private(
                source, root / "private", root / "sdk", hints=hints, build=False)
            self.assertEqual(result, 0)
            self.assertEqual(report["recompiled_cpp_units"], 1)
            self.assertFalse(report["native_guest_behavior_verified"])
            self.assertFalse(report["game_playable"])
            self.assertFalse(report["switch_nro_built"])
            self.assertEqual(report["steps"][-1]["name"], "host_link")
            self.assertEqual(report["steps"][-1]["status"], "skipped")
            self.assertTrue((work / "report.json").is_file())

    def test_invalid_xex_early_reject(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            xex = root / "bad"
            xex.write_bytes(b"not XEX2")
            with self.assertRaises(NativeBuildError):
                build_private(xex, root / "work", root / "sdk", build=False)


if __name__ == "__main__":
    unittest.main()
