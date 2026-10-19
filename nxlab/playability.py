"""Honest Castle Crashers playability gates. No synthetic frame counts as gameplay."""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path

GATES = (
    "stfs_verified", "xex_metadata_verified", "ppc_image_available",
    "ppc_codegen_verified", "native_ppc_call_verified",
    "xbox_services_verified", "graphics_from_game_verified",
    "nro_arm64_verified", "eden_game_menu_verified",
    "controller_input_verified", "switch_physical_verified",
)

HINTS = {
    "stfs_verified": "Inspect genuine STFS inventory",
    "xex_metadata_verified": "Parse the real XEX2 header",
    "ppc_image_available": "Obtain and validate an authorized PowerPC image with a compatible SDK",
    "ppc_codegen_verified": "Run actual ReXGlue, record SDK version and generated C++ diagnostics",
    "native_ppc_call_verified": "Execute and compare an actual recompiled PPC function",
    "xbox_services_verified": "Implement required XAM/Xboxkrnl service contracts",
    "graphics_from_game_verified": "Capture a frame produced by actual Castle Crashers code/assets",
    "nro_arm64_verified": "Build a valid ARM64 NRO for Switch",
    "eden_game_menu_verified": "Open actual game menu in Eden, with trace and image",
    "controller_input_verified": "Interact with real game/menu and record controller response",
    "switch_physical_verified": "Validate the game on physical Nintendo Switch",
}

@dataclass(frozen=True)
class Evidence:
    stage: str
    artifact_sha256: str
    source: str
    attested_by: str

    def verify(self) -> bool:
        return (self.stage in GATES and len(self.artifact_sha256) == 64
                and all(c in "0123456789abcdef" for c in self.artifact_sha256)
                and self.source in ("toolchain", "native-test", "eden-capture", "switch-capture")
                and self.attested_by == "human-review")


def assess(report: dict, evidence: list[Evidence] | None = None) -> dict:
    """Only M1 metadata status is derived automatically; no model claims accepted."""
    passed = set()
    steps = report.get("steps", [])
    if isinstance(steps, list):
        if any(x.get("name") == "stfs" and x.get("status") == "passed"
               for x in steps if isinstance(x, dict)):
            passed.add("stfs_verified")
        if any(x.get("name") == "xex_metadata" and x.get("status") == "passed"
               for x in steps if isinstance(x, dict)):
            passed.add("xex_metadata_verified")
    for item in evidence or []:
        if item.verify():
            passed.add(item.stage)
    stages = {name: ("verified" if name in passed else "pending") for name in GATES}
    next_goal = next((name for name in GATES if name not in passed), None)
    complete = len(passed) == len(GATES)
    return {"game": "castle-crashers",
            "verdict": "verified_playable" if complete else "not_playable",
            "gates": stages, "verified_count": len(passed),
            "total_gates": len(GATES),
            "next_goal": next_goal or "review-complete",
            "next_instruction": HINTS.get(next_goal, "Review all evidence")}


def save_private(state: dict, path: Path) -> None:
    path = Path(path).expanduser().resolve()
    if any((directory / ".git").exists() for directory in
           (path.parent, *path.parents)):
        raise ValueError("Do not save private evidence inside a Git repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
