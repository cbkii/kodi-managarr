import unittest
from unittest.mock import MagicMock, patch
from arr_manager.retention.service import RetentionService
from arr_manager.retention.models import RetentionCandidate

class TestRetentionService(unittest.TestCase):
    def setUp(self):
        self.manager = MagicMock()
        self.manager.settings.addon.getAddonInfo.return_value = "/tmp"
        self.kodi = MagicMock()
        self.ui = MagicMock()
        self.ui._progress_cancelled.return_value = False
        self.logger = MagicMock()
        self.authoriser = MagicMock()

        import sys
        if 'xbmcvfs' not in sys.modules:
            mock_xbmcvfs = MagicMock()
            mock_xbmcvfs.translatePath = lambda p: p
            sys.modules['xbmcvfs'] = mock_xbmcvfs

        self.service = RetentionService(self.manager, self.kodi, self.ui, self.logger, self.authoriser)
        self.service._test_mode = True

    @patch('arr_manager.retention.service.RetentionSettings')
    @patch('arr_manager.retention.service.RetentionPolicy')
    @patch('arr_manager.retention.service.RetentionEnumerator')
    @patch('arr_manager.retention.service.RetentionExecutor')
    def test_run_cleanup_success(self, MockExec, MockEnum, MockPol, MockSet):
        self.authoriser.authorize.return_value = True
        self.ui.confirm.return_value = True
        cand1 = RetentionCandidate("movie", 1, 10, 100, "Film", "Film", True, 0, 0, {})

        enum_inst = MockEnum.return_value
        enum_inst.get_movies.return_value = [cand1]
        enum_inst.get_episodes.return_value = []

        pol_inst = MockPol.return_value
        el = MagicMock()
        el.eligible = True
        el.reason = "test reason"
        pol_inst.evaluate.return_value = el

        exec_inst = MockExec.return_value
        report_item = MagicMock()
        report_item.action_taken = 'deleted'
        exec_inst.execute_deletion.return_value = report_item

        set_inst = MockSet.return_value
        set_inst.max_deletions = 5
        set_inst.background_dry_run = True
        self.service._init_components()
        res = self.service.run_cleanup_now()

        self.assertIn("Deleted: 1", res)

if __name__ == "__main__":
    unittest.main()
