"""Smoke checks for the optional Mark LVI-style Gemini Live voice path."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.live_voice import LIVE_MODEL, LIVE_VOICE, LIVE_VOICES, SAMPLE_RATE, live_voice_socket


class LiveVoiceDefaultsTest(unittest.TestCase):
    def test_uses_mark_live_compatible_voice_defaults(self):
        self.assertEqual(LIVE_MODEL, "gemini-3.1-flash-live-preview")
        self.assertEqual(LIVE_VOICE, "Charon")
        self.assertEqual(LIVE_VOICES, {"jarvis": "Charon", "friday": "Aoede"})
        self.assertEqual(SAMPLE_RATE, 24000)

    def test_websocket_handler_is_loaded_lazily(self):
        self.assertTrue(callable(live_voice_socket))


if __name__ == "__main__":
    unittest.main()
