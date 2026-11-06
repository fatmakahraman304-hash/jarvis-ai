"""Focused tests for the Mark-LVI-inspired fast conversation layer."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jarvis_fast_chat_test_")

from core.brain import _history_window, _quick_ack  # noqa: E402


def main():
    rows = [
        {"role": "user", "content": "A" * 100},
        {"role": "assistant", "content": "B" * 100},
        {"role": "user", "content": "C" * 100},
    ]
    compact = _history_window(rows, 220)
    assert [r["content"] for r in compact] == ["B" * 100, "C" * 100]
    assert sum(len(r["content"]) for r in compact) <= 220

    oversized = _history_window([{"role": "user", "content": "X" * 300}], 80)
    assert len(oversized) == 1 and oversized[0]["content"] == "X" * 80

    assert _quick_ack("Merhaba, nasılsın?", {"core", "plugins", "semantic"}) == ""
    assert _quick_ack("Bilgisayarımın durumu", {"core", "windows"}) == "Bilgisayarı kontrol ediyorum, efendim."
    assert _quick_ack("Find recent news", {"core", "browser"}) == "I'm looking into that now."
    print("FAST CONVERSATION: OK")


if __name__ == "__main__":
    main()
