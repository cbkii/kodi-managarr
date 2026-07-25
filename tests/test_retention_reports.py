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
    store.lock_fd = None
    store.lock_backend = None
    store.lock_identity = None
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

    def test_report_is_bounded_to_100_results_and_2000_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            long_text = "x" * 2500
            report = {
                "run_type": "manual",
                "dry_run": True,
                "timestamp": 200.0,
                "deleted": 0,
                "planned": 105,
                "failed": 0,
                "skipped": 0,
                "results": [
                    {
                        "name": long_text,
                        "action": long_text,
                        "reason": long_text,
                        "error": long_text,
                    }
                    for _index in range(105)
                ],
            }
            store.save_report(report)
            loaded = store.load_report()
            self.assertEqual(len(loaded["results"]), 100)
            for result in loaded["results"]:
                for field in ("name", "action", "reason", "error"):
                    self.assertEqual(len(result[field]), 2000)

    def test_malformed_state_and_report_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            with open(store.state_file, "w", encoding="utf-8") as handle:
                json.dump({"auth_generation": 1, "next_due": "soon"}, handle)
            with open(store.report_file, "w", encoding="utf-8") as handle:
                json.dump({"run_type": "periodic", "dry_run": "false"}, handle)
            self.assertIsNone(store.load_state())
            self.assertEqual(store.load_report(), {})

    def test_active_kernel_lock_cannot_be_stolen_even_with_old_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            first = make_store(directory)
            second = make_store(directory)
            self.assertTrue(first.acquire_lock(stale_after=1))
            old = time.time() - 60
            os.utime(first.lock_file, (old, old))
            self.assertFalse(second.acquire_lock(stale_after=1))
            first.release_lock()
            self.assertTrue(second.acquire_lock(stale_after=1))
            second.release_lock()

    def test_unlocked_stale_file_is_reused_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            with open(store.lock_file, "w", encoding="utf-8") as handle:
                handle.write("crashed-owner")
            old = time.time() - 60
            os.utime(store.lock_file, (old, old))
            self.assertTrue(store.acquire_lock(stale_after=1))
            self.assertTrue(store.refresh_lock())
            store.release_lock()
            self.assertTrue(os.path.exists(store.lock_file))

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

    def test_previous_owner_cannot_release_new_owner_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            first = make_store(directory)
            second = make_store(directory)
            self.assertTrue(first.acquire_lock())
            first.release_lock()
            self.assertTrue(second.acquire_lock())
            second_token = second.lock_token
            first.release_lock()
            self.assertTrue(second.refresh_lock())
            self.assertEqual(second.lock_token, second_token)
            second.release_lock()

    @unittest.skipIf(os.name == "nt", "Windows does not allow replacing an open locked file")
    def test_external_path_replacement_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            self.assertTrue(store.acquire_lock())
            moved = store.lock_file + ".moved"
            os.replace(store.lock_file, moved)
            with open(store.lock_file, "w", encoding="utf-8") as handle:
                handle.write("foreign-lock")
            self.assertFalse(store.refresh_lock())
            store.release_lock()
            with open(store.lock_file, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "foreign-lock")


if __name__ == "__main__":
    unittest.main()
