import os, sys, unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT,'resources','lib'))
from arr_manager.errors import ResolutionError
from arr_manager.models import SelectedItem
from arr_manager.resolver import resolve_movie, resolve_series
from arr_manager.util import PathMapper, parse_mappings

class Radarr:
    def movie_by_tmdb(self, value): return None
    def all_movies(self):
        return [
            {'id':1,'title':'Dune','year':2021,'path':''},
            {'id':2,'title':'Dune','year':2021,'path':'/media/Movies/Dune (2021)'},
        ]
class Sonarr:
    def series_by_tvdb(self,value): return None
    def all_series(self): return [{'id':4,'title':'The Bear','year':2022,'path':'/media/Shows/The Bear'}]
class ResolverTests(unittest.TestCase):
    def setUp(self): self.mapper=PathMapper(parse_mappings('/media/Movies=>smb://pi/Movies;/media/Shows=>smb://pi/Shows'))
    def test_empty_candidate_path_never_becomes_root_match(self):
        selected=SelectedItem(media_type='movie',title='Dune',year=2021,file_path='smb://pi/Movies/Dune (2021)/file.mkv')
        self.assertEqual(resolve_movie(selected,Radarr(),self.mapper)['id'],2)
    def test_title_only_is_not_enough(self):
        with self.assertRaises(ResolutionError): resolve_movie(SelectedItem(media_type='movie',title='Dune'),Radarr(),self.mapper)
    def test_series_path(self):
        selected=SelectedItem(media_type='episode',tvshow_title='The Bear',file_path='smb://pi/Shows/The Bear/Season 01/file.mkv')
        self.assertEqual(resolve_series(selected,Sonarr(),self.mapper)['id'],4)
if __name__=='__main__': unittest.main()
