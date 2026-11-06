"""Offline scheduling regression tests; no model or scheduled prompt is executed."""
import datetime as dt
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_tmp = tempfile.TemporaryDirectory(prefix="jarvis_schedule_")
os.environ["JARVIS_DATA"] = _tmp.name
from core.skills import automation as a


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        a.memory._q("DELETE FROM tasks", commit=True)
        self.clock = patch.object(a.time, "time", return_value=dt.datetime(2026, 1, 30, 10).timestamp())
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_weekend_and_month_end(self):
        self.assertEqual(a.schedule_preview(kind="weekdays", at="09:00", count=2)["çalışma_zamanları"],
                         ["02.02.2026 09:00", "03.02.2026 09:00"])
        self.assertEqual(a.schedule_preview(kind="monthly", monthday=31, count=3)["çalışma_zamanları"],
                         ["31.01.2026 09:00", "31.03.2026 09:00", "31.05.2026 09:00"])

    def test_weekly_interval_and_once(self):
        self.assertEqual(a.schedule_preview(kind="weekly", weekday="pazartesi", count=1)["çalışma_zamanları"], ["02.02.2026 09:00"])
        self.assertEqual(a.schedule_preview(kind="interval", every_minutes=30, count=2)["çalışma_zamanları"],
                         ["30.01.2026 10:30", "30.01.2026 11:00"])
        self.assertEqual(len(a.schedule_preview(kind="once", date="2026-02-01")["çalışma_zamanları"]), 1)
        self.assertEqual(a.memory._q("SELECT * FROM tasks"), [])

    def test_invalid_never_persisted(self):
        for kwargs in ({"at": "25:00"}, {"kind": "invalid"}, {"kind": "weekly", "weekday": "oops"},
                       {"kind": "monthly", "monthday": 1.5}, {"kind": "monthly", "monthday": 32},
                       {"kind": "once", "date": "2020-01-01"},
                       *({"kind": "interval", "every_minutes": n} for n in [0, -1, float("nan"), float("inf"), 525601])):
            with self.subTest(kwargs=kwargs):
                self.assertIsInstance(a.schedule_preview(**kwargs), str)
                self.assertIn("kurulmadı", a.schedule_task("brifing", **kwargs))
        self.assertEqual(a.memory._q("SELECT * FROM tasks"), [])

    def test_persistence_matches_preview(self):
        kwargs = dict(kind="weekly", weekday="cuma", at="11:00")
        preview = a.schedule_preview(**kwargs)
        self.assertIn("kuruldu", a.schedule_task("brifing", **kwargs))
        row = a.memory._q("SELECT * FROM tasks", one=True)
        self.assertEqual(dt.datetime.fromtimestamp(row["next_run"]).strftime("%d.%m.%Y %H:%M"), preview["çalışma_zamanları"][0])
        for count in [0, 11, 1.5, float("nan")]:
            self.assertIsInstance(a.schedule_preview(count=count), str)


if __name__ == "__main__":
    unittest.main()
