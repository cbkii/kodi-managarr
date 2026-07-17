import os,sys,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(ROOT,'resources','lib'))
from arr_manager.errors import SafetyError
from arr_manager.fileops import _validate_delete_path
class FileSafetyTests(unittest.TestCase):
    def test_mapping_root_and_ancestor_blocked_but_child_allowed(self):
        protected=['smb://pi/Movies']
        for value in ('smb://pi/Movies','smb://pi'):
            with self.subTest(value=value),self.assertRaises(SafetyError): _validate_delete_path(value,protected,folder=True)
        _validate_delete_path('smb://pi/Movies/Film',protected,folder=True)
    def test_case_mismatch_not_treated_as_protected_identity(self):
        _validate_delete_path('smb://pi/movies/Film',['smb://pi/Movies'],folder=True)
    def test_credential_url_blocked(self):
        with self.assertRaises(SafetyError): _validate_delete_path('sftp://user:pass@pi/media/file.mkv',[],False)
if __name__=='__main__': unittest.main()
