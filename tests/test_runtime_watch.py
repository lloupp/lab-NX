"""Synthetic log tests; never execute a commercial game in CI."""
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from collections import Counter
from nxlab.runtime_watch import classify, watch, make_alsa_null_config, run_with_optional_audio


class RuntimeWatchTests(unittest.TestCase):
    def test_fault_and_trap_classification(self):
        totals, faults, invalid = Counter(), Counter(), Counter()
        classify("[error] Unhandled guest access violation: read of guest 0x0000003C",
                 totals, faults, invalid)
        classify("[critical] Call to invalid or unregistered function at guest address 0x82114E20",
                 totals, faults, invalid)
        classify("[error] SDL_InitSubSystem(SDL_INIT_AUDIO) failed: unavailable",
                 totals, faults, invalid)
        self.assertEqual(faults["0x0000003c"], 1)
        self.assertEqual(invalid["0x82114e20"], 1)
        self.assertEqual(totals["sdl_audio_init_error"], 1)

    def test_bounded_synthetic_stream_without_raw_logs(self):
        program = (
            "for i in range(3000):\n"
            " print('[error] Unhandled guest access violation: read of guest 0x00000010',flush=True)"
        )
        report = watch([sys.executable, "-c", program], 4)
        self.assertEqual(report["guest_faults"]["0x00000010"], 3000)
        self.assertFalse(report["raw_logs_stored"])
        self.assertFalse(report["game_playable"])

    def test_private_alsa_null_audio_config(self):
        with TemporaryDirectory() as temporary:
            config = make_alsa_null_config(temporary)
            self.assertEqual(config.parent, Path(temporary))
            self.assertIn("pcm.!default", config.read_text())
            self.assertIn("type null", config.read_text())
            with self.assertRaises(FileExistsError):
                make_alsa_null_config(temporary)

    def test_temporary_audio_configuration_cleaned(self):
        with patch("nxlab.runtime_watch.watch", return_value={"guest_faults": {}}) as backend:
            result = run_with_optional_audio(["fake"], 1, {}, alsa_null=True)
            self.assertEqual(result["guest_faults"], {})
            passed_env = backend.call_args.args[2]
            self.assertEqual(passed_env["SDL_AUDIODRIVER"], "alsa")
            self.assertFalse(Path(passed_env["ALSA_CONFIG_PATH"]).exists())

    def test_deadline_validation(self):
        with self.assertRaises(ValueError):
            watch([sys.executable], 0)


if __name__ == "__main__":
    unittest.main()
