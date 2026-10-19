import unittest
from unittest.mock import patch
from nxlab.input_probe import probe_sdl


class InputProbeTests(unittest.TestCase):
    def test_missing_sdl3_is_not_a_connected_controller(self):
        with patch("nxlab.input_probe.ctypes.util.find_library", return_value=None):
            report = probe_sdl()
        self.assertFalse(report["sdl3_found"])
        self.assertEqual(report["connected"], 0)
        self.assertEqual(report["gamepads"], [])

    def test_probe_does_not_claim_start_pressed(self):
        with patch("nxlab.input_probe.ctypes.util.find_library", return_value=None):
            report = probe_sdl()
        self.assertNotEqual(report.get("start_button_verified"), True)


if __name__ == "__main__":
    unittest.main()
