import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import SafetyError
from arr_manager.fileops import _validate_delete_path


class FileSafetyTests(unittest.TestCase):
    def test_allows_child_of_protected_library_root(self):
        _validate_delete_path("/media/mediasmb/Movies/Film", ["/", "/media/mediasmb"], folder=True)

    def test_blocks_protected_root_itself(self):
        with self.assertRaises(SafetyError):
            _validate_delete_path("/media/mediasmb", ["/media/mediasmb"], folder=True)

    def test_blocks_ancestor_of_protected_path(self):
        with self.assertRaises(SafetyError):
            _validate_delete_path("/media", ["/media/mediasmb"], folder=True)

    def test_blocks_smb_share_root(self):
        with self.assertRaises(SafetyError):
            _validate_delete_path("smb://pi/Movies", [], folder=True)

    def test_allows_sftp_child_below_remote_root(self):
        _validate_delete_path("sftp://pi:22/media/Movies/Film", [], folder=True)

    def test_blocks_sftp_server_root(self):
        for value in ("sftp://pi/", "sftp://pi:22/", "ssh://pi/"):
            with self.subTest(value=value):
                with self.assertRaises(SafetyError):
                    _validate_delete_path(value, [], folder=True)

    def test_blocks_sftp_top_level_remote_directory(self):
        for value in ("sftp://pi/media", "ssh://pi/media"):
            with self.subTest(value=value):
                with self.assertRaises(SafetyError):
                    _validate_delete_path(value, [], folder=True)

    def test_allows_sftp_and_ssh_top_level_file_operations(self):
        for value in ("sftp://pi/movie.mkv", "ssh://pi/movie.mkv"):
            with self.subTest(value=value):
                _validate_delete_path(value, [], folder=False)

    def test_blocks_credential_bearing_sftp_url(self):
        with self.assertRaises(SafetyError):
            _validate_delete_path("sftp://user:pass@pi/media/Movies", [], folder=False)

    def test_blocks_relative_and_home_paths(self):
        for value in ("/", "~", ".", "..", "../Movies", "sftp://pi/media/../Movies"):
            with self.subTest(value=value):
                with self.assertRaises(SafetyError):
                    _validate_delete_path(value, [], folder=True)

    def test_blocks_protected_sftp_path_and_ancestor(self):
        protected = ["sftp://pi:22/media/Movies"]
        for value in ("sftp://pi:22/media/Movies", "sftp://pi:22/media"):
            with self.subTest(value=value):
                with self.assertRaises(SafetyError):
                    _validate_delete_path(value, protected, folder=True)

    def test_canonicalises_sftp_ssh_default_port_for_protected_paths(self):
        protected = ["sftp://pi:22/media/Movies"]
        for value in ("ssh://PI/media/Movies", "ssh://PI:22/media/Movies/Film"):
            with self.subTest(value=value):
                with self.assertRaises(SafetyError):
                    _validate_delete_path(value, protected, folder=True)

    def test_sftp_non_default_port_is_distinct_for_protected_paths(self):
        _validate_delete_path("sftp://pi:2222/media/Movies", ["sftp://pi/media/Movies"], folder=True)

    def test_sftp_path_case_is_preserved_for_protected_paths(self):
        _validate_delete_path("sftp://pi/media/movies", ["sftp://pi/media/Movies"], folder=True)


if __name__ == "__main__":
    unittest.main()
