import os,sys,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(ROOT,'resources','lib'))
from arr_manager.history import match_history
class HistoryTests(unittest.TestCase):
    def test_empty_paths_do_not_create_root_match(self):
        self.assertIsNone(match_history([{'id':1,'sourceTitle':'','data':{'importedPath':''}}], {'id':7,'path':'','relativePath':''}))
    def test_exact_import_path_matches(self):
        row={'id':99,'sourceTitle':'Movie.2026-GROUP','downloadId':'abc','data':{'importedPath':'/movies/Movie/Movie.2026-GROUP.mkv'}}
        match=match_history([row],{'id':7,'path':'/movies/Movie/Movie.2026-GROUP.mkv','relativePath':'Movie.2026-GROUP.mkv'})
        self.assertEqual(match.history_id,99)
if __name__=='__main__': unittest.main()
