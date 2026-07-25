import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import ConfigurationError
from arr_manager.retention.config import RetentionSettings, parse_exclusions
from arr_manager.retention.models import RetentionCandidate
from arr_manager.retention.policy import RetentionPolicy


class Addon:
    def __init__(self, **values):
        self.values = {
            "retention_enabled": "true",
            "retention_include_movies": "true",
            "retention_include_episodes": "true",
            "retention_watched_only": "true",
            "retention_use_added_age": "true",
            "retention_added_age_days": "30",
            "retention_use_watched_age": "true",
            "retention_watched_age_days": "30",
            "retention_criteria_mode": "all",
            "retention_movie_rating_threshold": "0",
            "retention_exclusions": "",
            "retention_manual_dry_run": "true",
            "retention_periodic_enabled": "false",
            "retention_interval_hours": "24",
            "retention_max_deletions": "5",
            "retention_background_dry_run": "true",
            "retention_notification_mode": "errors_only",
        }
        self.values.update(values)

    def getSetting(self, key):
        return self.values.get(key, "")


def movie(**values):
    defaults = {
        "media_type": "movie",
        "db_id": 10,
        "arr_id": 100,
        "file_id": 1000,
        "title": "Movie",
        "display_name": "Movie (2025)",
        "watched": True,
        "last_played": 100 * 86400,
        "date_added": 100 * 86400,
        "rating": 6.0,
    }
    defaults.update(values)
    return RetentionCandidate(**defaults)


def episode(**values):
    defaults = {
        "media_type": "episode",
        "db_id": 20,
        "arr_id": 200,
        "file_id": 2000,
        "title": "Episode",
        "display_name": "Show S02E03",
        "watched": True,
        "last_played": 100 * 86400,
        "date_added": 100 * 86400,
        "tvshow_db_id": 30,
        "season": 2,
        "episode": 3,
    }
    defaults.update(values)
    return RetentionCandidate(**defaults)


class RetentionConfigurationTests(unittest.TestCase):
    def test_exclusion_parser_supports_item_series_and_season_scopes(self):
        exclusions = parse_exclusions(
            "movie:10; episode:20, series:30\nseason:30:2"
        )
        self.assertEqual(exclusions["movie"], {10})
        self.assertEqual(exclusions["episode"], {20})
        self.assertEqual(exclusions["series"], {30})
        self.assertEqual(exclusions["season"], {(30, 2)})

    def test_malformed_exclusion_fails_closed(self):
        with self.assertRaises(ConfigurationError):
            RetentionSettings(Addon(retention_exclusions="Show Name"))
        with self.assertRaises(ConfigurationError):
            parse_exclusions("season:30:-1")

    def test_cleanup_defaults_are_dry_run_and_periodic_is_disabled(self):
        settings = RetentionSettings(Addon(
            retention_manual_dry_run="",
            retention_background_dry_run="",
            retention_periodic_enabled="",
        ))
        self.assertTrue(settings.manual_dry_run)
        self.assertTrue(settings.background_dry_run)
        self.assertFalse(settings.periodic_enabled)

    def test_at_least_one_age_criterion_is_required(self):
        with self.assertRaises(ConfigurationError):
            RetentionSettings(Addon(
                retention_use_added_age="false",
                retention_use_watched_age="false",
            )).validate()

    def test_malformed_protective_booleans_fail_closed(self):
        for setting_name in (
            "retention_watched_only",
            "retention_use_added_age",
            "retention_use_watched_age",
            "retention_manual_dry_run",
            "retention_background_dry_run",
        ):
            with self.subTest(setting=setting_name):
                with self.assertRaises(ConfigurationError):
                    RetentionSettings(Addon(**{setting_name: "definitely"}))

    def test_invalid_numeric_settings_fail_closed(self):
        cases = {
            "retention_added_age_days": ("unknown", "-1", "10000"),
            "retention_watched_age_days": ("unknown", "-1", "10000"),
            "retention_interval_hours": ("unknown", "0", "721"),
            "retention_max_deletions": ("unknown", "0", "101"),
        }
        for setting_name, values in cases.items():
            for value in values:
                with self.subTest(setting=setting_name, value=value):
                    with self.assertRaises(ConfigurationError):
                        RetentionSettings(Addon(**{setting_name: value}))

    def test_invalid_rating_thresholds_fail_closed(self):
        for value in ("unknown", "-1", "11", "nan", "inf", "-inf"):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    RetentionSettings(Addon(retention_movie_rating_threshold=value))

    def test_invalid_choice_settings_fail_closed(self):
        with self.assertRaises(ConfigurationError):
            RetentionSettings(Addon(retention_criteria_mode="sometimes"))
        with self.assertRaises(ConfigurationError):
            RetentionSettings(Addon(retention_notification_mode="loudly"))


class RetentionPolicyTests(unittest.TestCase):
    NOW = 200 * 86400

    def policy(self, **settings):
        return RetentionPolicy(RetentionSettings(Addon(**settings)).validate(), current_time=self.NOW)

    def test_all_enabled_age_rules_must_pass_by_default(self):
        policy = self.policy()
        self.assertTrue(policy.evaluate(movie()).eligible)
        self.assertFalse(policy.evaluate(movie(last_played=190 * 86400)).eligible)

    def test_any_mode_accepts_one_passing_age_rule(self):
        policy = self.policy(retention_criteria_mode="any")
        self.assertTrue(policy.evaluate(movie(last_played=190 * 86400)).eligible)

    def test_unwatched_media_is_protected(self):
        result = self.policy().evaluate(movie(watched=False, last_played=None))
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "Not watched")

    def test_movie_rating_threshold_protects_high_and_unknown_ratings(self):
        policy = self.policy(retention_movie_rating_threshold="7.5")
        self.assertFalse(policy.evaluate(movie(rating=8.0)).eligible)
        self.assertFalse(policy.evaluate(movie(rating=None)).eligible)
        self.assertTrue(policy.evaluate(movie(rating=7.0)).eligible)

    def test_missing_added_date_fails_closed(self):
        result = self.policy().evaluate(movie(date_added=None))
        self.assertFalse(result.eligible)
        self.assertIn("added_age_missing_date", result.failed_rules)

    def test_missing_last_played_date_fails_closed_for_watched_media(self):
        result = self.policy().evaluate(movie(watched=True, last_played=None))
        self.assertFalse(result.eligible)
        self.assertIn("watched_age_missing_date", result.failed_rules)

    def test_future_added_date_fails_closed(self):
        result = self.policy().evaluate(movie(date_added=self.NOW + 86400))
        self.assertFalse(result.eligible)
        self.assertIn("added_age_future_date", result.failed_rules)

    def test_future_last_played_date_fails_closed(self):
        result = self.policy().evaluate(movie(last_played=self.NOW + 86400))
        self.assertFalse(result.eligible)
        self.assertIn("watched_age_future_date", result.failed_rules)

    def test_explicit_movie_episode_series_and_season_exclusions_win(self):
        cases = [
            ("movie:10", movie()),
            ("episode:20", episode()),
            ("series:30", episode()),
            ("season:30:2", episode()),
        ]
        for exclusion, candidate in cases:
            with self.subTest(exclusion=exclusion):
                result = self.policy(retention_exclusions=exclusion).evaluate(candidate)
                self.assertFalse(result.eligible)
                self.assertIn("exclusion", result.reason.lower())


if __name__ == "__main__":
    unittest.main()
