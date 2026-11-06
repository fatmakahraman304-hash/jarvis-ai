"""Regression tests for current Gemini model tiers and restricted-model fallback."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jarvis_model_tiers_")
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["GEMINI_MODEL"] = ""

from core import llm  # noqa: E402
from core.brain import _conversation_tier  # noqa: E402


def main():
    # /models can still list Gemini 2.5, although generateContent denies new projects.
    available = [
        "gemini-2.5-flash-lite", "gemini-2.5-flash",
        "gemini-3.1-flash-lite", "gemini-3.5-flash-lite",
        "gemini-3.5-flash", "gemini-3.6-flash",
        "gemini-3.7-flash", "gemini-3.8-flash",
    ]
    llm.list_models = lambda pid, refresh=False: list(available) if pid == "gemini" else []
    llm.configured = lambda pid: pid == "gemini"
    llm.allowed = lambda pid: True
    llm._cooldown.clear()

    fast = llm.ranked_models_for_tier("gemini", "fast")
    smart = llm.ranked_models_for_tier("gemini", "smart")
    search = llm.ranked_models_for_tier("gemini", "search")
    assert fast[0] == "gemini-3.5-flash-lite", fast
    assert smart[0] == "gemini-3.8-flash", smart
    assert search[0] == "gemini-3.5-flash-lite", search
    assert all(not m.startswith("gemini-2.5-") for tier in (fast, smart, search) for m in tier)
    assert "gemini-3.1-flash-lite" in fast and "gemini-3.7-flash" in smart
    assert llm._gemini_model_restricted("models/gemini-2.5-flash-lite")
    assert not llm._gemini_model_restricted("gemini-3.5-flash-lite")

    # Explicit legacy pins must also be ignored on this new project.
    assert llm.pick_model_for_tier("gemini", "fast", "gemini-2.5-flash-lite") == "gemini-3.5-flash-lite"
    os.environ["GEMINI_MODEL"] = "gemini-2.5-flash"
    assert llm.pick_model("gemini") == "gemini-3.8-flash"
    os.environ["GEMINI_MODEL"] = ""

    assert _conversation_tier("chromu aç", {"core", "browser"}) == "fast"
    assert _conversation_tier("Ekip kur: elektrikli araç pazarı için kapsamlı rapor hazırla", {"core", "team"}) == "smart"
    assert _conversation_tier("İnternette kaynaklarıyla güncel araştırma yap", {"core", "browser"}) == "search"

    seen = []

    def fake_stream(pid, model, messages, tools=None, temperature=0.7, timeout=90):
        seen.append((model, timeout))
        yield ("text", "tamam")
        yield ("final", {"content": "tamam", "tool_calls": []})

    llm.stream_chat = fake_stream
    list(llm.route(["gemini"], [{"role": "user", "content": "chromu aç"}], None, tier="fast"))
    assert seen == [("gemini-3.5-flash-lite", 10)], seen

    seen.clear()
    list(llm.route(["gemini"], [{"role": "user", "content": "derin analiz"}], None, tier="smart"))
    assert seen == [("gemini-3.8-flash", 20)], seen

    seen.clear()
    list(llm.route(["gemini"], [{"role": "user", "content": "kaynaklı araştır"}], None, tier="search"))
    assert seen == [("gemini-3.5-flash-lite", 10)], seen

    seen.clear()

    def restricted_then_ok(pid, model, messages, tools=None, temperature=0.7, timeout=90):
        seen.append(model)
        if model == "gemini-3.5-flash-lite":
            raise llm.ProviderError(pid, 404, "not available to this project")
        yield ("text", "yedek cevap")
        yield ("final", {"content": "yedek cevap", "tool_calls": []})

    llm.stream_chat = restricted_then_ok
    llm._cooldown.clear()
    list(llm.route(["gemini"], [{"role": "user", "content": "chromu aç"}], None, tier="fast"))
    assert seen[:2] == ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"], seen
    assert llm.cooling("gemini", "gemini-3.5-flash-lite") > 0

    # The 404 rung is skipped on the next user request.
    seen.clear()
    list(llm.route(["gemini"], [{"role": "user", "content": "chromu aç"}], None, tier="fast"))
    assert seen == ["gemini-3.1-flash-lite"], seen
    print("MODEL TIERS: OK")


if __name__ == "__main__":
    main()
