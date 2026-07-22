import unittest
import os
import shutil
import tempfile
from pathlib import Path
import zipfile

class GenerateRepoTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.zip_path = Path(self.temp_dir) / "release.zip"

        with zipfile.ZipFile(self.zip_path, "w") as zf:
            zf.writestr("context.arr.manager/addon.xml", '<addon id="context.arr.manager" version="1.0.0"></addon>')
            zf.writestr("context.arr.manager/resources/icon.png", 'fakeicon')

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_generate_repo(self):
        # Just verifying the script runs correctly on a mock zip
        out_dir = Path(self.temp_dir) / "pages"
        # We need to run it as a module or subprocess, but let's just assert the zip was created
        os.system(f"python3 scripts/generate_repo.py {self.zip_path} --out-dir {out_dir}")
        self.assertTrue((out_dir / "addons.xml").exists())
        self.assertTrue((out_dir / "addons.xml.md5").exists())
        self.assertTrue((out_dir / "repository.managarr" / "repository.managarr-1.0.0.zip").exists())
        self.assertTrue((out_dir / "context.arr.manager" / "context.arr.manager-1.0.0.zip").exists())

if __name__ == "__main__":
    unittest.main()
