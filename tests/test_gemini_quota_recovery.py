"""Gemini quota and ambiguous HTTP 400 recovery without false success."""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_gemini_recovery_")
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["GEMINI_MODEL"] = ""

from core import gemini_native, llm


def bad_request():
    raw = json.dumps({"error": {"code": 400, "message": "Request contains an invalid argument.", "status": "INVALID_ARGUMENT"}})
    return urllib.error.HTTPError("https://example.test", 400, "Invalid Argument", {}, io.BytesIO(raw.encode()))


class GeminiRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.before = set(gemini_native._NO_THINK_CFG)
        gemini_native._NO_THINK_CFG.clear()
        llm._cooldown.clear()

    def tearDown(self):
        gemini_native._NO_THINK_CFG.clear()
        gemini_native._NO_THINK_CFG.update(self.before)
        llm._cooldown.clear()

    def test_ambiguous_400_retries_once_without_optional_thinking(self):
        payload = json.dumps({"candidates": [{"content": {"parts": [{"text": "devam"}]}}]}).encode()
        decl = [{"type": "function", "function": {"name": "test_tool", "parameters": {"type": "object", "properties": {
            "value": {"type": "string"}
        }}}}]
        with patch.object(gemini_native.urllib.request, "urlopen",
                          side_effect=[bad_request(), io.BytesIO(payload)]) as req:
            events = list(gemini_native.stream("test", "gemini-3.5-flash",
                         [{"role": "user", "content": "devam"}], decl, tool_choice="required"))
        self.assertEqual(req.call_count, 2)
        bodies = [json.loads(c.args[0].data) for c in req.call_args_list]
        self.assertIn("thinkingConfig", bodies[0]["generationConfig"])
        self.assertNotIn("thinkingConfig", bodies[1].get("generationConfig", {}))
        self.assertEqual(bodies[0]["tools"], bodies[1]["tools"])
        self.assertEqual(bodies[0]["toolConfig"], bodies[1]["toolConfig"])
        self.assertEqual(bodies[0]["contents"], bodies[1]["contents"])
        self.assertEqual(events[-1][0], "final")

    def test_two_generic_400s_do_not_loop(self):
        with patch.object(gemini_native.urllib.request, "urlopen",
                          side_effect=[bad_request(), bad_request()]) as req:
            with self.assertRaisesRegex(gemini_native.NativeError, "400"):
                list(gemini_native.stream("test", "gemini-3.5-flash",
                                         [{"role": "user", "content": "selam"}]))
        self.assertEqual(req.call_count, 2)

    def test_429_then_400_reports_400_and_skips_cooling_models(self):
        models = ["gemini-3.8-flash", "gemini-3.5-flash"]
        seen = []

        def stream(pid, model, messages, tools=None, **kwargs):
            seen.append(model)
            if model == models[0]:
                raise llm.ProviderError(pid, 429, "quota")
            raise llm.ProviderError(pid, 400,
                '{"error":{"code":400,"message":"Request contains an invalid argument.","status":"INVALID_ARGUMENT"}}')
            yield ("text", "unreachable")

        with patch.object(llm, "list_models", return_value=models), \
             patch.object(llm, "configured", side_effect=lambda x: x == "gemini"), \
             patch.object(llm, "stream_chat", side_effect=stream), \
             patch.object(llm, "only_gemini", return_value=True), \
             patch.dict(os.environ, {"GEMINI_MODEL": ""}):
            first = list(llm.route(["gemini"], [{"role": "user", "content": "tasarla"}], None, tier="smart"))
            self.assertEqual(seen, models)
            errors = [v for k, v in first if k == "error"]
            self.assertEqual(len(errors), 1)
            self.assertIn("HTTP 400", errors[0])
            self.assertIn("HTTP 429", errors[0])
            self.assertNotIn("bugünkü ücretsiz hakkı doldu", errors[0])
            seen.clear()
            second = list(llm.route(["gemini"], [{"role": "user", "content": "tasarla"}], None, tier="smart"))
            self.assertEqual(seen, [])
            self.assertTrue(any(k == "error" and "kota" in v for k, v in second))


if __name__ == "__main__":
    unittest.main()
