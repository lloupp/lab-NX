import math
import unittest

from nxlab.goldeneye_controls import (
    ControlConfig, PadSample, XboxStyleAdapter, radial_deadzone,
)

class XboxControlTests(unittest.TestCase):
    def test_default_buttons_and_edges(self):
        adapter = XboxStyleAdapter()
        pad = PadSample(buttons=frozenset({"A", "B", "X", "Y", "L", "R", "ZL", "ZR", "PLUS"}))
        first = adapter.step(pad)
        self.assertTrue(first.aim and first.fire and first.crouch)
        self.assertTrue(first.interact_pressed and first.reload_pressed)
        self.assertTrue(first.weapon_next_pressed and first.weapon_prev_pressed and first.pause_pressed)
        second = adapter.step(pad)
        self.assertTrue(second.aim and second.fire)
        self.assertFalse(second.interact_pressed or second.reload_pressed or second.weapon_next_pressed)
        self.assertFalse(second.weapon_prev_pressed or second.pause_pressed)
        adapter.step(PadSample())
        self.assertTrue(adapter.step(pad).interact_pressed)

    def test_sticks_and_deadzone(self):
        a = XboxStyleAdapter(ControlConfig(movement_deadzone=0.1, look_deadzone=0.1))
        s = a.step(PadSample(lx=.5, ly=1, rx=-.5, ry=.5))
        self.assertTrue(s.move_x > 0 and s.move_y > 0 and s.look_x < 0 and s.look_y > 0)
        self.assertEqual(radial_deadzone(.01, .02, .15), (0, 0))
        self.assertAlmostEqual(radial_deadzone(1, 0, .15)[0], 1)

    def test_sensitivity_inversion_and_toggle(self):
        a = XboxStyleAdapter(ControlConfig(look_sensitivity=2, invert_look_y=True, look_deadzone=0))
        self.assertEqual(a.step(PadSample(ry=.5)).look_y, -1)
        b = XboxStyleAdapter(ControlConfig(aim_mode="toggle", crouch_mode="toggle"))
        b.step(PadSample(buttons=frozenset({"B", "ZL"})))
        self.assertTrue(b.step(PadSample()).aim)
        self.assertTrue(b.step(PadSample()).crouch)
        b.step(PadSample(buttons=frozenset({"B", "ZL"})))
        self.assertFalse(b.step(PadSample()).aim)
        self.assertFalse(b.step(PadSample()).crouch)

    def test_screen_transition_suppresses_held_presses(self):
        a = XboxStyleAdapter()
        a.step(PadSample(buttons=frozenset({"A"})))
        a.reset(frozenset({"A"}))
        self.assertFalse(a.step(PadSample(buttons=frozenset({"A"}))).interact_pressed)

    def test_reject_bad_config(self):
        for cfg in ({"look_sensitivity": math.nan}, {"movement_deadzone": 1}, {"look_deadzone": -.1},
                    {"aim_mode": "wrong"}):
            with self.assertRaises(ValueError):
                ControlConfig(**cfg)
        with self.assertRaises(ValueError):
            radial_deadzone(math.inf, 0, .1)
