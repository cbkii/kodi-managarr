import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.models import SelectedItem
from arr_manager.resolver import resolve_movie, resolve_series
from arr_manager.util import PathMapper, parse_mappings


class FakeRadarr:
    def movie_by_tmdb(self, tmdb_id):
        return {"id": 1, "title": "Exact"} if tmdb_id == 123 else None

    def all_movies(self):
        return [
            {"id": 2, "title": "Dune", "year": 2021, "path": "/media/Movies/Dune (2021)"},
            {"id": 3, "title": "Dune", "year": 1984, "path": "/media/Movies/Dune (1984)"},
        ]


class FakeSonarr:
    def series_by_tvdb(self, tvdb_id):
        return None

    def all_series(self):
        return [{"id": 4, "title": "The Bear", "year": 2022, "path": "/media/Shows/The Bear"}]


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.mapper = PathMapper(parse_mappings("/media/Movies=>smb://pi/Movies;/media/Shows=>smb://pi/Shows"))

    def test_tmdb_first(self):
        selected = SelectedItem(media_type="movie", title="Anything", unique_ids={"tmdb": "123"})
        self.assertEqual(resolve_movie(selected, FakeRadarr(), self.mapper)["id"], 1)

    def test_movie_path_and_year(self):
        selected = SelectedItem(media_type="movie", title="Dune", year=2021, file_path="smb://pi/Movies/Dune (2021)/Dune.mkv")
        self.assertEqual(resolve_movie(selected, FakeRadarr(), self.mapper)["id"], 2)

    def test_series_path(self):
        selected = SelectedItem(media_type="episode", tvshow_title="The Bear", file_path="smb://pi/Shows/The Bear/Season 01/file.mkv")
        self.assertEqual(resolve_series(selected, FakeSonarr(), self.mapper)["id"], 4)


if __name__ == "__main__":
    unittest.main()
