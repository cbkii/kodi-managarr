import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.errors import SafetyError
from arr_manager.fileops import KodiNetworkVFSBackend, _validate_delete_path


class FakeVFS:
    def __init__(self, stale_directory_listing=False):
        self.stale_directory_listing = stale_directory_listing
        self.listings = {
            "/media/Movies": {"dirs": ["Film"], "files": []},
            "/media/Movies/Film": {"dirs": ["Extras"], "files": ["movie.mkv"]},
            "/media/Movies/Film/Extras": {"dirs": [], "files": ["sample.mkv"]},
        }
        self.existing = {
            "/media/Movies",
            "/media/Movies/Film",
            "/media/Movies/Film/Extras",
            "/media/Movies/Film/movie.mkv",
            "/media/Movies/Film/Extras/sample.mkv",
        }
        self.deleted = []
        self.removed = []

    @staticmethod
    def _key(path):
        return path.rstrip("/") or "/"

    def listdir(self, path):
        state = self.listings[self._key(path)]
        return list(state["dirs"]), list(state["files"])

    def exists(self, path):
        return self._key(path) in self.existing

    def delete(self, path):
        path = self._key(path)
        if path not in self.existing:
            return False
        parent, name = path.rsplit("/", 1)
        self.existing.remove(path)
        self.listings[parent]["files"].remove(name)
        self.deleted.append(path)
        return True

    def rmdir(self, path, force=False):
        del force
        path = self._key(path)
        state = self.listings.get(path)
        if path not in self.existing or state is None or state["dirs"] or state["files"]:
            return False
        parent, name = path.rsplit("/", 1)
        self.existing.remove(path)
        if not self.stale_directory_listing:
            self.listings[parent]["dirs"].remove(name)
        self.removed.append(path)
        return True


class FileSafetyTests(unittest.TestCase):
    def test_mapping_root_and_ancestor_blocked_but_child_allowed(self):
        protected = ["smb://pi/Movies"]
        for value in ("smb://pi/Movies", "smb://pi"):
            with self.subTest(value=value), self.assertRaises(SafetyError):
                _validate_delete_path(value, protected, folder=True)
        _validate_delete_path("smb://pi/Movies/Film", protected, folder=True)

    def test_case_mismatch_not_treated_as_protected_identity(self):
        with self.assertRaises(SafetyError):
            _validate_delete_path(
                "smb://pi/movies",
                ["smb://pi/Movies"],
                folder=True,
            )

    def test_credential_url_blocked(self):
        with self.assertRaises(SafetyError):
            _validate_delete_path("sftp://user:pass@pi/media/file.mkv", [], False)

    @staticmethod
    def _backend(vfs):
        backend = object.__new__(KodiNetworkVFSBackend)
        backend.vfs = vfs
        backend.protected_paths = []
        backend.logger = None
        backend._sftp_checked = False
        return backend

    def test_new_empty_directory_after_confirmation_aborts_before_deletion(self):
        vfs = FakeVFS()
        backend = self._backend(vfs)
        target = "/media/Movies/Film"
        plan = backend.preflight_tree(target)
        vfs.listings[target]["dirs"].append("NewEmpty")
        vfs.listings[f"{target}/NewEmpty"] = {"dirs": [], "files": []}
        vfs.existing.add(f"{target}/NewEmpty")

        with self.assertRaisesRegex(SafetyError, "changed after confirmation"):
            backend.delete_tree(target, plan)

        self.assertEqual(vfs.deleted, [])
        self.assertIn(f"{target}/movie.mkv", vfs.existing)

    def test_removed_directory_must_disappear_from_parent_listing(self):
        vfs = FakeVFS(stale_directory_listing=True)
        backend = self._backend(vfs)
        target = "/media/Movies/Film"
        plan = backend.preflight_tree(target)

        with self.assertRaisesRegex(SafetyError, "parent listing still contains removed folder"):
            backend.delete_tree(target, plan)

        self.assertIn("Extras", vfs.listings[target]["dirs"])

    def test_unchanged_tree_is_deleted_and_verified(self):
        vfs = FakeVFS()
        backend = self._backend(vfs)
        target = "/media/Movies/Film"
        plan = backend.preflight_tree(target)

        backend.delete_tree(target, plan)

        self.assertNotIn(target, vfs.existing)
        self.assertNotIn("Film", vfs.listings["/media/Movies"]["dirs"])
        self.assertEqual(
            set(vfs.deleted),
            {f"{target}/movie.mkv", f"{target}/Extras/sample.mkv"},
        )


if __name__ == "__main__":
    unittest.main()
