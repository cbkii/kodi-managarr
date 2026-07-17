import os,sys,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(ROOT,'resources','lib'))
from arr_manager.actions import ArrManager
from arr_manager.errors import SafetyError
from arr_manager.util import PathMapper
class Settings: poll_timeout=1; path_mapper=PathMapper([])
class UI:
    def wait_for_abort(self,seconds): return False
class Client:
    def __init__(self,state): self.state=state
    def command_status(self,command_id): return self.state
class PollingTests(unittest.TestCase):
    def test_completed_successful_required(self):
        manager=ArrManager(Settings(),UI(),None)
        state=manager._poll_command(Client({'id':1,'status':'completed','result':'successful'}),{'id':1},'search')
        self.assertEqual(state['result'],'successful')
    def test_completed_unsuccessful_and_missing_result_fail(self):
        manager=ArrManager(Settings(),UI(),None)
        for state in ({'id':1,'status':'completed','result':'unsuccessful'},{'id':1,'status':'completed'}):
            with self.subTest(state=state),self.assertRaises(SafetyError): manager._poll_command(Client(state),{'id':1},'search')
    def test_orphaned_fails(self):
        with self.assertRaises(SafetyError): ArrManager(Settings(),UI(),None)._poll_command(Client({'id':1,'status':'orphaned'}),{'id':1},'search')
if __name__=='__main__': unittest.main()
