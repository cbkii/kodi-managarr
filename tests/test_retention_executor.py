import unittest
from unittest import mock

from arr_manager.retention.executor import RetentionExecutor
from arr_manager.retention.models import RetentionCandidate


class Settings:
    watched_only = True
    use_added_age = True
    added_age_days = 0
    use_watched_age = True
    watched_age_days = 0
    criteria_mode = "all"


class Manager:
    def __init__(self):
        self.radarr = mock.MagicMock()
        self.sonarr = mock.MagicMock()
        self.settings = type("S", (), {"path_mapper": object()})()
        self._plan_kodi = mock.MagicMock(return_value={"ok": True})
        self._sync_kodi = mock.MagicMock()
        self._record_transaction = mock.MagicMock()


class Enumerator:
    def __init__(self, fresh=None): self.fresh = fresh
    def revalidate(self, candidate): return self.fresh or candidate


def movie(**overrides):
    values = dict(
        media_type="movie", kodi_db_ids=(10,), arr_id=20, file_id=30,
        title="Film", display_name="Film (2020)", watched=True,
        last_played=1_600_000_000, date_added=1_600_000_000,
        unique_ids={"tmdb": "123"}, file_path="/movies/Film.mkv",
    )
    values.update(overrides)
    return RetentionCandidate(**values)


def episode(**overrides):
    values = dict(
        media_type="episode", kodi_db_ids=(11, 12), arr_id=21, file_id=31,
        title="Episode", display_name="Show S01E01, S01E02", watched=True,
        last_played=1_600_000_000, date_added=1_600_000_000,
        unique_ids={"tvdb": "456"}, linked_episode_ids=(101, 102),
        season=1, episode=1, tvshow_title="Show", file_path="/shows/a.mkv",
    )
    values.update(overrides)
    return RetentionCandidate(**values)


class RetentionExecutorTests(unittest.TestCase):
    def test_dry_run_never_revalidates_or_mutates(self):
        manager = Manager()
        enumerator = mock.MagicMock()
        result = RetentionExecutor(manager, enumerator).execute(movie(), Settings(), dry_run=True)
        self.assertEqual(result.action_taken, "dry_run")
        enumerator.revalidate.assert_not_called()
        manager.radarr.delete_movie.assert_not_called()

    def test_stale_candidate_stops_before_commit(self):
        manager = Manager()
        fresh = movie(watched=False)
        result = RetentionExecutor(manager, Enumerator(fresh)).execute(movie(), Settings())
        self.assertEqual(result.action_taken, "failed_before_commit")
        self.assertFalse(result.committed)
        manager.radarr.delete_movie.assert_not_called()

    def test_movie_uses_radarr_delete_exclusion_and_targeted_kodi_sync(self):
        manager = Manager()
        result = RetentionExecutor(manager, Enumerator()).execute(movie(), Settings())
        self.assertEqual(result.action_taken, "deleted")
        manager.radarr.delete_movie.assert_called_once_with(20, delete_files=True, add_exclusion=True)
        manager._plan_kodi.assert_called_once()
        manager._sync_kodi.assert_called_once()
        manager._record_transaction.assert_called_once()

    @mock.patch("arr_manager.retention.executor.resolve_episode_context")
    @mock.patch("arr_manager.retention.executor.resolve_series")
    def test_episode_unmonitors_all_linked_records_and_deletes_one_file(
        self, resolve_series, resolve_context
    ):
        manager = Manager()
        resolve_series.return_value = {"id": 21, "title": "Show"}
        linked = [
            {"id": 101, "monitored": True, "episodeFileId": 31},
            {"id": 102, "monitored": True, "episodeFileId": 31},
        ]
        resolve_context.return_value = (linked[0], linked, {"id": 31})
        result = RetentionExecutor(manager, Enumerator()).execute(episode(), Settings())
        self.assertEqual(result.action_taken, "deleted")
        manager.sonarr.set_episodes_monitored.assert_called_once_with([101, 102], False)
        manager.sonarr.delete_episode_file.assert_called_once_with(31)
        manager.sonarr.search_episodes.assert_not_called()
        manager.sonarr.delete_series.assert_not_called()

    @mock.patch("arr_manager.retention.executor.resolve_episode_context")
    @mock.patch("arr_manager.retention.executor.resolve_series")
    def test_episode_monitoring_is_restored_when_delete_fails_before_commit(
        self, resolve_series, resolve_context
    ):
        manager = Manager()
        resolve_series.return_value = {"id": 21, "title": "Show"}
        linked = [
            {"id": 101, "monitored": True, "episodeFileId": 31},
            {"id": 102, "monitored": False, "episodeFileId": 31},
        ]
        resolve_context.return_value = (linked[0], linked, {"id": 31})
        manager.sonarr.delete_episode_file.side_effect = RuntimeError("failed")
        result = RetentionExecutor(manager, Enumerator()).execute(episode(), Settings())
        self.assertEqual(result.action_taken, "failed_before_commit")
        self.assertEqual(
            manager.sonarr.set_episodes_monitored.call_args_list,
            [mock.call([101], False), mock.call([101], True)],
        )

    def test_kodi_failure_after_movie_delete_is_reported_as_committed(self):
        manager = Manager()
        manager._sync_kodi.side_effect = RuntimeError("Kodi failed")
        result = RetentionExecutor(manager, Enumerator()).execute(movie(), Settings())
        self.assertEqual(result.action_taken, "failed_after_commit")
        self.assertTrue(result.committed)
        self.assertIn("Radarr movie deletion and exclusion", result.stages)


if __name__ == "__main__":
    unittest.main()
