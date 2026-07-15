import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import ResolutionError
from arr_manager.models import SelectedItem
from arr_manager.resolver import resolve_movie, resolve_series
from arr_manager.util import PathMapper, parse_mappings


class FakeRadarr:
    def movie_by_tmdb(self, tmdb_id):
        return {"id": 1, "title": "Exact", "year": 2024} if tmdb_id == 123 else None
    def all_movies(self):
        return [
            {"id": 2, "title": "Dune", "year": 2021, "path": "/media/Movies/Dune (2021)"},
            {"id": 3, "title": "Dune", "year": 1984, "path": "/media/Movies/Dune (1984)"},
        ]

class FakeSonarr:
    def series_by_tvdb(self, tvdb_id):
        return {"id": 9, "title": "Other", "year": 2020} if tvdb_id == 9 else None
    def all_series(self):
        return [{"id": 4, "title": "The Bear", "year": 2022, "path": "/media/Shows/The Bear"}]

class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.mapper = PathMapper(parse_mappings("/media/Movies=>smb://pi/Movies;/media/Shows=>smb://pi/Shows"))

    def test_tmdb_first_with_consistent_metadata(self):
        selected = SelectedItem(media_type="movie", title="Exact", year=2024, unique_ids={"tmdb": "123"})
        self.assertEqual(resolve_movie(selected, FakeRadarr(), self.mapper)["id"], 1)

    def test_external_id_rejects_contradictory_title(self):
        selected = SelectedItem(media_type="movie", title="Wrong", year=2024, unique_ids={"tmdb": "123"})
        with self.assertRaises(ResolutionError):
            resolve_movie(selected, FakeRadarr(), self.mapper)

    def test_movie_path_and_year(self):
        selected = SelectedItem(media_type="movie", title="Dune", year=2021, file_path="smb://pi/Movies/Dune (2021)/Dune.mkv")
        self.assertEqual(resolve_movie(selected, FakeRadarr(), self.mapper)["id"], 2)

    def test_title_only_is_not_enough(self):
        selected = SelectedItem(media_type="movie", title="Dune")
        with self.assertRaises(ResolutionError):
            resolve_movie(selected, FakeRadarr(), self.mapper)

    def test_explicit_year_mismatch_rejected_without_path(self):
        selected = SelectedItem(media_type="movie", title="Dune", year=1999)
        with self.assertRaises(ResolutionError):
            resolve_movie(selected, FakeRadarr(), self.mapper)

    def test_series_path(self):
        selected = SelectedItem(media_type="episode", tvshow_title="The Bear", file_path="smb://pi/Shows/The Bear/Season 01/file.mkv")
        self.assertEqual(resolve_series(selected, FakeSonarr(), self.mapper)["id"], 4)

    def test_unsupported_virtual_path_rejected(self):
        selected = SelectedItem(media_type="movie", title="Dune", file_path="videodb://movies/titles/1")
        with self.assertRaises(ResolutionError):
            resolve_movie(selected, FakeRadarr(), self.mapper)

if __name__ == "__main__":
    unittest.main()
