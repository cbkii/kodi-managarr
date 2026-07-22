import unittest
import time
from arr_manager.retention.models import RetentionCandidate
from arr_manager.retention.policy import RetentionPolicy
from arr_manager.retention.config import RetentionSettings
from unittest.mock import MagicMock
class MockAddon:
    def getSetting(self, key):
        return ''

class TestRetentionPolicy(unittest.TestCase):
    def setUp(self):
        self.settings = RetentionSettings(MockAddon())
        self.now = 1000000000
        self.policy = RetentionPolicy(self.settings, current_time=self.now)
        self.SECONDS_PER_DAY = 86400

    def get_candidate(self, watched=True, age_added_days=10, age_watched_days=10, has_added_date=True, has_watched_date=True):
        added_ts = self.now - (age_added_days * self.SECONDS_PER_DAY) if has_added_date else None
        watched_ts = self.now - (age_watched_days * self.SECONDS_PER_DAY) if has_watched_date else None
        return RetentionCandidate(
            media_type="movie",
            db_id=1,
            arr_id=1,
            file_id=1,
            title="Test Movie",
            display_name="Test Movie (2020)",
            watched=watched,
            last_played=watched_ts,
            date_added=added_ts
        )

    def test_watched_only_gate(self):
        self.settings.watched_only = True
        cand = self.get_candidate(watched=False)
        result = self.policy.evaluate(cand)
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "Not watched")

    def test_no_enabled_criteria(self):
        self.settings.use_added_age = False
        self.settings.use_watched_age = False
        cand = self.get_candidate()
        result = self.policy.evaluate(cand)
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "No enabled criteria")

    def test_all_mode_success(self):
        self.settings.use_added_age = True
        self.settings.added_age_days = 5
        self.settings.use_watched_age = True
        self.settings.watched_age_days = 5
        self.settings.criteria_mode = "all"

        cand = self.get_candidate(age_added_days=6, age_watched_days=6)
        result = self.policy.evaluate(cand)
        self.assertTrue(result.eligible)

    def test_all_mode_partial_fail(self):
        self.settings.use_added_age = True
        self.settings.added_age_days = 5
        self.settings.use_watched_age = True
        self.settings.watched_age_days = 10
        self.settings.criteria_mode = "all"

        # added passes, watched fails
        cand = self.get_candidate(age_added_days=6, age_watched_days=6)
        result = self.policy.evaluate(cand)
        self.assertFalse(result.eligible)

    def test_any_mode_partial_success(self):
        self.settings.use_added_age = True
        self.settings.added_age_days = 5
        self.settings.use_watched_age = True
        self.settings.watched_age_days = 10
        self.settings.criteria_mode = "any"

        # added passes, watched fails, but ANY means it's eligible
        cand = self.get_candidate(age_added_days=6, age_watched_days=6)
        result = self.policy.evaluate(cand)
        self.assertTrue(result.eligible)

    def test_any_mode_fail(self):
        self.settings.use_added_age = True
        self.settings.added_age_days = 10
        self.settings.use_watched_age = True
        self.settings.watched_age_days = 10
        self.settings.criteria_mode = "any"

        cand = self.get_candidate(age_added_days=6, age_watched_days=6)
        result = self.policy.evaluate(cand)
        self.assertFalse(result.eligible)

    def test_zero_days_means_immediate(self):
        self.settings.use_added_age = True
        self.settings.added_age_days = 0
        self.settings.use_watched_age = False
        cand = self.get_candidate(age_added_days=0) # 0 age
        result = self.policy.evaluate(cand)
        self.assertTrue(result.eligible)

    def test_missing_dates(self):
        self.settings.use_added_age = True
        self.settings.added_age_days = 5
        self.settings.use_watched_age = True
        self.settings.watched_age_days = 5
        self.settings.criteria_mode = "all"

        cand = self.get_candidate(has_added_date=False, has_watched_date=False)
        result = self.policy.evaluate(cand)
        self.assertFalse(result.eligible)
        self.assertIn("added_age_missing_date", result.failed_rules)
        self.assertIn("watched_age_missing_date", result.failed_rules)

    def test_future_dates(self):
        self.settings.use_added_age = True
        self.settings.added_age_days = 5
        cand = self.get_candidate(age_added_days=-5) # Future date
        result = self.policy.evaluate(cand)
        self.assertFalse(result.eligible)
        self.assertIn("added_age_future_date", result.failed_rules)

    def test_watched_age_but_unwatched(self):
        self.settings.watched_only = False # explicitly allow unwatched
        self.settings.use_watched_age = True
        self.settings.use_added_age = False
        cand = self.get_candidate(watched=False)
        result = self.policy.evaluate(cand)
        self.assertFalse(result.eligible)
        self.assertIn("watched_age_not_watched", result.failed_rules)

    def test_9999_days(self):
        self.settings.use_added_age = True
        self.settings.added_age_days = 9999
        self.settings.use_watched_age = False
        cand = self.get_candidate(age_added_days=10000)
        result = self.policy.evaluate(cand)
        self.assertTrue(result.eligible)

        cand = self.get_candidate(age_added_days=9998)
        result = self.policy.evaluate(cand)
        self.assertFalse(result.eligible)

if __name__ == "__main__":
    unittest.main()
