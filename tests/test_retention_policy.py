import unittest

from arr_manager.retention.config import RetentionSettings
from arr_manager.retention.models import RetentionCandidate
from arr_manager.retention.policy import RetentionPolicy, SECONDS_PER_DAY, complete_days


class Addon:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def getSetting(self, key):
        return self.values.get(key, "")


def candidate(now, *, watched=True, added_days=30, watched_days=10,
              added=None, last_played=None):
    return RetentionCandidate(
        media_type="movie",
        kodi_db_ids=(1,),
        arr_id=2,
        file_id=3,
        title="Film",
        display_name="Film (2020)",
        watched=watched,
        date_added=(now - added_days * SECONDS_PER_DAY if added is None else added),
        last_played=(now - watched_days * SECONDS_PER_DAY if last_played is None else last_played),
    )


class RetentionConfigTests(unittest.TestCase):
    def test_safe_defaults_and_disabled_isolated(self):
        settings = RetentionSettings(Addon())
        self.assertFalse(settings.enabled)
        self.assertTrue(settings.include_movies)
        self.assertTrue(settings.include_episodes)
        self.assertTrue(settings.watched_only)
        self.assertEqual(settings.added_age_days, 30)
        self.assertEqual(settings.watched_age_days, 7)
        self.assertTrue(settings.background_dry_run)
        self.assertEqual(settings.max_deletions, 5)
        with self.assertRaisesRegex(Exception, "Retention is disabled"):
            settings.validate()

    def test_invalid_bounds_fail_when_feature_used(self):
        settings = RetentionSettings(Addon({
            "retention_enabled": "true",
            "retention_added_age_days": "10000",
            "retention_watched_age_days": "-1",
            "retention_max_deletions": "0",
        }))
        self.assertGreaterEqual(len(settings.errors), 3)
        with self.assertRaisesRegex(Exception, "between 0 and 9999"):
            settings.validate()

    def test_zero_and_9999_are_valid(self):
        settings = RetentionSettings(Addon({
            "retention_enabled": "true",
            "retention_added_age_days": "0",
            "retention_watched_age_days": "9999",
        }))
        settings.validate()
        self.assertEqual(settings.added_age_days, 0)
        self.assertEqual(settings.watched_age_days, 9999)

    def test_no_media_or_no_age_criterion_is_rejected(self):
        for values, text in [
            ({"retention_include_movies": "false", "retention_include_episodes": "false"}, "movies or episodes"),
            ({"retention_use_added_age": "false", "retention_use_watched_age": "false"}, "at least one age"),
        ]:
            with self.subTest(text=text):
                merged = {"retention_enabled": "true", **values}
                with self.assertRaisesRegex(Exception, text):
                    RetentionSettings(Addon(merged)).validate()


class RetentionPolicyTests(unittest.TestCase):
    NOW = 2_000_000_000.0

    def settings(self, **values):
        raw = {
            "retention_enabled": "true",
            "retention_include_movies": "true",
            "retention_include_episodes": "true",
            "retention_watched_only": "true",
            "retention_use_added_age": "true",
            "retention_added_age_days": "30",
            "retention_use_watched_age": "true",
            "retention_watched_age_days": "7",
            "retention_criteria_mode": "all",
        }
        raw.update({key: str(value).lower() if isinstance(value, bool) else str(value) for key, value in values.items()})
        return RetentionSettings(Addon(raw)).validate()

    def evaluate(self, item, **settings):
        return RetentionPolicy(self.settings(**settings), current_time=self.NOW).evaluate(item)

    def test_complete_days_uses_floor_at_boundaries(self):
        self.assertEqual(complete_days(self.NOW, self.NOW - SECONDS_PER_DAY), 1)
        self.assertEqual(complete_days(self.NOW, self.NOW - SECONDS_PER_DAY + 1), 0)
        self.assertIsNone(complete_days(self.NOW, self.NOW + 1))

    def test_watched_gate_is_independent(self):
        result = self.evaluate(candidate(self.NOW, watched=False))
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "not_watched")

    def test_all_and_any_modes(self):
        item = candidate(self.NOW, added_days=31, watched_days=2)
        self.assertFalse(self.evaluate(item).eligible)
        self.assertTrue(self.evaluate(item, retention_criteria_mode="any").eligible)

    def test_added_only_and_watched_only(self):
        item = candidate(self.NOW, added_days=31, watched_days=8)
        self.assertTrue(self.evaluate(item, retention_use_watched_age=False).eligible)
        self.assertTrue(self.evaluate(item, retention_use_added_age=False).eligible)

    def test_malformed_timestamps_fail_without_raising(self):
        settings = self.settings()
        item = candidate(self.NOW, added="not-a-date", last_played="also-bad")
        result = RetentionPolicy(settings, current_time=self.NOW).evaluate(item)
        self.assertFalse(result.eligible)
        self.assertIn("added_date_missing_or_invalid", result.failed_rules)
        self.assertIn("watched_date_missing_or_invalid", result.failed_rules)

    def test_zero_days_is_immediate_when_timestamp_exists(self):
        item = candidate(self.NOW, added=self.NOW, last_played=self.NOW)
        result = self.evaluate(
            item,
            retention_added_age_days=0,
            retention_watched_age_days=0,
        )
        self.assertTrue(result.eligible)

    def test_missing_and_future_dates_fail_with_reasons(self):
        missing = candidate(self.NOW, added=0, last_played=0)
        result = self.evaluate(missing)
        self.assertFalse(result.eligible)
        self.assertIn("added_date_missing_or_invalid", result.failed_rules)
        self.assertIn("watched_date_missing_or_invalid", result.failed_rules)

        future = candidate(self.NOW, added=self.NOW + 10, last_played=self.NOW + 20)
        result = self.evaluate(future)
        self.assertFalse(result.eligible)
        self.assertIn("added_date_in_future", result.failed_rules)
        self.assertIn("watched_date_in_future", result.failed_rules)

    def test_9999_day_threshold(self):
        old = candidate(self.NOW, added_days=10_000, watched_days=10_000)
        recent = candidate(self.NOW, added_days=9_998, watched_days=10_000)
        settings = {
            "retention_added_age_days": 9999,
            "retention_watched_age_days": 9999,
        }
        self.assertTrue(self.evaluate(old, **settings).eligible)
        self.assertFalse(self.evaluate(recent, **settings).eligible)


if __name__ == "__main__":
    unittest.main()
