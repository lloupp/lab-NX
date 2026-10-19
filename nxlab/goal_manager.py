"""Bounded Bonsai goal manager for Castle Crashers; no arbitrary code execution.

One approved supervisor attempt, evidence evaluation, private plan.
No automatic patches, binary redistribution or game-related claims without proof.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .playability import assess, save_private


def plan(report: dict, advice: dict | None = None) -> dict:
    outcome = assess(report)
    suggestion = None
    if isinstance(advice, dict) and advice.get("status") == "available":
        raw = advice.get("suggestion")
        if isinstance(raw, dict):
            suggestion = {"category": raw.get("category"),
                          "action": raw.get("action"), "advisory_only": True}
    blocked = [s for s in report.get("steps", [])
               if isinstance(s, dict) and s.get("status") in ("blocked", "failed")]
    if blocked:
        operation, blocking = "diagnose_blocker", blocked[-1].get("name")
    else:
        operation, blocking = "request_next_milestone", None
    return {"playability": outcome, "safe_operation": operation,
            "blocking_step": blocking, "bonsai_advice": suggestion,
            "automatic_code_change": False, "automatic_merge": False,
            "attempt_limit": 1}


def run(source: Path, workspace: Path, *, recipe: str = "castle-crashers",
        codegen=False, bonsai=False, bonsai_url=None, model="bonsai-4b",
        force=False, rexglue='rexglue'):
    """Call existing supervisor once; never auto-retry unchanged failures."""
    from .supervisor import observe
    opts = {"profile": recipe, "codegen": codegen, "force": force,
            "rexglue": rexglue,
            "bonsai": bonsai, "bonsai_model": model}
    if bonsai_url is not None:
        opts["bonsai_url"] = bonsai_url
    result = observe(source, workspace, **opts)
    if result["state"] != "evaluated":
        return {"state": result["state"], "action": result.get("action"),
                "attempts": 0, "playable": False}
    report_path = Path(result["report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    decision = plan(report, result.get("bonsai"))
    output = {"state": "evaluated", "attempts": 1,
              "playable": decision["playability"]["verdict"] == "verified_playable",
              "goal": decision, "report": str(report_path)}
    save_private(output, report_path.parent / "goal-plan.json")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bonsai-assisted Castle Crashers goal manager")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--recipe", default="castle-crashers")
    parser.add_argument("--codegen", action="store_true")
    parser.add_argument("--bonsai", action="store_true")
    parser.add_argument("--bonsai-url")
    parser.add_argument("--bonsai-model", default="bonsai-4b")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--rexglue", default="rexglue", help="CLI name or absolute SDK path")
    args = parser.parse_args(argv)
    try:
        result = run(args.input, args.workspace, recipe=args.recipe,
                     codegen=args.codegen, bonsai=args.bonsai,
                     bonsai_url=args.bonsai_url, model=args.bonsai_model,
                     force=args.force, rexglue=args.rexglue)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("state") == "evaluated" else 3
    except (OSError, ValueError) as error:
        print(f"lab-NX goal manager: {type(error).__name__}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
