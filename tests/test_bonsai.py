"""Advisory-only model bridge tests; no model weights and no game files needed."""
import io
import json
import unittest
from unittest.mock import patch

from nxlab.bonsai import BonsaiError, advise, endpoint, parse_suggestion, sanitize


REPORT = {
    "source_sha256": "TOP_PRIVATE_HASH",
    "input_path": "/home/user/private/game.xex",
    "steps": [
        {"name": "xex_metadata", "status": "passed"},
        {"name": "rexglue_codegen", "status": "blocked",
         "detail": "KEY=PRIVATE Secret directory /home/user/private"},
    ],
    "xex": {
        "file_format": {"compression": "normal_lzx", "encryption": "normal"},
        "import_slots_total": 401,
        "imports": [{"name": "xam.xex"}, {"name": "xboxkrnl.exe"},
                    {"name": "super-private-payload"}],
    },
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class BonsaiTests(unittest.TestCase):
    def test_secret_fields_are_not_transferred(self):
        summary = json.dumps(sanitize(REPORT, "castle-crashers"))
        for secret in ("TOP_PRIVATE_HASH", "/home/user", "KEY=PRIVATE",
                       "super-private-payload"):
            self.assertNotIn(secret, summary)
        self.assertIn("401", summary)

    def test_local_only_by_default(self):
        self.assertEqual(endpoint("http://127.0.0.1:8080/v1/chat/completions"),
                         "http://127.0.0.1:8080/v1/chat/completions")
        for remote in ("http://192.168.1.2:8080/v1/chat/completions",
                       "https://evil.example/v1/chat/completions",
                       "file:///etc/passwd",
                       "http://user:pass@127.0.0.1:8080/v1/chat/completions"):
            with self.assertRaises(BonsaiError):
                endpoint(remote)
        self.assertEqual(endpoint("http://192.168.1.2:8080/v1/chat/completions",
                                  allow_lan=True),
                         "http://192.168.1.2:8080/v1/chat/completions")
        with self.assertRaises(BonsaiError):
            endpoint("https://example.com/v1/chat/completions", allow_lan=True)

    def test_disallow_actions_outside_vocabulary(self):
        with self.assertRaises(BonsaiError):
            parse_suggestion(json.dumps({"category": "unknown", "action": "execute_shell",
                                         "reason": "Run arbitrary commands", "confidence": 0.9}))

    def test_valid_advice_cannot_execute(self):
        suggestion = {"category": "dependency_missing", "action": "install_sdk",
                      "reason": "The required SDK is not installed", "confidence": 0.8}
        reply = {"choices": [{"message": {"content": json.dumps(suggestion)}}]}
        with patch("nxlab.bonsai.urlopen",
                   return_value=FakeResponse(json.dumps(reply).encode())) as client:
            result = advise(REPORT, "castle-crashers")
        self.assertFalse(result["auto_execution"])
        self.assertFalse(result["suggestion"]["executed"])
        sent = client.call_args[0][0].data.decode()
        for secret in ("TOP_PRIVATE_HASH", "KEY=PRIVATE", "/home/user/private"):
            self.assertNotIn(secret, sent)
        self.assertIn("json_object", sent)

    def test_invalid_model_reply_rejected(self):
        reply = {"choices": [{"message": {"content": "not json"}}]}
        with patch("nxlab.bonsai.urlopen",
                   return_value=FakeResponse(json.dumps(reply).encode())):
            with self.assertRaises(BonsaiError):
                advise(REPORT, "castle-crashers")

    def test_disallow_remote_before_network(self):
        with patch("nxlab.bonsai.urlopen") as network:
            with self.assertRaises(BonsaiError):
                advise(REPORT, "castle-crashers",
                       url="https://public.example/v1/chat/completions")
            network.assert_not_called()

    def test_payload_with_unknown_fields_fails_closed(self):
        with self.assertRaises(BonsaiError):
            parse_suggestion(json.dumps({"category": "unknown",
                                         "action": "escalate", "reason": "needs review",
                                         "confidence": 0.5, "execute": True}))

    def test_no_error_for_missing_metadata(self):
        summary = sanitize({"steps": []}, "castle-crashers")
        self.assertIsNone(summary["xex"]["import_slots"])
        self.assertEqual(summary["xex"]["encryption"], "unknown")


if __name__ == "__main__":
    unittest.main()
