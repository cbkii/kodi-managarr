import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import SafetyError
from arr_manager.retention.executor import RetentionExecutor, RetentionPostCommitError
from arr_manager.retention.models import RetentionCandidate


def movie(**values):
    defaults = {
        "media_type": "movie",
        "db_id": 1,
        "arr_id": 10,
        "file_id": 100,
        "title": "Movie",
        "display_name": "Movie",
        "watched": True,
        "last_played": 1,
        "date_added": 1,
    }
    defaults.update(values)
    return RetentionCandidate(**defaults)


def episode(**values):
    defaults = {
        "media_type": "episode",
        "db_id": 2,
        "arr_id": 20,
        "file_id": 200,
        "title": "Episode",
        "display_name": "Show S01E01",
        "watched": True,
        "last_played": 1,
        "date_added": 1,
        "season": 1,
        "episode": 1,
        "tvshow_db_id": 30,
        "series_title": "Show",
    }
    defaults.update(values)
    return RetentionCandidate(**defaults)


class Radarr:
    def __init__(self):
        self.deleted = []

    def delete_movie(self, movie_id, delete_files, add_exclusion):
        self.deleted.append((movie_id, delete_files, add_exclusion))


class Sonarr:
    def __init__(self, delete_error=None):
        self.monitor_calls = []
        self.delete_calls = []
        self.delete_error = delete_error

    def set_episodes_monitored(self, episode_ids, monitored):
        self.monitor_calls.append((list(episode_ids), monitored))

    def delete_episode_file(self, file_id):
        self.delete_calls.append(file_id)
        if self.delete_error:
            raise self.delete_error


class Manager:
    def __init__(self, sync_error=None, delete_error=None):
        self.radarr = Radarr()
        self.sonarr = Sonarr(delete_error)
        self.sync_error = sync_error
        self.sync_calls = []

    def _plan_kodi(self, *args, **kwargs):
        return {"plan": True}

    def _sync_kodi(self, *args, **kwargs):
        self.sync_calls.append((args, kwargs))
        if self.sync_error:
            raise self.sync_error


class Kodi:
    def call(self, *_args, **_kwargs):
        raise AssertionError("Kodi must not be called")


class Policy:
    def evaluate(self, _candidate):
        return type("Result", (), {"eligible": True})()


class Enumerator:
    MOVIE_PROPS = []
    EPISODE_PROPS = []


class RetentionExecutorTests(unittest.TestCase):
    def executor(self, manager=None):
        return RetentionExecutor(manager or Manager(), Kodi(), Enumerator(), Policy())

    def test_missing_file_id_fails_before_any_api_call(self):
        result = self.executor().execute(movie(file_id=None), dry_run=False)
        self.assertEqual(result.action_taken, "failed")
        self.assertFalse(result.committed)
        self.assertIn("positive ID", result.error_message)

    def test_post_commit_failure_is_reported_as_deleted(self):
        executor = self.executor()
        candidate = movie()
        with mock.patch.object(executor, "_revalidate_movie", return_value=candidate), \
             mock.patch.object(
                 executor,
                 "_delete_movie",
                 side_effect=RetentionPostCommitError(
                     "Movie was deleted from Radarr, but Kodi reconciliation failed"
                 ),
             ):
            result = executor.execute(candidate, dry_run=False)
        self.assertTrue(result.committed)
        self.assertEqual(result.action_taken, "deleted_with_error")
        self.assertTrue(result.error_message)

    def test_movie_kodi_sync_failure_crosses_commit_boundary(self):
        manager = Manager(sync_error=RuntimeError("sync failed"))
        executor = self.executor(manager)
        with self.assertRaises(RetentionPostCommitError):
            executor._delete_movie(movie())
        self.assertEqual(manager.radarr.deleted, [(10, True, True)])

    def test_episode_delete_error_never_reenables_monitoring(self):
        manager = Manager(delete_error=TimeoutError("ambiguous timeout"))
        executor = self.executor(manager)
        linked = [{"id": 201, "monitored": True}]
        with self.assertRaises(SafetyError):
            executor._delete_episode_file(episode(), linked)
        self.assertEqual(manager.sonarr.monitor_calls, [([201], False)])
        self.assertEqual(manager.sonarr.delete_calls, [200])

    def test_episode_sync_failure_is_post_commit(self):
        manager = Manager(sync_error=RuntimeError("sync failed"))
        executor = self.executor(manager)
        linked = [{"id": 201, "monitored": True}]
        with self.assertRaises(RetentionPostCommitError):
            executor._delete_episode_file(episode(), linked)
        self.assertEqual(manager.sonarr.monitor_calls, [([201], False)])
        self.assertEqual(manager.sonarr.delete_calls, [200])


if __name__ == "__main__":
    unittest.main()
