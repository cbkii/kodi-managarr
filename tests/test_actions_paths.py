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


class FakeSettings:
    backend = "vfs"
    confirm = False
    dry_run = False
    require_blocklist = False
    poll_timeout = 1

    def __init__(self, mappings=None):
        self.path_mapper = PathMapper(mappings or [])


class FakeBackend:
    name = "Kodi VFS (SMB/SFTP)"

    def __init__(self):
        self.deleted = []

    def delete_file(self, path):
        self.deleted.append(path)

    def close(self):
        return None


class FakeSonarr:
    def __init__(self, files, backend):
        self.files = list(files)
        self.backend = backend
        self.rescanned = []
        self.searched = []

    def episode_files(self, series_id):
        return [] if self.backend.deleted else list(self.files)

    def episodes(self, series_id):
        return [{"id": 11, "episodeFileId": self.files[0]["id"]}]

    def series_history(self, series_id, event_type=None):
        return []

    def rescan_series(self, series_id):
        self.rescanned.append(series_id)
        return {"id": 101}

    def command_status(self, command_id):
        return {"id": command_id, "status": "completed"}

    def search_series(self, series_id):
        self.searched.append(series_id)
        return {"id": 102}


class FakeUI:
    def __init__(self):
        self.series_syncs = 0
        self.episode_syncs = 0

    def refresh_kodi_library(self):
        return None

    def sync_deleted_series(self, selected):
        self.series_syncs += 1

    def sync_deleted_episodes(self, selected, linked=None):
        self.episode_syncs += 1
        return ["OK"] if getattr(selected, "db_id", 0) else ["unresolved"]


class ActionPathTests(unittest.TestCase):
    def make_manager(self, files, backend):
        manager = ArrManager(FakeSettings([("/media/Shows", "sftp://pi/media/Shows")]), FakeUI(), logger=None)
        manager._sonarr = FakeSonarr(files, backend)
        return manager

    def test_series_replace_uses_mapped_sftp_url_without_selected_path(self):
        backend = FakeBackend()
        manager = self.make_manager([{"id": 7, "path": "/media/Shows/Episode.mkv"}], backend)
        selected = SelectedItem(media_type="tvshow", tvshow_title="Show")
        with patch("arr_manager.actions.resolve_series", return_value={"id": 3, "title": "Show", "path": "/media/Shows"}), \
             patch("arr_manager.actions.make_direct_backend", return_value=backend):
            result = manager._series_replace(selected)
        self.assertEqual(backend.deleted, ["sftp://pi/media/Shows/Episode.mkv"])
        self.assertEqual(manager.ui.series_syncs, 0)
        self.assertEqual(manager.ui.episode_syncs, 1)
        self.assertIn("Deleted 1 files", result)

    def test_series_replace_uses_mapped_ssh_alias_url_without_selected_path(self):
        backend = FakeBackend()
        manager = ArrManager(FakeSettings([("/media/Shows", "ssh://pi/media/Shows")]), FakeUI(), logger=None)
        manager._sonarr = FakeSonarr([{"id": 7, "path": "/media/Shows/Episode.mkv"}], backend)
        selected = SelectedItem(media_type="tvshow", tvshow_title="Show")
        with patch("arr_manager.actions.resolve_series", return_value={"id": 3, "title": "Show", "path": "/media/Shows"}), \
             patch("arr_manager.actions.make_direct_backend", return_value=backend):
            manager._series_replace(selected)
        self.assertEqual(backend.deleted, ["ssh://pi/media/Shows/Episode.mkv"])

    def test_backend_path_rejects_unsupported_direct_url(self):
        manager = ArrManager(FakeSettings(), FakeUI(), logger=None)
        with self.assertRaises(SafetyError):
            manager._backend_path("ftp://pi/media/file.mkv", "", FakeBackend())

    def test_backend_path_rejects_unmapped_filesystem_path(self):
        manager = ArrManager(FakeSettings(), FakeUI(), logger=None)
        with self.assertRaises(SafetyError):
            manager._backend_path("/media/Shows/file.mkv", "", FakeBackend())

    def test_backend_path_requires_mapping_for_direct_network_url(self):
        manager = ArrManager(FakeSettings(), FakeUI(), logger=None)
        with self.assertRaises(SafetyError):
            manager._backend_path("smb://pi/Shows/file.mkv", "", FakeBackend())

    def test_remote_file_path_recognises_mixed_case_network_schemes(self):
        for value in ("SMB://host/share/file.mkv", "SFTP://host/media/file.mkv", "SsH://host/media/file.mkv"):
            with self.subTest(value=value):
                self.assertEqual(ArrManager._remote_file_path("/series", {"path": value}), value)


if __name__ == "__main__":
    unittest.main()
