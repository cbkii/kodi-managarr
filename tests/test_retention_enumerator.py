import datetime
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import SafetyError
from arr_manager.retention.enumerator import RetentionEnumerator


class Logger:
    def debug(self, *args):
        pass

    def warning(self, *args):
        pass


class SeriesKodi:
    def __init__(self):
        self.calls = []

    def call(self, method, params):
        self.calls.append((method, params))
        if method == "VideoLibrary.GetTVShowDetails":
            return {
                "tvshowdetails": {
                    "title": "Show",
                    "year": 2024,
                    "uniqueid": {"tvdb": "123"},
                }
            }
        raise AssertionError(method)


class Sonarr:
    def __init__(self):
        self.episode_calls = 0
        self.file_calls = 0
        self._episodes = [
            {"id": 101, "seasonNumber": 1, "episodeNumber": 1, "episodeFileId": 501},
            {"id": 102, "seasonNumber": 1, "episodeNumber": 2, "episodeFileId": 502},
        ]
        self._files = [
            {"id": 501, "dateAdded": "2022-01-01T00:00:00Z"},
            {"id": 502, "dateAdded": "2022-01-02T00:00:00Z"},
        ]

    def episodes(self, _series_id):
        self.episode_calls += 1
        return self._episodes

    def episode_files(self, _series_id):
        self.file_calls += 1
        return self._files


class Manager:
    def __init__(self):
        self.sonarr = Sonarr()


class PagedKodi:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def call(self, method, params):
        self.calls.append((method, params))
        return self.pages.pop(0)


def episode_row(episode_id, episode_number, date_added="2020-01-01 00:00:00"):
    return {
        "episodeid": episode_id,
        "tvshowid": 10,
        "title": f"Episode {episode_number}",
        "tvshowtitle": "Show",
        "season": 1,
        "episode": episode_number,
        "file": f"/show/e{episode_number}.mkv",
        "uniqueid": {"tvdb": str(episode_id)},
        "playcount": 1,
        "lastplayed": "2021-01-01 00:00:00",
        "dateadded": date_added,
    }


class RetentionEnumeratorTests(unittest.TestCase):
    def test_pagination_is_bounded_and_complete(self):
        kodi = PagedKodi([
            {"rows": [{"id": 1}, {"id": 2}]},
            {"rows": [{"id": 3}]},
        ])
        enumerator = RetentionEnumerator(kodi, object(), None)
        enumerator.PAGE_SIZE = 2
        result = enumerator._paged("Library.Get", "rows", [], lambda row: row["id"])
        self.assertEqual(result, [1, 2, 3])
        self.assertEqual(kodi.calls[0][1]["limits"], {"start": 0, "end": 2})
        self.assertEqual(kodi.calls[1][1]["limits"], {"start": 2, "end": 4})

    def test_malformed_page_shape_fails_closed(self):
        kodi = PagedKodi([{"rows": "not-a-list"}])
        enumerator = RetentionEnumerator(kodi, object(), None)
        with self.assertRaises(SafetyError):
            enumerator._paged("Library.Get", "rows", [], lambda row: row)

    def test_malformed_nonempty_date_skips_candidate(self):
        kodi = PagedKodi([{"rows": [{"date": "not-a-date"}]}])
        enumerator = RetentionEnumerator(kodi, object(), None, Logger())
        result = enumerator._paged(
            "Library.Get",
            "rows",
            [],
            lambda row: enumerator._parse_kodi_date(row["date"]),
        )
        self.assertEqual(result, [])

    def test_episode_enumeration_reuses_one_sonarr_snapshot_per_series(self):
        kodi = SeriesKodi()
        manager = Manager()
        enumerator = RetentionEnumerator(kodi, manager, None)
        series = {"id": 20, "title": "Show", "added": "2025-01-01T00:00:00Z"}
        with mock.patch("arr_manager.retention.enumerator.resolve_series", return_value=series) as resolve:
            first = enumerator._process_kodi_episode(episode_row(1, 1))
            second = enumerator._process_kodi_episode(episode_row(2, 2))
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(manager.sonarr.episode_calls, 1)
        self.assertEqual(manager.sonarr.file_calls, 1)
        self.assertEqual(
            len([call for call in kodi.calls if call[0] == "VideoLibrary.GetTVShowDetails"]),
            1,
        )
        expected_added = datetime.datetime(
            2025, 1, 1, tzinfo=datetime.timezone.utc
        ).timestamp()
        self.assertEqual(first.date_added, expected_added)
        self.assertEqual(second.date_added, expected_added)

    def test_duplicate_sonarr_episode_numbers_fail_closed(self):
        kodi = SeriesKodi()
        manager = Manager()
        manager.sonarr._episodes[1]["episodeNumber"] = 1
        enumerator = RetentionEnumerator(kodi, manager, None)
        series = {"id": 20, "title": "Show", "added": "2025-01-01T00:00:00Z"}
        with mock.patch("arr_manager.retention.enumerator.resolve_series", return_value=series):
            with self.assertRaises(SafetyError):
                enumerator._process_kodi_episode(episode_row(1, 1))

    def test_refresh_uses_supplied_fresh_snapshot(self):
        kodi = SeriesKodi()
        manager = Manager()
        enumerator = RetentionEnumerator(kodi, manager, None)
        snapshot = (
            {"id": 20, "title": "Show", "added": "2025-01-01T00:00:00Z"},
            [{"id": 101, "seasonNumber": 1, "episodeNumber": 1, "episodeFileId": 501}],
            [{"id": 501, "dateAdded": "2025-01-01T00:00:00Z"}],
        )
        candidate = enumerator._process_kodi_episode(
            episode_row(1, 1),
            refresh=True,
            sonarr_snapshot=snapshot,
        )
        self.assertEqual(candidate.file_id, 501)
        self.assertEqual(manager.sonarr.episode_calls, 0)
        self.assertEqual(manager.sonarr.file_calls, 0)


if __name__ == "__main__":
    unittest.main()
