import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.retention.auth import pin_generation
from arr_manager.retention.config import RetentionSettings
from arr_manager.retention.models import RetentionCandidate, RetentionEligibility, RetentionReportItem
from arr_manager.retention.service import RetentionService


def episode(db_id, season, episode_number, file_id=500, linked_episode_count=1):
    return RetentionCandidate(
        media_type="episode",
        db_id=db_id,
        arr_id=50,
        file_id=file_id,
        title="Episode",
        display_name=f"Show S{season:02d}E{episode_number:02d}",
        watched=True,
        last_played=1,
        date_added=1,
        tvshow_db_id=5,
        season=season,
        episode=episode_number,
        linked_episode_count=linked_episode_count,
    )


def movie(db_id, arr_id=60, file_id=600):
    return RetentionCandidate(
        media_type="movie",
        db_id=db_id,
        arr_id=arr_id,
        file_id=file_id,
        title="Movie",
        display_name=f"Movie {db_id}",
        watched=True,
        last_played=1,
        date_added=1,
    )


class Settings:
    pin_invalid = False
    pin_enabled = False
    pin_hash = b""
    pin_salt = b""


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
            "retention_periodic_enabled": "true",
            "retention_interval_hours": "24",
            "retention_max_deletions": "5",
            "retention_background_dry_run": "true",
            "retention_notification_mode": "errors_only",
        }
        self.values.update(values)

    def getLocalizedString(self, _string_id):
        return ""

    def getSetting(self, key):
        return self.values.get(key, "")

    def setSetting(self, key, value):
        self.values[key] = value


class Progress:
    def __init__(self):
        self.updates = []
        self.closed = False

    def update(self, percentage, message):
        self.updates.append((percentage, message))

    def iscanceled(self):
        return False

    def close(self):
        self.closed = True


class UI:
    monitor = None

    def __init__(self):
        self.progress_dialog = Progress()
        self.notifications = []

    def progress(self, _heading, _message):
        return self.progress_dialog

    def notification(self, message, **kwargs):
        self.notifications.append((message, kwargs))


class Logger:
    def error(self, *args):
        pass

    def exception(self, *args):
        pass


class Store:
    def __init__(self, fail_save=False):
        self.fail_save = fail_save
        self.lock_token = None
        self.saved = []
        self.released = False
        self.refreshes = 0

    def load_state(self):
        return {"auth_generation": "none", "next_due": 0.0}

    def acquire_lock(self):
        self.lock_token = "owner"
        return True

    def refresh_lock(self):
        self.refreshes += 1
        return True

    def save_state(self, generation, next_due):
        self.saved.append((generation, next_due))
        if self.fail_save:
            raise OSError("storage unavailable")

    def release_lock(self):
        self.released = True
        self.lock_token = None


class Executor:
    def __init__(self, results=None):
        self.calls = []
        self.results = list(results or [])

    def execute(self, candidate, dry_run):
        self.calls.append((candidate, dry_run))
        if self.results:
            return self.results.pop(0)
        return RetentionReportItem(
            candidate.media_type,
            candidate.display_name,
            candidate.db_id,
            True,
            "Criteria met",
            "dry_run" if dry_run else "deleted",
            committed=not dry_run,
        )


class RetentionServiceTests(unittest.TestCase):
    def test_shared_file_is_protected_when_any_linked_episode_is_protected(self):
        evaluated = [
            (episode(1, 1, 1, linked_episode_count=2), RetentionEligibility(True, "Criteria met")),
            (
                episode(2, 1, 2, linked_episode_count=2),
                RetentionEligibility(False, "Explicit episode exclusion"),
            ),
        ]
        protected = RetentionService._protect_shared_files(evaluated)
        self.assertFalse(protected[0][1].eligible)
        self.assertEqual(protected[0][1].reason, "Shared episode file contains a protected episode")
        self.assertFalse(protected[1][1].eligible)

    def test_shared_file_is_protected_when_a_linked_kodi_row_is_missing(self):
        evaluated = [
            (episode(1, 1, 1, linked_episode_count=2), RetentionEligibility(True, "Criteria met")),
        ]
        protected = RetentionService._protect_shared_files(evaluated)
        self.assertFalse(protected[0][1].eligible)
        self.assertEqual(
            protected[0][1].reason,
            "Shared episode file has missing or duplicate Kodi episode identities",
        )

    def test_duplicate_episode_identity_cannot_satisfy_shared_file_count(self):
        evaluated = [
            (episode(1, 1, 1, linked_episode_count=2), RetentionEligibility(True, "Criteria met")),
            (episode(2, 1, 1, linked_episode_count=2), RetentionEligibility(True, "Criteria met")),
        ]
        protected = RetentionService._protect_shared_files(evaluated)
        self.assertFalse(protected[0][1].eligible)
        self.assertFalse(protected[1][1].eligible)

    def test_distinct_episode_files_are_evaluated_independently(self):
        evaluated = [
            (episode(1, 1, 1, file_id=500), RetentionEligibility(True, "Criteria met")),
            (episode(2, 1, 2, file_id=501), RetentionEligibility(False, "Not watched")),
        ]
        protected = RetentionService._protect_shared_files(evaluated)
        self.assertTrue(protected[0][1].eligible)
        self.assertFalse(protected[1][1].eligible)

    def test_duplicate_movie_rows_protect_the_physical_radarr_target(self):
        evaluated = [
            (movie(1), RetentionEligibility(True, "Criteria met")),
            (movie(2), RetentionEligibility(True, "Criteria met")),
        ]
        protected = RetentionService._protect_duplicate_movies(evaluated)
        self.assertFalse(protected[0][1].eligible)
        self.assertFalse(protected[1][1].eligible)

    def test_missing_file_id_is_never_an_eligible_deletion_target(self):
        evaluated = [
            (episode(1, 1, 1, file_id=None), RetentionEligibility(True, "Criteria met")),
            (episode(2, 1, 2, file_id=501), RetentionEligibility(True, "Criteria met")),
        ]
        eligible = RetentionService._eligible_unique(evaluated)
        self.assertEqual([candidate.file_id for candidate in eligible], [501])

    def test_interactive_progress_reaches_100_percent(self):
        service = object.__new__(RetentionService)
        service.addon = Addon()
        service.ui = UI()
        service.store = Store()
        summary = service._run_pass(
            [episode(1, 1, 1), episode(2, 1, 2, file_id=501)],
            Executor(),
            dry_run=True,
            interactive=True,
        )
        self.assertEqual(service.ui.progress_dialog.updates[-1][0], 100)
        self.assertTrue(service.ui.progress_dialog.closed)
        self.assertEqual(summary["planned"], 2)

    def test_disable_check_stops_between_deletions(self):
        service = object.__new__(RetentionService)
        service.addon = Addon()
        service.ui = UI()
        service.store = Store()
        executor = Executor()
        checks = iter((True, False))
        summary = service._run_pass(
            [episode(1, 1, 1), episode(2, 1, 2, file_id=501)],
            executor,
            dry_run=False,
            interactive=False,
            continue_check=lambda: next(checks),
            refresh_lock=True,
        )
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(summary["deleted"], 1)
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(service.store.refreshes, 1)

    def test_committed_deletion_with_sync_error_counts_as_deleted_and_failed(self):
        service = object.__new__(RetentionService)
        service.addon = Addon()
        service.ui = UI()
        service.store = Store()
        result = RetentionReportItem(
            "movie",
            "Movie",
            1,
            True,
            "Criteria met",
            "deleted_with_error",
            "Kodi reconciliation failed",
            committed=True,
        )
        summary = service._run_pass(
            [movie(1)],
            Executor([result]),
            dry_run=False,
            interactive=False,
        )
        self.assertEqual(summary["deleted"], 1)
        self.assertEqual(summary["failed"], 1)

    def test_periodic_storage_failure_aborts_before_enumeration_and_disables_schedule(self):
        service = object.__new__(RetentionService)
        addon = Addon(retention_periodic_enabled="true")
        service.addon = addon
        service.ui = UI()
        service.logger = Logger()
        service.store = Store(fail_save=True)
        service.manager = type("Manager", (), {"settings": Settings()})()
        settings = RetentionSettings(addon).validate()
        service._components = lambda: (settings, object(), object(), Executor())
        service._evaluate = lambda *_args: self.fail("enumeration must not begin")
        self.assertIsNone(service.run_background())
        self.assertEqual(addon.getSetting("retention_periodic_enabled"), "false")
        self.assertTrue(service.store.released)

    def test_pin_generation_changes_with_pin_material(self):
        settings = Settings()
        self.assertEqual(pin_generation(settings), "none")
        settings.pin_enabled = True
        settings.pin_hash = b"a" * 32
        settings.pin_salt = b"b" * 16
        first = pin_generation(settings)
        settings.pin_hash = b"c" * 32
        second = pin_generation(settings)
        self.assertNotEqual(first, second)
        settings.pin_invalid = True
        self.assertEqual(pin_generation(settings), "invalid")


if __name__ == "__main__":
    unittest.main()
