"""Regression tests for the one-pass web research budget."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jarvis_research_budget_")

from core.brain import _research_tool_specs, _search_result_usable  # noqa: E402


def main():
    specs = [
        {"type": "function", "function": {"name": "web_search"}},
        {"type": "function", "function": {"name": "news_search"}},
        {"type": "function", "function": {"name": "read_webpage"}},
        {"type": "function", "function": {"name": "open_app"}},
    ]

    names = lambda rows: [row["function"]["name"] for row in rows]

    assert names(_research_tool_specs(specs)) == [
        "web_search", "news_search", "read_webpage", "open_app"
    ]

    # Once one federated search has usable results, no second search tool is exposed.
    usable_web = json.dumps({"sonuçlar": [{"başlık": "Oyuncu kadrosu", "link": "https://example.com"}]})
    assert _search_result_usable("web_search", usable_web)
    after_search = _research_tool_specs(specs, search_done=True)
    assert names(after_search) == ["read_webpage", "open_app"]

    # An empty/error response permits one alternative wording, not an unlimited loop.
    assert not _search_result_usable("web_search", "Arama yapılamadı")
    after_one_failure = _research_tool_specs(specs, search_attempts=1)
    assert names(after_one_failure) == [
        "web_search", "news_search", "read_webpage", "open_app"
    ]
    after_two_failures = _research_tool_specs(specs, search_attempts=2)
    assert names(after_two_failures) == ["read_webpage", "open_app"]

    # At most one source page is opened in a single user turn.
    after_page = _research_tool_specs(specs, search_done=True, page_reads=1)
    assert names(after_page) == ["open_app"]

    usable_news = json.dumps([{"başlık": "Haber", "kaynak": "AA"}], ensure_ascii=False)
    assert _search_result_usable("news_search", usable_news)
    assert not _search_result_usable("news_search", '"Haber bulunamadı."')

    print("RESEARCH BUDGET: OK")


if __name__ == "__main__":
    main()
