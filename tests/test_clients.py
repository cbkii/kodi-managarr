import os,sys,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(ROOT,'resources','lib'))
from arr_manager.clients import RadarrClient, SonarrClient
from arr_manager.errors import ApiError
class HTTP:
    def __init__(self,responses): self.responses=list(responses); self.calls=[]
    def request(self,*args,**kwargs): self.calls.append((args,kwargs)); return self.responses.pop(0)
class ClientTests(unittest.TestCase):
    def test_duplicate_external_id_rejected(self):
        client=object.__new__(RadarrClient); client.http=HTTP([[{'id':1},{'id':2}]])
        with self.assertRaises(ApiError): client.movie_by_tmdb(5)
    def test_queue_and_remove_contracts(self):
        client=object.__new__(SonarrClient); client.http=HTTP([{'records':[{'id':9}]},None])
        self.assertEqual(client.queue(3),[{'id':9}])
        client.remove_queue_item(9)
        self.assertEqual(client.http.calls[0][0],('GET','/queue'))
        self.assertEqual(client.http.calls[1][0],('DELETE','/queue/9'))
        self.assertEqual(client.http.calls[1][1]['params'],{'removeFromClient':True,'blocklist':False})
if __name__=='__main__': unittest.main()
