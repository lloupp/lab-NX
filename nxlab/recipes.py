"""Reusable porting recipes and verifiable stage gates (configuration, not shell)."""
from __future__ import annotations
from dataclasses import asdict, dataclass

STAGES = (
    "container_inventory", "xex_inspection", "ppc_codegen", "ppc_execution",
    "runtime_services", "graphics", "nro_build", "eden_smoke", "switch_hardware",
)


@dataclass(frozen=True)
class Recipe:
    name: str
    platform: str
    backend: str
    base: str
    graphics_backend: str
    services: tuple[str, ...]
    supported_now: bool
    notes: str

    def to_json(self):
        d = asdict(self)
        d["services"] = list(self.services)
        return d


X360 = Recipe("xbox360-base", "xbox360", "rexglue", "xbox360-base", "deko3d",
              ("xam", "xboxkrnl"), True, "Shared XEX/STFS, PPC and GPU contracts")
PS3 = Recipe("ps3-base", "ps3", "unavailable", "ps3-base", "deko3d",
             ("cell_syscalls", "spu"), False, "PS3 backend is not implemented")

BASES = {"xbox360-base": X360, "ps3-base": PS3}
GAMES = {
    "castle-crashers": ("xbox360-base", "XBLA; STFS/XEX2 verified"),
    "forza-horizon": ("xbox360-base", "Xenos/PM4 rendering requires special handling"),
    "fallout-nv": ("xbox360-base", "Gamebryo runtime requires special handling"),
    "demons-souls": ("ps3-base", "Cell/SPU requires separate backend"),
}


def resolve(name: str) -> Recipe:
    if name in BASES:
        return BASES[name]
    if name not in GAMES:
        raise ValueError(f"Unknown recipe: {name}")
    base_name, notes = GAMES[name]
    base = BASES[base_name]
    return Recipe(name, base.platform, base.backend, base.name,
                  base.graphics_backend, base.services, base.supported_now, notes)


def evaluate(report: dict, recipe: Recipe) -> dict:
    statuses = {x.get("name"): x.get("status") for x in report.get("steps", [])}
    passed = set()
    if statuses.get("stfs") == "passed":
        passed.add("container_inventory")
    if statuses.get("xex_metadata") == "passed":
        passed.add("xex_inspection")
    if statuses.get("rexglue_codegen") == "passed":
        passed.add("ppc_codegen")

    stages = {name: ("passed" if name in passed else "pending") for name in STAGES}
    if statuses.get("stfs") == "skipped" and "xex_inspection" in passed:
        stages["container_inventory"] = "skipped"  # Raw XEX has no STFS.
    if not recipe.supported_now:
        return {"recipe": recipe.name, "platform": recipe.platform,
                "status": "unsupported_backend", "stages": stages,
                "next_stage": None, "reason": "Platform backend not implemented"}
    blocked = [s for s in report.get("steps", [])
               if s.get("status") in ("failed", "blocked")]
    status = ("blocked" if blocked else
              "passed_through_codegen" if "ppc_codegen" in passed else "partial")
    next_stage = next((x for x in STAGES if stages[x] == "pending"), None)
    return {"recipe": recipe.name, "platform": recipe.platform,
            "status": status, "stages": stages, "next_stage": next_stage,
            "reason": blocked[-1].get("detail") if blocked else None}


HINTS = {
    "container_inventory": "Inspect STFS with the existing analyzer",
    "xex_inspection": "Run XEX2 metadata parser",
    "ppc_codegen": "Install and validate ReXGlue; run codegen",
    "ppc_execution": "Compile generated C++ and test an actual PPC function",
    "runtime_services": "Implement verified XAM/Xboxkrnl import contracts",
    "graphics": "Translate real GPU commands and capture a game-generated frame",
    "nro_build": "Compile and validate an ARM64 NRO with devkitPro",
    "eden_smoke": "Run the NRO in Eden, recording logs and frames",
    "switch_hardware": "Run the NRO on actual Nintendo Switch hardware",
}


def next_action(evaluation: dict, report: dict) -> dict:
    if evaluation["status"] == "unsupported_backend":
        return {"kind": "blocked", "instruction": "Implement platform backend first"}
    blocked = [s for s in report.get("steps", [])
               if s.get("status") in ("failed", "blocked")]
    if blocked:
        return {"kind": "investigate", "stage": blocked[-1].get("name"),
                "instruction": "Inspect sanitized logs; do not retry unchanged"}
    stage = evaluation.get("next_stage")
    return {"kind": "next_milestone" if stage else "complete", "stage": stage,
            "instruction": HINTS.get(stage, "All milestones independently verified")}
