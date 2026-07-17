import os,sys,unittest
from unittest.mock import patch
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(ROOT,'resources','lib'))
from arr_manager.actions import ArrManager
from arr_manager.models import SelectedItem
from arr_manager.util import PathMapper
class Settings:
    backend='api'; confirm=False; dry_run=False; require_blocklist=True; poll_timeout=1; path_mapper=PathMapper([])
    def validate_backend(self): pass
class UI:
    def confirm(self,*args): return True
    def wait_for_abort(self,*args): return False
class Radarr:
    def __init__(self): self.updated=[]; self.removed=[]
    def update_movie(self,row): self.updated.append(row); return row
    def quality_profiles(self): return [{'id':1,'name':'HD-1080p'},{'id':2,'name':'Ultra'}]
    def queue(self,movie_id): return [{'id':8,'title':'Film','status':'downloading','size':100,'sizeleft':50}]
    def remove_queue_item(self,*args,**kwargs): self.removed.append((args,kwargs))
class ManagementTests(unittest.TestCase):
    def test_monitor_and_quality_profile(self):
        manager=ArrManager(Settings(),UI(),None); manager._radarr=Radarr()
        selected=SelectedItem(media_type='movie',title='Film')
        with patch('arr_manager.actions_management.resolve_movie',return_value={'id':3,'title':'Film','monitored':False,'qualityProfileId':1}):
            manager.set_monitoring(selected,True)
            manager.change_quality_profile(selected,2)
        self.assertTrue(manager._radarr.updated[0]['monitored'])
        self.assertEqual(manager._radarr.updated[1]['qualityProfileId'],2)
    def test_queue_view_and_remove(self):
        manager=ArrManager(Settings(),UI(),None); manager._radarr=Radarr()
        selected=SelectedItem(media_type='movie',title='Film')
        with patch('arr_manager.actions_management.resolve_movie',return_value={'id':3,'title':'Film'}):
            entries=manager.queue_entries(selected)
            self.assertIn('50%',entries[0]['detail'])
            manager.remove_queue_item(selected,8)
        self.assertTrue(manager._radarr.removed)
if __name__=='__main__': unittest.main()
