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


if __name__ == "__main__":
    unittest.main()
