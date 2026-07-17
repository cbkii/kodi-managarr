import os, sys, unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT,'resources','lib'))
from arr_manager.util import PathMapper, is_path_under, normalise_path, normalise_release, normalise_title, parse_mappings

class UtilTests(unittest.TestCase):
    def test_title_and_release_normalisation(self):
        self.assertEqual(normalise_title('Spider-Man: No Way Home'),'spider man no way home')
        self.assertEqual(normalise_release('Movie.2026.1080p-GROUP.mkv'),'movie 2026 1080p group')
    def test_empty_path_rejected(self):
        with self.assertRaises(ValueError): normalise_path('')
    def test_path_mapping_round_trip(self):
        mapper=PathMapper(parse_mappings('/srv/Movies=>smb://pi/Movies'))
        self.assertEqual(mapper.remote_to_kodi('/srv/Movies/Test/file.mkv'),'smb://pi/Movies/Test/file.mkv')
        self.assertEqual(mapper.kodi_to_remote('smb://pi/Movies/Test/file.mkv'),'/srv/Movies/Test/file.mkv')
    def test_smb_path_case_is_preserved_and_compared_exactly(self):
        self.assertTrue(is_path_under('smb://PI/Movies/Film','smb://pi/Movies'))
        self.assertFalse(is_path_under('smb://pi/movies/Film','smb://pi/Movies'))
    def test_authority_and_sftp_aliases(self):
        self.assertFalse(is_path_under('smb://other/Movies/Film','smb://pi/Movies'))
        self.assertTrue(is_path_under('sftp://[::1]:22/media/Shows/Ep.mkv','ssh://[::1]/media/Shows'))
    def test_rejects_encoded_and_overlapping(self):
        for value in ('/media/A%2FB','smb://pi/share/%2e%2e/file.mkv','/media/%zz','/media/../secret'):
            with self.subTest(value=value), self.assertRaises(ValueError): normalise_path(value)
        for value in ('/media','/media=>smb://pi/share;/media/Movies=>smb://pi/movies'):
            with self.subTest(value=value), self.assertRaises(ValueError): parse_mappings(value)
if __name__=='__main__': unittest.main()
