"""Synthetic log tests; never execute a commercial game in CI."""
import sys
import unittest
from collections import Counter
from nxlab.runtime_watch import classify, watch


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

    def test_deadline_validation(self):
        with self.assertRaises(ValueError):
            watch([sys.executable], 0)


if __name__ == "__main__":
    unittest.main()
