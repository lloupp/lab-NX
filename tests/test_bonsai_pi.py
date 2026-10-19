"""Unit tests for the Bonsai/Pi bridge. No real model or network required."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "launch_bonsai_pi.py"
spec = importlib.util.spec_from_file_location("launch_bonsai_pi", SCRIPT)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BonsaiPiTests(unittest.TestCase):
    def test_normalizes_valid_endpoint(self):
        self.assertEqual(
            bridge.normalized_api_url("http://127.0.0.1:8080/"),
            "http://127.0.0.1:8080/v1",
        )
        self.assertEqual(
            bridge.normalized_api_url("http://127.0.0.1:8080/v1"),
            "http://127.0.0.1:8080/v1",
        )
        with self.assertRaises(ValueError):
            bridge.normalized_api_url("file:///etc/passwd")
        with self.assertRaises(ValueError):
            bridge.normalized_api_url("http://127.0.0.1:8080/incorrect/path")

    def test_detects_server_context_and_model(self):
        def fake_get_json(url):
            if url.endswith("/health"):
                return {"status": "ok"}
            if url.endswith("/v1/models"):
                return {"data": [{"id": "bonsai-2-4b"}]}
            if url.endswith("/props"):
                return {"default_generation_settings": {"n_ctx": 65536}}
            raise AssertionError(url)
        with patch.object(bridge, "get_json", side_effect=fake_get_json):
            self.assertEqual(
                bridge.inspect_server("http://127.0.0.1:8080/v1", "bonsai-2-4b"), 65536
            )
            with self.assertRaisesRegex(RuntimeError, "ausente"):
                bridge.inspect_server("http://127.0.0.1:8080/v1", "bonsai-2-2b")

    def test_profile_isolated_and_sampling_configured(self):
        with TemporaryDirectory() as td:
            directory = Path(td) / "pi-agent"
            file = bridge.write_profile(
                directory, "http://127.0.0.1:8080/v1", "bonsai-2-4b", 16384
            )
            obj = json.loads(file.read_text(encoding="utf-8"))
            provider = obj["providers"]["bonsai-local"]
            self.assertEqual(provider["api"], "openai-completions")
            self.assertEqual(provider["apiKey"], "local")
            model = provider["models"][0]
            self.assertEqual(model["contextWindow"], 16384)
            self.assertEqual(model["maxTokens"], 4096)
            self.assertEqual(model["samplingParams"]["temperature"], 0.2)
            self.assertFalse(model["reasoning"])
            bridge.write_profile(
                directory, "http://127.0.0.1:8080/v1", "bonsai-2-2b", 8192
            )
            obj = json.loads(file.read_text(encoding="utf-8"))
            self.assertEqual(obj["providers"]["bonsai-local"]["models"][0]["id"], "bonsai-2-2b")

    def test_cannot_start_without_ready_server(self):
        with patch.object(bridge, "get_json", return_value={"status": "loading"}):
            self.assertEqual(bridge.main(["--verificar"]), 2)


if __name__ == "__main__":
    unittest.main()
