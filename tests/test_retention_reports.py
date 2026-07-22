import unittest
import os
import shutil
import tempfile
from unittest.mock import MagicMock
from arr_manager.retention.reports import RetentionStateStore

class TestRetentionReports(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addon = MagicMock()
        self.addon.getAddonInfo.return_value = self.temp_dir

        # Patch xbmcvfs globally just for this test
        import sys
        if 'xbmcvfs' not in sys.modules:
            mock_xbmcvfs = MagicMock()
            mock_xbmcvfs.translatePath = lambda p: p
            sys.modules['xbmcvfs'] = mock_xbmcvfs

        self.store = RetentionStateStore(self.addon)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_save_load_state(self):
        self.store.save_state("gen1", 1234567890)
        state = self.store.load_state()
        self.assertEqual(state.get("auth_generation"), "gen1")
        self.assertEqual(state.get("next_due"), 1234567890)

    def test_save_load_report(self):
        report = {"test": "data"}
        self.store.save_report(report)
        loaded = self.store.load_report()
        self.assertEqual(loaded, report)

    def test_lock_acquire_release(self):
        self.assertTrue(self.store.acquire_lock())
        self.assertFalse(self.store.acquire_lock()) # already locked
        self.store.release_lock()
        self.assertTrue(self.store.acquire_lock())

if __name__ == "__main__":
    unittest.main()
