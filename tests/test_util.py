import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.util import PathMapper, normalise_path, normalise_release, normalise_title, parse_mappings


class UtilTests(unittest.TestCase):
    def test_title_normalisation(self):
        self.assertEqual(normalise_title("Spider-Man: No Way Home"), "spider man no way home")

    def test_release_normalisation(self):
        self.assertEqual(normalise_release("Movie.2026.1080p-GROUP.mkv"), "movie 2026 1080p group")

    def test_path_mapping_round_trip(self):
        mapper = PathMapper(parse_mappings("/srv/Movies=>smb://pi/movies;/srv/Shows=>smb://pi/shows"))
        self.assertEqual(mapper.remote_to_kodi("/srv/Movies/Test/file.mkv"), "smb://pi/movies/Test/file.mkv")
        self.assertEqual(mapper.kodi_to_remote("smb://pi/movies/Test/file.mkv"), "/srv/Movies/Test/file.mkv")

    def test_sftp_path_mapping(self):
        mapper = PathMapper(parse_mappings("/media/Shows=>sftp://pi:22/media/Shows"))
        self.assertEqual(mapper.remote_to_kodi("/media/Shows/Test/file.mkv"), "sftp://pi:22/media/Shows/Test/file.mkv")
        self.assertEqual(mapper.kodi_to_remote("sftp://pi:22/media/Shows/Test/file.mkv"), "/media/Shows/Test/file.mkv")

    def test_rejects_encoded_separators_and_dot_segments(self):
        for value in ("/media/A%2FB", "smb://pi/share/%2e%2e/file.mkv", "/media/../secret"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalise_path(value)

    def test_rejects_malformed_and_overlapping_mappings(self):
        for value in ("/media", "/media=>smb://pi/share;/media/Movies=>smb://pi/movies", "/a=>smb://pi/share;/b=>smb://pi/share/child"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_mappings(value)

    def test_rejects_unsupported_virtual_schemes(self):
        for value in ("videodb://movies/titles/1", "stack://file1 , file2", "plugin://video/test"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalise_path(value)


if __name__ == "__main__":
    unittest.main()
