import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.actions import ArrManager
from arr_manager.errors import SafetyError
from arr_manager.models import SelectedItem
from arr_manager.util import PathMapper


class Settings:
    backend = "vfs"; confirm = False; dry_run = False; require_blocklist = False; poll_timeout = 1
    protected_paths = []
    def __init__(self, mappings): self.path_mapper = PathMapper(mappings)
    def validate_backend(self): return None


class Backend:
    def __init__(self): self.preflighted = []; self.deleted = []
    def preflight_file(self, path): self.preflighted.append(path)
    def delete_file(self, path): self.deleted.append(path)
    def close(self): pass


class UI:
    def __init__(self): self.affected = None
    def confirm(self, heading, message): return True
    def wait_for_abort(self, seconds): return False
    def sync_deleted_episodes(self, selected, linked=None): self.affected = list(linked or [])


class Sonarr:
    def __init__(self, files, episodes): self.files = files; self.episode_rows = episodes
    def episode_files(self, series_id): return [] if getattr(self, "deleted", False) else self.files
    def episodes(self, series_id): return self.episode_rows
    def series_history(self, series_id, event_type=3): return []
    def rescan_series(self, series_id): self.deleted = True; return {"id": 1}
    def command_status(self, command_id): return {"id": command_id, "status": "completed", "result": "successful"}
    def search_series(self, series_id): return {"id": 2}


class ActionPathTests(unittest.TestCase):
    def test_series_replace_syncs_only_episodes_tied_to_deleted_files(self):
        backend = Backend(); ui = UI()
        settings = Settings([("/media/Shows", "sftp://pi/media/Shows")])
        manager = ArrManager(settings, ui, None)
        manager._sonarr = Sonarr(
            [{"id": 7, "path": "/media/Shows/Show/Episode.mkv"}],
            [{"id": 11, "episodeFileId": 7, "seasonNumber": 1, "episodeNumber": 1},
             {"id": 12, "episodeFileId": 0, "seasonNumber": 1, "episodeNumber": 2}],
        )
        with patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 3, "title": "Show", "path": "/media/Shows/Show"}), \
             patch("arr_manager.actions_destructive.make_direct_backend", return_value=backend):
            manager._series_replace(SelectedItem(media_type="tvshow", title="Show"))
        self.assertEqual(backend.preflighted, ["sftp://pi/media/Shows/Show/Episode.mkv"])
        self.assertEqual([item["id"] for item in ui.affected], [11])

    def test_backend_path_rejects_mapping_root(self):
        manager = ArrManager(Settings([("/media/Shows", "smb://pi/Shows")]), UI(), None)
        with self.assertRaisesRegex(SafetyError, "mapping root"):
            manager._backend_path("/media/Shows")

    def test_remote_file_path_rejects_incomplete_record(self):
        with self.assertRaises(SafetyError):
            ArrManager._remote_file_path("", {"relativePath": "file.mkv"})


if __name__ == "__main__":
    unittest.main()
