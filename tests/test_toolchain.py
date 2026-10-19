import unittest
from nxlab.toolchain import doctor


class ToolchainTests(unittest.TestCase):
    def test_missing_tools(self):
        report = doctor(lookup=lambda name: None)
        self.assertFalse(report["rexglue_ready"])
        self.assertEqual(report["blocker"], "rexglue_or_clang20")

    def test_clang20_and_rexglue(self):
        def lookup(name):
            return "/usr/bin/" + name
        def version(path):
            return ("clang version 20.1.1" if path.endswith("clang++")
                    else "tool version 1.0")
        report = doctor(lookup, version)
        self.assertTrue(report["rexglue_ready"])
        self.assertTrue(report["can_validate_switch_nro"])

    def test_old_clang_blocks_sdk(self):
        def lookup(name):
            return name
        def version(name):
            return "clang version 17.0.0" if name == "clang++" else "fake v1"
        self.assertFalse(doctor(lookup, version)["rexglue_ready"])


if __name__ == "__main__":
    unittest.main()
