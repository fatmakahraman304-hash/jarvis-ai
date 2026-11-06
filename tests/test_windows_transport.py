"""Windows-only Proactor reset filtering tests; safe to run on every platform."""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jarvis_transport_test_")

from run import _is_expected_proactor_reset  # noqa: E402


def _call_connection_lost():
    pass


def main():
    expected = ConnectionResetError(10054, "connection reset by peer")
    context = {"exception": expected, "handle": SimpleNamespace(_callback=_call_connection_lost)}
    assert _is_expected_proactor_reset(context)

    wrong_code = ConnectionResetError(10061, "connection refused")
    wrong_code_context = {"exception": wrong_code, "handle": SimpleNamespace(_callback=_call_connection_lost)}
    assert not _is_expected_proactor_reset(wrong_code_context)

    unrelated_callback = {"exception": expected, "message": "unrelated connection reset"}
    assert not _is_expected_proactor_reset(unrelated_callback)

    other_error = RuntimeError("unexpected failure")
    assert not _is_expected_proactor_reset({"exception": other_error, "handle": SimpleNamespace(_callback=_call_connection_lost)})

    print("WINDOWS TRANSPORT: OK")


if __name__ == "__main__":
    main()
