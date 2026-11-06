"""Regression tests for Gemini tool schemas: empty enum values cause HTTP 400."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_gemini_schema_")

from core import gemini_native, tools


def assert_valid_enums(test, node, path="root"):
    if isinstance(node, dict):
        if "enum" in node:
            values = node["enum"]
            test.assertIsInstance(values, list, path)
            test.assertTrue(values, path)
            for i, value in enumerate(values):
                test.assertIsNotNone(value, f"{path}.enum[{i}]")
                if isinstance(value, str):
                    test.assertTrue(value.strip(), f"{path}.enum[{i}]")
        for key, value in node.items():
            assert_valid_enums(test, value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            assert_valid_enums(test, item, f"{path}[{index}]")


class GeminiToolSchemaTests(unittest.TestCase):
    def test_all_real_tools_have_valid_native_declarations(self):
        native = gemini_native._tools(tools.specs())
        self.assertTrue(native and native[0]["functionDeclarations"])
        declarations = native[0]["functionDeclarations"]
        self.assertGreater(len(declarations), 100)
        assert_valid_enums(self, native)
        excel = next(d for d in declarations if d["name"] == "create_excel")
        chart = excel["parameters"]["properties"]["chart"]
        self.assertEqual(chart["enum"], ["bar", "line", "pie"])
        self.assertNotIn("chart", excel["parameters"].get("required", []))

    def test_recursive_sanitizer_removes_invalid_options(self):
        raw = {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["", "bar", None, "line", "  "]},
            "empty": {"type": "string", "enum": ["", " "]},
            "nested": {"type": "array", "items": {"type": "object", "properties": {
                "v": {"type": "string", "enum": ["", "ok"]},
            }}},
        }}
        cleaned = gemini_native._schema(raw)
        self.assertEqual(cleaned["properties"]["kind"]["enum"], ["bar", "line"])
        self.assertNotIn("enum", cleaned["properties"]["empty"])
        self.assertEqual(cleaned["properties"]["nested"]["items"]["properties"]["v"]["enum"], ["ok"])
        assert_valid_enums(self, cleaned)


if __name__ == "__main__":
    unittest.main()
