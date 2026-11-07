"""Routine browser actions skip repeated prompts; sensitive actions fail closed."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_approvals_")
from core import tools
from core.skills import browser, computer


class RoutineBrowserApprovalTests(unittest.TestCase):
    def setUp(self):
        self.old_state = dict(browser._state)
        self.page = Mock(url="https://example.org/planner")
        browser._state.update(page=self.page, manual=False)
        self.loc = Mock()
        self.loc.evaluate.return_value = {"kind": "text", "hint": "search"}
        self.patches = [
            patch.object(browser, "_page", return_value=self.page),
            patch.object(browser, "_call", side_effect=lambda f, *a, **kw: f(*a)),
            patch.object(browser, "_loc", return_value=self.loc),
            patch.object(browser, "_label_of", return_value="Next"),
            patch.object(browser, "load_settings", return_value={"auto_control": False, "routine_browser_auto": True}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        browser._state.clear()
        browser._state.update(self.old_state)

    def test_routine_navigation_and_text_no_confirmation(self):
        self.assertFalse(tools.is_critical("browser_click", {"target": "12"}))
        self.assertFalse(tools.is_critical("browser_fill", {"field": "search", "value": "room design"}))
        self.assertTrue(tools.is_critical("browser_fill", {"field": "search", "value": "room design", "submit": True}))

    def test_sensitive_clicks_still_require_confirmation(self):
        for label in ("Pay now", "Delete account", "Continue with Google", "Accept Terms",
                      "Allow permission", "Giriş yap", "Export PDF", "Paylaş"):
            with self.subTest(label=label), patch.object(browser, "_label_of", return_value=label):
                self.assertTrue(tools.is_critical("browser_click", {"target": "12"}))

    def test_sensitive_form_fields_require_confirmation(self):
        for field in (
            {"kind": "password", "hint": "password"},
            {"kind": "email", "hint": "contact"},
            {"kind": "text", "hint": "billing address"},
            {"kind": "text", "hint": "OTP verification code"},
        ):
            with self.subTest(field=field):
                self.loc.evaluate.return_value = field
                self.assertTrue(tools.is_critical("browser_fill", {"field": "4", "value": "abc"}))

    def test_auth_domains_require_confirmation(self):
        self.page.url = "https://accounts.google.com/signin"
        self.assertTrue(tools.is_critical("browser_click", {"target": "12"}))
        self.assertTrue(tools.is_critical("browser_fill", {"field": "4", "value": "abc"}))

    def test_unknown_controls_fail_closed(self):
        with patch.object(browser, "_loc", side_effect=RuntimeError("element missing")):
            self.assertTrue(tools.is_critical("browser_click", {"target": "12"}))
            self.assertTrue(tools.is_critical("browser_fill", {"field": "4", "value": "abc"}))

    def test_setting_can_restore_old_approval_behavior(self):
        with patch.object(browser, "load_settings", return_value={"auto_control": False, "routine_browser_auto": False}):
            self.assertTrue(tools.is_critical("browser_click", {"target": "12"}))
            self.assertTrue(tools.is_critical("browser_fill", {"field": "search", "value": "room design"}))

    def test_design_site_controls_follow_general_policy(self):
        self.page.url = "https://example.test/editor"
        with patch.object(browser, "_label_of", return_value="Room"):
            self.assertFalse(tools.is_critical("browser_click", {"target": "12"}))
        with patch.object(browser, "_label_of", return_value="Export PDF"):
            self.assertTrue(tools.is_critical("browser_click", {"target": "12"}))
        self.loc.evaluate.return_value = {"kind": "number", "hint": "width"}
        self.assertFalse(tools.is_critical("browser_fill", {"field": "width", "value": "400"}))

    def test_desktop_full_automation_is_still_opt_in(self):
        with patch.object(computer, "load_settings", return_value={"auto_control": False}):
            self.assertTrue(tools.is_critical("mouse_click", {"x": 20, "y": 30}))


if __name__ == "__main__":
    unittest.main()
