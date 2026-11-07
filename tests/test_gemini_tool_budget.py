"""Regression: a large JARVIS registry must not be sent wholesale to Gemini."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_tool_budget_")

from core import brain, tools


def names(specs):
    return {s["function"]["name"] for s in specs}


class ToolBudgetTests(unittest.TestCase):
    def test_all_groups_still_have_only_small_exposed_toolset(self):
        all_specs = tools.specs()
        self.assertGreater(len(all_specs), 200)
        for text in ("JARVIS bir Excel tablosu oluştur, grafik ekle",
                     "Chrome tarayıcısında sayfadaki düğmeye tıkla",
                     "Bilgisayarda ekran görüntüsü gör ve fareyle sürükle",
                     "Güncel haberleri internette araştır ve kaynaklarla anlat",
                     "Bana bir günlük hatırlatıcı ayarla",
                     "Word belgesi oluştur",
                     "Ölçülü bir ev tasarla"):
            with self.subTest(command=text):
                chosen = brain._bounded_specs(all_specs, text)
                self.assertLessEqual(len(chosen), 24)
                self.assertIn("enable_tools", names(chosen))
                self.assertEqual(len(names(chosen)), len(chosen))

    def test_relevant_tools_survive_broad_shortlist(self):
        all_specs = tools.specs()
        cases = {
            "Excel tablosu oluştur": "create_excel",
            "Bir Word belgesi oluştur": "create_word",
            "Güncel haberleri internette araştır": "web_search",
            "Chrome'da tarayıcıdaki butona tıkla": "browser_click",
            "Ekrandaki fareyi sürükle": "mouse_drag",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertIn(expected, names(brain._bounded_specs(all_specs, command)))

    def test_manual_group_has_priority_without_widening_wire_budget(self):
        all_specs = tools.specs()
        chosen = brain._bounded_specs(all_specs, "Buna devam et", {"office"})
        self.assertLessEqual(len(chosen), 24)
        self.assertIn("create_excel", names(chosen))
        self.assertIn("create_word", names(chosen))
        self.assertIn("enable_tools", names(chosen))

    def test_local_architecture_flow_uses_native_model_tools(self):
        command = "Ev çiz, salon ve odaları yerleştir"
        focused = brain._bounded_specs(tools.specs({'core','architecture'}),command)
        self.assertIn('architecture_house',names(focused))
        self.assertIn('architecture_apply',names(focused))
        self.assertLessEqual(len(focused),24)

    def test_chat_routes_only_bounded_set_even_after_broad_group_match(self):
        captured = []
        def fake_route(order, messages, specs, *args, **kwargs):
            captured.append(specs)
            yield ("final", {"content": "Hazır.", "tool_calls": []})
        with patch.object(brain.llm, "route", side_effect=fake_route), \
             patch.object(brain.memory, "history", return_value=[]), \
             patch.object(brain.memory, "add_message"):
            list(brain.chat("JARVIS bana kapsamlı sistem haber müzik video güvenlik "
                            "ve grafik ofis takvim bilgisayar çalışma raporu hazırla."))
        self.assertTrue(captured)
        self.assertLessEqual(len(captured[0]), 24)
        self.assertIn("enable_tools", names(captured[0]))


if __name__ == "__main__":
    unittest.main()
