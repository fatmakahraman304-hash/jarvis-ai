"""Offline regressions for failed rollback and concurrent updater writes."""
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with tempfile.TemporaryDirectory(prefix="jv_recovery_") as data:
    os.environ["JARVIS_DATA"] = data
    from core import updater

    class RecoveryTests(unittest.TestCase):
        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.addCleanup(self.temp.cleanup)
            self.backups = Path(self.temp.name)
            self.patches = [patch.object(updater, "BACKUPS", self.backups),
                            patch.object(updater, "STATE", {}),
                            patch.object(updater.threading, "Timer")]
            for p in self.patches:
                p.start()
                self.addCleanup(p.stop)

        def test_missing_backup_does_not_restart_or_hold_lock(self):
            result = updater.rollback()
            self.assertEqual(result["durum"], "hata")
            updater.threading.Timer.assert_not_called()
            self.assertFalse(updater._lock.locked())

        def test_corrupt_backup_reports_error_and_releases_lock(self):
            (self.backups / "v1.zip").write_bytes(b"corrupt archive")
            result = updater.rollback()
            self.assertEqual(result["durum"], "hata")
            self.assertIn("geri yüklenemedi", result["hata"])
            self.assertEqual(updater.STATE["durum"], "hata")
            updater.threading.Timer.assert_not_called()
            self.assertFalse(updater._lock.locked())

        def test_rollback_rejected_while_update_holds_lock(self):
            with updater._lock, patch.object(updater, "restore") as restore:
                result = updater.rollback()
                self.assertEqual(result["durum"], "hata")
                restore.assert_not_called()
                updater.threading.Timer.assert_not_called()

        def test_update_and_second_rollback_rejected_during_restore(self):
            (self.backups / "v1.zip").touch()
            entered, release = threading.Event(), threading.Event()
            results = []

            def restore(path):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test did not release restore")
                return "restored"

            with patch.object(updater, "restore", side_effect=restore), patch.object(updater, "check") as check:
                thread = threading.Thread(target=lambda: results.append(updater.rollback()))
                thread.start()
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertEqual(updater.apply(restart=False)["durum"], "zaten güncelleniyor")
                    self.assertEqual(updater.rollback()["durum"], "hata")
                    check.assert_not_called()
                finally:
                    release.set()
                    thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(results[0]["durum"], "geri alındı")
            self.assertEqual(updater.STATE["ilerleme"], 100)
            updater.threading.Timer.return_value.start.assert_called_once()
            self.assertFalse(updater._lock.locked())

    if __name__ == "__main__":
        unittest.main()
