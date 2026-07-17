import os,sys,unittest
from unittest.mock import patch
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(ROOT,'resources','lib'))
from arr_manager.actions import ArrManager
from arr_manager.errors import SafetyError
from arr_manager.models import SelectedItem
from arr_manager.util import PathMapper
class Settings:
    backend='vfs'; confirm=False; dry_run=False; require_blocklist=False; poll_timeout=1
    path_mapper=PathMapper([('/shows','smb://pi/Shows')]); protected_paths=['smb://pi/Shows']
    def validate_backend(self): pass
class UI:
    def confirm(self,*args): return True
    def wait_for_abort(self,*args): return False
class Backend:
    def __init__(self,fail_on=0): self.preflight=[]; self.deleted=[]; self.fail_on=fail_on
    def preflight_file(self,path):
        self.preflight.append(path)
        if self.fail_on and len(self.preflight)==self.fail_on: raise SafetyError('bad mapping target')
    def delete_file(self,path): self.deleted.append(path)
    def close(self): pass
class Sonarr:
    def episode_files(self,_): return [{'id':1,'path':'/shows/A.mkv'},{'id':2,'path':'/shows/B.mkv'}]
    def episodes(self,_): return [{'id':11,'episodeFileId':1},{'id':12,'episodeFileId':2},{'id':13,'episodeFileId':0}]
    def series_history(self,*args,**kwargs): return []
class PreflightTests(unittest.TestCase):
    def test_all_files_preflight_before_any_delete(self):
        backend=Backend(fail_on=2); manager=ArrManager(Settings(),UI(),None); manager._sonarr=Sonarr()
        selected=SelectedItem(media_type='tvshow',title='Show')
        with patch('arr_manager.actions_destructive.resolve_series',return_value={'id':3,'title':'Show','path':'/shows'}),patch('arr_manager.actions_destructive.make_direct_backend',return_value=backend):
            with self.assertRaises(SafetyError): manager._series_replace(selected)
        self.assertEqual(backend.deleted,[])
    def test_exact_mapping_root_rejected(self):
        manager=ArrManager(Settings(),UI(),None)
        with self.assertRaises(SafetyError): manager._backend_path('/shows')
if __name__=='__main__': unittest.main()
