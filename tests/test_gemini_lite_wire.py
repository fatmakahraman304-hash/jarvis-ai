"""Wire-level Gemini 3.5+ compatibility and safe 400 diagnostics."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="gemini_lite_wire_")
from core import gemini_native


class GeminiLiteWireTests(unittest.TestCase):
    def setUp(self):
        self.old = set(gemini_native._NO_THINK_CFG)
        gemini_native._NO_THINK_CFG.clear()

    def tearDown(self):
        gemini_native._NO_THINK_CFG.clear()
        gemini_native._NO_THINK_CFG.update(self.old)

    def _capture(self, model, tools=None, required=False):
        response = io.BytesIO(json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}).encode())
        with patch.object(gemini_native.urllib.request, "urlopen", return_value=response) as urlopen:
            list(gemini_native.stream("test", model, [{"role": "user", "content": "hi"}],
                                      tools, tool_choice="required" if required else "auto"))
        return json.loads(urlopen.call_args.args[0].data)

    def test_lite_sends_no_legacy_generation_config(self):
        for model in ("gemini-3.5-flash-lite", "gemini-3.5-flash-lite-001"):
            with self.subTest(model=model):
                body = self._capture(model)
                self.assertNotIn("generationConfig", body)

    def test_flash_sends_low_thinking_but_not_sampling(self):
        for model in ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"):
            with self.subTest(model=model):
                body = self._capture(model)
                self.assertEqual(body["generationConfig"], {"thinkingConfig": {"thinkingLevel": "low"}})

    def test_legacy_model_preserves_sampling(self):
        body = self._capture("gemini-3-test")
        self.assertEqual(body["generationConfig"]["temperature"], 0.7)

    def test_tool_declaration_and_required_mode_unchanged(self):
        schema = [{"type": "function", "function": {"name": "safe_tool", "parameters": {
            "type": "object", "properties": {"a": {"type": "string"}}
        }}}]
        body = self._capture("gemini-3.5-flash-lite", schema, required=True)
        self.assertEqual(body["tools"][0]["functionDeclarations"][0]["name"], "safe_tool")
        self.assertEqual(body["toolConfig"]["functionCallingConfig"]["mode"], "ANY")

    def test_diagnostics_include_counts_not_user_data(self):
        body = {"contents": [
            {"role": "user", "parts": [{"text": "TOP_SECRET_PRIVATE_PROMPT"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "secret_name",
                "args": {"key": "SUPER_SECRET_KEY"}}, "thoughtSignature": "SIGSECRET"}]},
            {"role": "user", "parts": [{"functionResponse": {"name": "secret_name",
                "response": {"password": "secret123"}}}]}
        ], "tools": [{"functionDeclarations": [{"name": "secret_name"}]}]}
        summary = gemini_native._shape_summary(body)
        for secret in ("TOP_SECRET_PRIVATE_PROMPT", "SUPER_SECRET_KEY", "SIGSECRET",
                       "secret123", "secret_name"):
            self.assertNotIn(secret, summary)
        self.assertIn("arac_yaniti=1", summary)
        self.assertIn("imzali_cagri=1", summary)
        self.assertIn("son_rol=user", summary)


if __name__ == "__main__":
    unittest.main()
