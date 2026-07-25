import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.actions import ArrManager
from arr_manager.errors import SafetyError
from arr_manager.kodi_jsonrpc import KodiJsonRpcError
from arr_manager.models import SelectedItem
from arr_manager.util import PathMapper


class Settings:
    backend = "api"
    confirm = False
    dry_run = False
    require_blocklist = True
    poll_timeout = 1
    path_mapper = PathMapper([])


class UI:
    def __init__(self):
        self.records = []

    def record_transaction(self, transaction, exc=None):
        self.records.append(transaction.as_dict(exc))

    def wait_for_abort(self, seconds):
        return False


class MovieRecoveryClient:
    def __init__(self):
        self.calls = []

    def movie_files(self, movie_id):
        self.calls.append(("files", movie_id))
        return []

    def search_movie(self, movie_id):
        self.calls.append(("search", movie_id))
        return {"id": 41, "status": "queued"}


class EpisodeRecoveryClient:
    def __init__(self):
        self.calls = []

    def episodes(self, series_id, season=None):
        self.calls.append(("episodes", series_id, season))
        return [{"id": 77, "seasonNumber": 0, "episodeNumber": 1, "episodeFileId": 0}]

    def search_episodes(self, episode_ids):
        self.calls.append(("search", list(episode_ids)))
        return {"id": 42, "status": "queued"}


class ReplacementReliabilityTests(unittest.TestCase):
    def test_missing_movie_recovery_only_queues_search(self):
        ui = UI()
        manager = ArrManager(Settings(), ui, logger=None)
        manager._radarr = MovieRecoveryClient()
        selected = SelectedItem(media_type="movie", title="Film")
        with patch(
            "arr_manager.actions_destructive.resolve_movie",
            return_value={"id": 3, "title": "Film"},
        ):
            result = manager._movie_replace(selected)
        self.assertIn("already missing", result)
        self.assertEqual(manager._radarr.calls, [("files", 3), ("search", 3)])
        self.assertEqual(ui.records[-1]["commandId"], 41)
        self.assertFalse(ui.records[-1]["committed"])

    def test_missing_special_episode_recovery_only_queues_search(self):
        ui = UI()
        manager = ArrManager(Settings(), ui, logger=None)
        manager._sonarr = EpisodeRecoveryClient()
        selected = SelectedItem(
            media_type="episode", tvshow_title="Show", season=0, episode=1
        )
        with patch(
            "arr_manager.actions_destructive.resolve_series",
            return_value={"id": 7, "title": "Show"},
        ):
            result = manager._episode_replace(selected)
        self.assertIn("already missing", result)
        self.assertEqual(
            manager._sonarr.calls,
            [("episodes", 7, 0), ("search", [77])],
        )
        self.assertEqual(ui.records[-1]["commandId"], 42)
        self.assertFalse(ui.records[-1]["committed"])

    def test_kodi_preflight_error_is_recorded_before_commit(self):
        ui = UI()

        def fail(_selected, _linked):
            raise KodiJsonRpcError(
                "Invalid params.",
                method="VideoLibrary.GetEpisodes",
                code=-32602,
                safe_data={"property": "bad"},
            )

        ui.plan_deleted_episodes = fail
        manager = ArrManager(Settings(), ui, logger=None)
        with self.assertRaisesRegex(SafetyError, "before destructive changes"):
            manager._plan_kodi(
                "episodes",
                SelectedItem(media_type="episode"),
                [{"seasonNumber": 1, "episodeNumber": 2}],
            )
        record = ui.records[-1]
        self.assertFalse(record["committed"])
        self.assertEqual(record["failedStage"], "Kodi cleanup preflight")
        self.assertEqual(record["kodiJsonRpcMethod"], "VideoLibrary.GetEpisodes")
        self.assertEqual(record["kodiJsonRpcCode"], -32602)
        self.assertEqual(record["kodiJsonRpcData"], {"property": "bad"})


if __name__ == "__main__":
    unittest.main()
