import unittest
from nxlab.recipes import resolve, evaluate, next_action


class RecipeTests(unittest.TestCase):
    def test_xbox_games_share_the_base(self):
        games = [resolve(name) for name in (
            "castle-crashers", "forza-horizon", "fallout-nv")]
        self.assertEqual({x.base for x in games}, {"xbox360-base"})
        self.assertEqual({x.backend for x in games}, {"rexglue"})

    def test_ps3_has_separate_unsupported_backend(self):
        profile = resolve("demons-souls")
        self.assertEqual(profile.platform, "ps3")
        self.assertFalse(profile.supported_now)
        self.assertEqual(evaluate({}, profile)["status"], "unsupported_backend")

    def test_codegen_is_not_execution(self):
        report = {"steps": [
            {"name": "stfs", "status": "passed"},
            {"name": "xex_metadata", "status": "passed"},
            {"name": "rexglue_codegen", "status": "passed"}]}
        state = evaluate(report, resolve("castle-crashers"))
        self.assertEqual(state["stages"]["ppc_codegen"], "passed")
        self.assertEqual(state["stages"]["ppc_execution"], "pending")
        self.assertEqual(state["next_stage"], "ppc_execution")

    def test_raw_xex_skips_stfs(self):
        report = {"steps": [
            {"name": "stfs", "status": "skipped"},
            {"name": "xex_metadata", "status": "passed"}]}
        result = evaluate(report, resolve("castle-crashers"))
        self.assertEqual(result["stages"]["container_inventory"], "skipped")
        self.assertEqual(result["next_stage"], "ppc_codegen")

    def test_blocker_generates_investigation_not_autoretry(self):
        report = {"steps": [{
            "name": "rexglue_codegen", "status": "blocked",
            "detail": "SDK unavailable"}]}
        state = evaluate(report, resolve("castle-crashers"))
        self.assertEqual(next_action(state, report)["kind"], "investigate")

    def test_unknown_recipe_rejected(self):
        with self.assertRaises(ValueError):
            resolve("unknown-game")


if __name__ == "__main__":
    unittest.main()
