import json
import os
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.retention.reports import RetentionStateStore


def make_store(directory):
    store = object.__new__(RetentionStateStore)
    store.profile = directory
    store.state_file = os.path.join(directory, "retention-state.json")
    store.report_file = os.path.join(directory, "retention-last-report.json")
    store.lock_file = os.path.join(directory, "retention.lock")
    store.lock_token = None
    return store


class RetentionStateStoreTests(unittest.TestCase):
    def test_state_and_report_round_trip_with_schema_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            store.save_state("generation", 123.5)
            self.assertEqual(store.load_state(), {
                "auth_generation": "generation",
                "next_due": 123.5,
            })
            report = {
                "run_type": "periodic",
                "dry_run": False,
                "timestamp": 200.0,
                "deleted": 1,
                "planned": 0,
                "failed": 1,
                "skipped": 2,
                "results": [{
                    "name": "Movie",
                    "action": "deleted_with_error",
                    "reason": "Criteria met",
                    "error": "Kodi reconciliation failed",
                }],
            }
            store.save_report(report)
            self.assertEqual(store.load_report(), report)
            self.assertFalse(any(name.endswith(".tmp") for name in os.listdir(directory)))

    def test_malformed_state_and_report_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            with open(store.state_file, "w", encoding="utf-8") as handle:
                json.dump({"auth_generation": 1, "next_due": "soon"}, handle)
            with open(store.report_file, "w", encoding="utf-8") as handle:
                json.dump({"run_type": "periodic", "dry_run": "false"}, handle)
            self.assertIsNone(store.load_state())
            self.assertEqual(store.load_report(), {})

    def test_stale_takeover_cannot_be_released_by_previous_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            first = make_store(directory)
            second = make_store(directory)
            self.assertTrue(first.acquire_lock(stale_after=1))
            old = time.time() - 60
            os.utime(first.lock_file, (old, old))
            self.assertTrue(second.acquire_lock(stale_after=1))
            second_token = second.lock_token
            first.release_lock()
            self.assertTrue(os.path.exists(second.lock_file))
            with open(second.lock_file, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read().strip(), second_token)
            second.release_lock()
            self.assertFalse(os.path.exists(second.lock_file))

    def test_refresh_keeps_long_running_owner_live(self):
        with tempfile.TemporaryDirectory() as directory:
            first = make_store(directory)
            second = make_store(directory)
            self.assertTrue(first.acquire_lock(stale_after=1))
            old = time.time() - 60
            os.utime(first.lock_file, (old, old))
            self.assertTrue(first.refresh_lock())
            self.assertFalse(second.acquire_lock(stale_after=1))
            first.release_lock()

    def test_release_does_not_remove_foreign_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            store.lock_token = "old-owner"
            with open(store.lock_file, "w", encoding="utf-8") as handle:
                handle.write("new-owner")
            store.release_lock()
            self.assertTrue(os.path.exists(store.lock_file))


if __name__ == "__main__":
    unittest.main()
