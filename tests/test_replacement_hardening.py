import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.actions import ArrManager
from arr_manager.diagnostics_hardening import normalise_transaction_candidate
from arr_manager.errors import SafetyError
from arr_manager.models import SelectedItem
from arr_manager.util import PathMapper


class Settings:
    backend = "api"
    confirm = False
    dry_run = False
    require_blocklist = False
    poll_timeout = 1
    path_mapper = PathMapper([])


class UI:
    def __init__(self, approved=True):
        self.approved = approved
        self.records = []
        self.confirm_calls = []

    def confirm(self, heading, message):
        self.confirm_calls.append((heading, message))
        return self.approved

    def record_transaction(self, transaction, exc=None):
        self.records.append(transaction.as_dict(exc))

    def wait_for_abort(self, seconds):
        return False


class MovieRecoveryClient:
    def __init__(self, response=None):
        self.response = response or {"id": 41, "status": "queued"}
        self.calls = []

    def movie_files(self, movie_id):
        self.calls.append(("files", movie_id))
        return []

    def search_movie(self, movie_id):
        self.calls.append(("search", movie_id))
        return self.response


class EpisodeRecoveryClient:
    def __init__(self, response=None):
        self.response = response or {"id": 42, "status": "queued"}
        self.calls = []

    def episodes(self, series_id, season=None):
        self.calls.append(("episodes", series_id, season))
        return [{"id": 77, "seasonNumber": 0, "episodeNumber": 1, "episodeFileId": 0}]

    def search_episodes(self, episode_ids):
        self.calls.append(("search", list(episode_ids)))
        return self.response


class SeriesClient:
    def __init__(self, response=None):
        self.response = response or {"id": 91, "status": "queued"}
        self.calls = []

    def delete_episode_files(self, file_ids):
        self.calls.append(("delete", list(file_ids)))

    def search_series(self, series_id):
        self.calls.append(("search", series_id))
        return self.response

    def mark_history_failed(self, history_id):
        self.calls.append(("blocklist", history_id))


class ReplacementHardeningTests(unittest.TestCase):
    def manager(self, settings=None, ui=None):
        return ArrManager(settings or Settings(), ui or UI(), logger=None)

    def test_movie_recovery_dry_run_has_no_search_side_effect(self):
        settings = Settings()
        settings.dry_run = True
        ui = UI()
        manager = self.manager(settings, ui)
        manager._radarr = MovieRecoveryClient()
        selected = SelectedItem(media_type="movie", title="Film")
        with patch("arr_manager.actions_destructive.resolve_movie", return_value={"id": 3, "title": "Film"}):
            result = manager._movie_replace(selected)
        self.assertIn("Dry run", result)
        self.assertEqual(manager._radarr.calls, [("files", 3)])
        self.assertEqual(ui.records, [])

    def test_movie_recovery_cancellation_has_no_search_side_effect(self):
        settings = Settings()
        settings.confirm = True
        ui = UI(approved=False)
        manager = self.manager(settings, ui)
        manager._radarr = MovieRecoveryClient()
        selected = SelectedItem(media_type="movie", title="Film")
        with patch("arr_manager.actions_destructive.resolve_movie", return_value={"id": 3, "title": "Film"}):
            result = manager._movie_replace(selected)
        self.assertEqual(result, "Cancelled")
        self.assertEqual(manager._radarr.calls, [("files", 3)])
        self.assertEqual(len(ui.confirm_calls), 1)
        self.assertEqual(ui.records, [])

    def test_episode_recovery_dry_run_has_no_search_side_effect(self):
        settings = Settings()
        settings.dry_run = True
        ui = UI()
        manager = self.manager(settings, ui)
        manager._sonarr = EpisodeRecoveryClient()
        selected = SelectedItem(media_type="episode", tvshow_title="Show", season=0, episode=1)
        with patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 7, "title": "Show"}):
            result = manager._episode_replace(selected)
        self.assertIn("Dry run", result)
        self.assertEqual(manager._sonarr.calls, [("episodes", 7, 0)])
        self.assertEqual(ui.records, [])

    def test_rejected_recovery_search_records_submission_stage(self):
        ui = UI()
        manager = self.manager(ui=ui)
        manager._radarr = MovieRecoveryClient({"id": 41, "status": "failed"})
        selected = SelectedItem(media_type="movie", title="Film")
        with patch("arr_manager.actions_destructive.resolve_movie", return_value={"id": 3, "title": "Film"}):
            with self.assertRaisesRegex(SafetyError, "replacement search submission"):
                manager._movie_replace(selected)
        record = ui.records[-1]
        self.assertFalse(record["committed"])
        self.assertEqual(record["failedStage"], "replacement search submission")

    def test_multi_episode_series_records_queued_command_and_stages(self):
        ui = UI()
        manager = self.manager(ui=ui)
        manager._sonarr = SeriesClient()
        manager._sync_kodi = lambda *args, **kwargs: None
        selected = SelectedItem(media_type="tvshow", title="Show")
        files = [{"id": 10}, {"id": 11}]
        affected = [
            {"id": 70, "episodeFileId": 10},
            {"id": 71, "episodeFileId": 11},
        ]
        manager._execute_series_replacement(
            selected,
            {"id": 7, "title": "Show"},
            files,
            affected,
            {"kind": "episodes", "ids": [1, 2]},
            [],
            None,
            [],
        )
        record = ui.records[-1]
        self.assertEqual(record["commandId"], 91)
        self.assertEqual(record["commandStatus"], "queued")
        self.assertEqual(
            record["stages"],
            ["release blocklists", "episode file deletion", "replacement search queued", "Kodi library synchronisation"],
        )
        self.assertTrue(record["committed"])
        self.assertEqual(manager._sonarr.calls, [("delete", [10, 11]), ("search", 7)])

    def test_series_search_rejection_reports_search_stage_after_commit(self):
        ui = UI()
        manager = self.manager(ui=ui)
        manager._sonarr = SeriesClient({"id": 91, "status": "failed"})
        manager._sync_kodi = lambda *args, **kwargs: None
        with self.assertRaisesRegex(SafetyError, "replacement search submission"):
            manager._execute_series_replacement(
                SelectedItem(media_type="tvshow", title="Show"),
                {"id": 7, "title": "Show"},
                [{"id": 10}],
                [{"id": 70, "episodeFileId": 10}],
                {"kind": "episodes", "ids": [1]},
                [],
                None,
                [],
            )
        record = ui.records[-1]
        self.assertTrue(record["committed"])
        self.assertEqual(record["failedStage"], "replacement search submission")

    def test_kodi_sync_failure_reports_kodi_stage_with_command_evidence(self):
        ui = UI()
        manager = self.manager(ui=ui)
        manager._sonarr = SeriesClient()

        def fail_sync(*args, **kwargs):
            raise SafetyError("sync failed")

        manager._sync_kodi = fail_sync
        with self.assertRaisesRegex(SafetyError, "Kodi library synchronisation"):
            manager._execute_series_replacement(
                SelectedItem(media_type="tvshow", title="Show"),
                {"id": 7, "title": "Show"},
                [{"id": 10}],
                [{"id": 70, "episodeFileId": 10}],
                {"kind": "episodes", "ids": [1]},
                [],
                None,
                [],
            )
        record = ui.records[-1]
        self.assertEqual(record["failedStage"], "Kodi library synchronisation")
        self.assertEqual(record["commandId"], 91)
        self.assertTrue(record["committed"])


class DiagnosticsNormalisationTests(unittest.TestCase):
    def test_malformed_fields_fall_back_independently(self):
        candidate = normalise_transaction_candidate(
            {
                "operation": "episode replacement",
                "stages": None,
                "commandId": {"bad": "value"},
                "failedStage": "replacement search submission",
            }
        )
        self.assertEqual(candidate["operation"], "episode replacement")
        self.assertEqual(candidate["stages"], [])
        self.assertEqual(candidate["commandId"], 0)
        self.assertEqual(candidate["failedStage"], "replacement search submission")

    def test_valid_fields_are_bounded_and_preserved(self):
        candidate = normalise_transaction_candidate(
            {"stages": ["one", 2, "two"] + ["x"] * 30, "commandId": "42"}
        )
        self.assertEqual(candidate["commandId"], 42)
        self.assertEqual(candidate["stages"][:2], ["one", "two"])
        self.assertEqual(len(candidate["stages"]), 20)

    def test_boolean_command_id_is_not_accepted_as_integer(self):
        self.assertEqual(normalise_transaction_candidate({"commandId": True})["commandId"], 0)


if __name__ == "__main__":
    unittest.main()
