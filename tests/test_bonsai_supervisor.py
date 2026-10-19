"""Tests that Bonsai advice cannot turn into an execution gate or forced retry."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from nxlab.supervisor import observe


class SupervisorBonsaiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / "fake.xex"
        self.src.write_bytes(b"XEX2" + bytes(48))
        self.workspace = self.root / "private"

    def fake_pipeline(self, source, workspace, **kwargs):
        run_dir = self.workspace / "runs" / "mock001"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "report.json").write_text("{}")
        return ({"steps": [{"name": "stfs", "status": "skipped"},
                           {"name": "xex_metadata", "status": "passed"}]},
                run_dir, 0)

    def test_opt_in_advice_only(self):
        mock_advice = {"suggestion": {"action": "escalate", "category": "unknown",
                                      "reason": "A developer should review",
                                      "confidence": 0.9, "advisory_only": True,
                                      "executed": False}}
        with patch("nxlab.auto.run", side_effect=self.fake_pipeline), \
             patch("nxlab.bonsai.advise", return_value=mock_advice) as advice:
            result = observe(self.src, self.workspace, bonsai=True)
        self.assertEqual(result["bonsai"]["status"], "available")
        self.assertEqual(result["evaluation"]["next_stage"], "ppc_codegen")
        self.assertEqual(result["exit_code"], 0)
        advice.assert_called_once()

    def test_offline_bonsai_keeps_verified_results(self):
        with patch("nxlab.auto.run", side_effect=self.fake_pipeline), \
             patch("nxlab.bonsai.advise", side_effect=OSError("offline")):
            result = observe(self.src, self.workspace, bonsai=True)
        self.assertEqual(result["bonsai"]["status"], "unavailable")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["evaluation"]["next_stage"], "ppc_codegen")

    def test_bonsai_not_called_without_flag(self):
        with patch("nxlab.auto.run", side_effect=self.fake_pipeline), \
             patch("nxlab.bonsai.advise") as advice:
            result = observe(self.src, self.workspace)
        self.assertEqual(result["bonsai"]["status"], "not_requested")
        advice.assert_not_called()


if __name__ == "__main__":
    unittest.main()
