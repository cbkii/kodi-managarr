import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.util import PathMapper, normalise_release, normalise_title, parse_mappings


class UtilTests(unittest.TestCase):
    def test_title_normalisation(self):
        self.assertEqual(normalise_title("Spider-Man: No Way Home"), "spider man no way home")

    def test_release_normalisation(self):
        self.assertEqual(normalise_release("Movie.2026.1080p-GROUP.mkv"), "movie 2026 1080p group")

    def test_longest_path_mapping(self):
        mapper = PathMapper(parse_mappings("/media=>smb://pi/all;/media/Movies=>smb://pi/movies"))
        self.assertEqual(mapper.remote_to_kodi("/media/Movies/Test/file.mkv"), "smb://pi/movies/Test/file.mkv")
        self.assertEqual(mapper.kodi_to_remote("smb://pi/movies/Test/file.mkv"), "/media/Movies/Test/file.mkv")


if __name__ == "__main__":
    unittest.main()
