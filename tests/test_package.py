import re
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
from package_deployment import package

class PackageTests(unittest.TestCase):
    def test_archive_excludes_private_data_and_runtime_files(self):
        path=package()
        with ZipFile(path) as archive:
            names=archive.namelist()
            self.assertIn('app.py',names)
            self.assertIn('backend/schema.sql',names)
            self.assertIn('.streamlit/secrets.toml.example',names)
            for name in names:
                self.assertFalse(any(part in name.split('/') for part in ('assets','Voices','venv','.deploy-venv','pretrained_models','__pycache__','database')))
                self.assertNotEqual(name,'.streamlit/secrets.toml')
                self.assertIsNone(re.search(rb'hf_[A-Za-z0-9]{30,}',archive.read(name)))

if __name__=='__main__':
    unittest.main()
