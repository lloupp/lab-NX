"""GoldenEye 007: Xbox-style Switch gamepad adapter (engine-independent).

Translates a sample into semantic actions.  The game/backend must consume
these actions; this module alone does NOT remap RetroArch, patch a ROM,
or produce a playable NRO.
"""
from dataclasses import dataclass, field
from math import hypot, isfinite
from typing import FrozenSet

# Switch button labels (NOT Xbox letter positions).
DEFAULT_BUTTONS = {
    "A": "interact", "B": "crouch", "X": "weapon_next",
    "Y": "reload", "L": "weapon_prev", "R": "weapon_next",
    "ZL": "aim", "ZR": "fire", "PLUS": "pause",
}

@dataclass(frozen=True)
class ControlConfig:
    look_sensitivity: float = 1.0
    movement_deadzone: float = 0.15
    look_deadzone: float = 0.12
    invert_look_y: bool = False
    aim_mode: str = "hold"
    crouch_mode: str = "toggle"

    def __post_init__(self):
        if not isfinite(self.look_sensitivity) or not 0.1 <= self.look_sensitivity <= 3.0:
            raise ValueError("look_sensitivity must be in [0.1,3.0]")
        for name in ("movement_deadzone", "look_deadzone"):
            value = getattr(self, name)
            if not isfinite(value) or not 0 <= value < 1:
                raise ValueError(f"{name} must be in [0,1)")
        if self.aim_mode not in ("hold", "toggle"):
            raise ValueError("aim_mode must be hold or toggle")
        if self.crouch_mode not in ("hold", "toggle"):
            raise ValueError("crouch_mode must be hold or toggle")

@dataclass(frozen=True)
class PadSample:
    # Analog axes normalized to [-1,1], positive Y is up.
    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    buttons: FrozenSet[str] = field(default_factory=frozenset)

@dataclass(frozen=True)
class GameActions:
    move_x: float
    move_y: float
    look_x: float
    look_y: float
    aim: bool
    fire: bool
    crouch: bool
    interact_pressed: bool
    reload_pressed: bool
    weapon_next_pressed: bool
    weapon_prev_pressed: bool
    pause_pressed: bool

def radial_deadzone(x: float, y: float, threshold: float) -> tuple[float, float]:
    if not isfinite(x) or not isfinite(y):
        raise ValueError("Axes must be finite")
    x = max(-1.0, min(x, 1.0))
    y = max(-1.0, min(y, 1.0))
    magnitude = hypot(x, y)
    if magnitude <= threshold:
        return 0.0, 0.0
    scale = (min(magnitude, 1.0) - threshold) / ((1.0 - threshold) * magnitude)
    return x * scale, y * scale

class XboxStyleAdapter:
    """Independent look/movement, with held and press-edge actions."""

    def __init__(self, config: ControlConfig | None = None):
        self.config = config or ControlConfig()
        self._previous: FrozenSet[str] = frozenset()
        self._aim_toggled = False
        self._crouch_toggled = False

    def reset(self, held_buttons: FrozenSet[str] = frozenset()) -> None:
        """Pass currently held buttons during screen transitions."""
        self._previous = held_buttons
        self._aim_toggled = False
        self._crouch_toggled = False

    def step(self, pad: PadSample) -> GameActions:
        new = pad.buttons - self._previous
        self._previous = pad.buttons
        if self.config.aim_mode == "toggle" and "ZL" in new:
            self._aim_toggled = not self._aim_toggled
        if self.config.crouch_mode == "toggle" and "B" in new:
            self._crouch_toggled = not self._crouch_toggled

        mx, my = radial_deadzone(pad.lx, pad.ly, self.config.movement_deadzone)
        rx, ry = radial_deadzone(pad.rx, pad.ry, self.config.look_deadzone)
        lx = max(-1.0, min(rx * self.config.look_sensitivity, 1.0))
        ly = max(-1.0, min(ry * self.config.look_sensitivity *
                          (-1 if self.config.invert_look_y else 1), 1.0))
        return GameActions(
            move_x=mx, move_y=my, look_x=lx, look_y=ly,
            aim=self._aim_toggled if self.config.aim_mode == "toggle" else "ZL" in pad.buttons,
            fire="ZR" in pad.buttons,
            crouch=self._crouch_toggled if self.config.crouch_mode == "toggle" else "B" in pad.buttons,
            interact_pressed="A" in new,
            reload_pressed="Y" in new,
            weapon_next_pressed=bool(new & {"X", "R"}),
            weapon_prev_pressed="L" in new,
            pause_pressed="PLUS" in new,
        )
