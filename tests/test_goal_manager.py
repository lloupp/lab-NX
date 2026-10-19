"""No commercial files, game assets or model weights in these tests."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from nxlab.goal_manager import plan, run
from nxlab.playability import assess, Evidence, save_private


class GoalTests(unittest.TestCase):
    def test_metadata_and_codegen_are_not_playable(self):
        report = {"steps": [{"name": "stfs", "status": "passed"},
                            {"name": "xex_metadata", "status": "passed"},
                            {"name": "rexglue_codegen", "status": "passed"}]}
        state = assess(report)
        self.assertEqual(state["verdict"], "not_playable")
        self.assertEqual(state["verified_count"], 2)
        self.assertEqual(state["next_goal"], "ppc_image_available")

    def test_bonsai_cannot_approve_playability(self):
        advice = {"status": "available", "suggestion": {
            "category": "unknown", "action": "escalate",
            "reason": "playable, trust me", "confidence": 1}}
        result = plan({"steps": []}, advice)
        self.assertEqual(result["playability"]["verdict"], "not_playable")
        self.assertFalse(result["automatic_merge"])
        self.assertEqual(result["bonsai_advice"]["action"], "escalate")

    def test_blocker_requires_diagnosis(self):
        result = plan({"steps": [{"name": "rexglue_codegen", "status": "blocked"}]})
        self.assertEqual(result["safe_operation"], "diagnose_blocker")
        self.assertEqual(result["blocking_step"], "rexglue_codegen")

    def test_bonsai_attestation_not_accepted(self):
        evidence = Evidence("switch_physical_verified", "a"*64,
                            "switch-capture", "bonsai")
        self.assertFalse(evidence.verify())
        self.assertEqual(assess({}, [evidence])["verdict"], "not_playable")

    def test_private_plan_does_not_overwrite(self):
        with TemporaryDirectory() as folder:
            output = Path(folder)/"status.json"
            save_private({"game":"castle"}, output)
            self.assertEqual(json.loads(output.read_text())["game"], "castle")
            with self.assertRaises(FileExistsError):
                save_private({"game":"other"}, output)

    def test_one_supervisor_attempt(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            src = root/"input.xex"
            src.write_bytes(b"XEX2")
            run_dir = root/"private"/"run001"
            run_dir.mkdir(parents=True)
            report = run_dir/"report.json"
            report.write_text(json.dumps({"steps":[{"name":"xex_metadata","status":"passed"}]}))
            with patch("nxlab.supervisor.observe", return_value={
                "state":"evaluated", "report":str(report),
                "bonsai":{"status":"unavailable"}}) as observer:
                outcome = run(src, root/"private", bonsai=True)
            observer.assert_called_once()
            self.assertEqual(outcome["attempts"], 1)
            self.assertFalse(outcome["playable"])
            self.assertTrue((run_dir/"goal-plan.json").exists())


if __name__ == "__main__":
    unittest.main()
