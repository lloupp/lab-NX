"""Unit checks for bounded, non-privileged replay. No commercial game files."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nxlab.x11_input_probe import (
    InputProbeError, check_private, load_plan, validate_actions, DISPLAY_RE
)


class X11ReplayTests(unittest.TestCase):
    def test_whitelisted_game_actions(self):
        actions = [
            {"name": "press_start", "button": "start", "hold_ms": 250, "wait_ms": 500},
            {"name": "move_left", "button": "left", "hold_ms": 2000, "wait_ms": 500},
            {"name": "move_right", "button": "right", "hold_ms": 2000, "wait_ms": 500},
        ]
        self.assertEqual(validate_actions(actions), actions)

    def test_disallow_arbitrary_commands_and_keys(self):
        common = {"name": "invalid", "button": "start", "hold_ms": 100, "wait_ms": 1}
        for invalid in ({**common, "button": "Control+Alt+Delete"},
                        {**common, "name": "../escape"},
                        {**common, "hold_ms": 7000},
                        {**common, "wait_ms": -1},
                        {**common, "execute": "shell"}):
            with self.assertRaises(InputProbeError):
                validate_actions([invalid])
        with self.assertRaises(InputProbeError):
            validate_actions([common] * 21)

    def test_private_only_and_no_overwrite(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "repo" / ".git").mkdir(parents=True)
            with self.assertRaises(InputProbeError):
                check_private(root / "repo" / "screenshots")
            target = check_private(root / "test1")
            self.assertFalse(target.exists())
            target.mkdir()
            with self.assertRaises(InputProbeError):
                check_private(target)

    def test_replay_file_schema(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "recipe.json"
            value = {"schema": 1, "actions": [
                {"name": "confirm", "button": "confirm", "hold_ms": 200, "wait_ms": 400}]}
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual(load_plan(path), value["actions"])
            path.write_text(json.dumps({"schema": 2, "actions": []}))
            with self.assertRaises(InputProbeError):
                load_plan(path)

    def test_local_display_only(self):
        self.assertTrue(DISPLAY_RE.fullmatch(":125"))
        self.assertFalse(DISPLAY_RE.fullmatch("10.2.3.4:0"))
        self.assertFalse(DISPLAY_RE.fullmatch(":2; rm -rf ."))


if __name__ == "__main__":
    unittest.main()
