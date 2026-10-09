import subprocess
import sys
import unittest
import tomllib
from pathlib import Path
from ui.workspace import csv_safe

ROOT=Path(__file__).resolve().parent.parent

class StructureTests(unittest.TestCase):
    def test_backend_import_does_not_load_audio_model_libraries(self):
        result=subprocess.run([sys.executable,'-c',"import backend,sys; assert 'torch' not in sys.modules; assert 'torchaudio' not in sys.modules"],cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_uncaught_error_details_are_disabled(self):
        config=tomllib.loads((ROOT/'.streamlit/config.toml').read_text())
        self.assertEqual(config['client']['showErrorDetails'],'none')

    def test_csv_neutralizes_formulas_without_changing_numbers(self):
        for value in ('=HYPERLINK("https://example.invalid")',' +SUM(1,2)','@formula','-cmd'):
            self.assertTrue(csv_safe(value).startswith("'"))
        self.assertEqual(csv_safe(-1),-1)
        self.assertEqual(csv_safe('Student'),'Student')
