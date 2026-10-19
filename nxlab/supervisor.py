"""Evidence-based recipe supervisor: one bounded execution, no implicit agents.

Never uploads binaries or makes code changes. Saves evidence in private
workspace and avoids retrying unchanged inputs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from . import rexbridge
from .recipes import resolve, evaluate, next_action


def _fingerprint(source: Path, recipe: str, codegen: bool, rexglue: str):
    stat = source.stat()
    sdk = rexbridge.find(rexglue) if codegen else None
    sdk_info = None
    if sdk:
        s = Path(sdk).stat()
        sdk_info = [str(sdk), s.st_size, s.st_mtime_ns]
    record = [str(source.resolve()), stat.st_size, stat.st_mtime_ns,
              recipe, codegen, rexglue, sdk_info]
    return hashlib.sha256(json.dumps(record).encode()).hexdigest()


def observe(source, workspace, profile="castle-crashers", codegen=False,
            rexglue="rexglue", force=False, bonsai=False,
            bonsai_url="http://127.0.0.1:8080/v1/chat/completions",
            bonsai_model="bonsai-4b", bonsai_allow_lan=False) -> dict:
    """One supervised attempt; requires --force to rerun unchanged inputs."""
    from .auto import run as run_pipeline, workspace_outside_git

    recipe = resolve(profile)
    source = Path(source).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("Input must be a file")
    workspace = workspace_outside_git(workspace)
    if not recipe.supported_now:
        return {"state": "unsupported_backend", "recipe": recipe.to_json(),
                "action": {"kind": "blocked", "instruction": "No PS3 backend integrated"}}

    fingerprint = _fingerprint(source, profile, codegen, rexglue)
    ledger = workspace / "supervisor" / profile / "history.jsonl"
    if ledger.is_file() and not force:
        for line in ledger.read_text(encoding="utf8").splitlines():
            try:
                old = json.loads(line)
            except json.JSONDecodeError:
                continue
            if old.get("fingerprint") == fingerprint:
                return {"state": "unchanged_input", "recipe": recipe.to_json(),
                        "action": {"kind": "stopped", "instruction":
                                   "No changed inputs/SDK; fix blocker or use --force"}}

    report, location, rc = run_pipeline(
        source, workspace, project=profile.replace("-", "_"),
        codegen=codegen, rexglue=rexglue)
    assessment = evaluate(report, recipe)
    action = next_action(assessment, report)
    advisory = {"status": "not_requested"}
    if bonsai:
        from .bonsai import advise, BonsaiError
        try:
            suggestion = advise(report, profile, url=bonsai_url,
                                model=bonsai_model, allow_lan=bonsai_allow_lan)
            advisory = {"status": "available", "suggestion": suggestion["suggestion"]}
        except (BonsaiError, OSError, ValueError) as error:
            advisory = {"status": "unavailable", "reason": type(error).__name__}
    record = {"fingerprint": fingerprint, "recipe": recipe.name,
              "run_id": location.name, "exit_code": rc,
              "status": assessment["status"],
              "next_stage": assessment["next_stage"], "next_action": action}
    ledger.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with ledger.open("a", encoding="utf8") as fp:
        fp.write(json.dumps(record, separators=(",", ":")) + "\n")
    return {"state": "evaluated", "recipe": recipe.to_json(),
            "evaluation": assessment, "action": action, "bonsai": advisory,
            "report": str(location / "report.json"), "exit_code": rc}


def main(argv=None):
    p = argparse.ArgumentParser(description="NX-Lab recipe and evidence supervisor")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--recipe", default="castle-crashers")
    p.add_argument("--codegen", action="store_true")
    p.add_argument("--rexglue", default="rexglue")
    p.add_argument("--force", action="store_true")
    p.add_argument("--bonsai", action="store_true", help="Ask Bonsai for advice after the verified pipeline")
    p.add_argument("--bonsai-url", default="http://127.0.0.1:8080/v1/chat/completions")
    p.add_argument("--bonsai-model", default="bonsai-4b")
    p.add_argument("--bonsai-allow-lan", action="store_true")
    args = p.parse_args(argv)
    try:
        result = observe(args.input, args.workspace, args.recipe,
                         args.codegen, args.rexglue, args.force,
                        args.bonsai, args.bonsai_url, args.bonsai_model, args.bonsai_allow_lan)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result["state"] == "unsupported_backend":
            return 3
        return result.get("exit_code", 0)
    except (OSError, ValueError) as exc:
        print(f"lab-NX supervisor: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
