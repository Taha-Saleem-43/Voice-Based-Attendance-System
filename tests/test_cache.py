import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.database import DatabaseHandler
from backend.reference_cache import reference_rows,invalidate_references,_read

class ReferenceCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=DatabaseHandler(Path(self.tmp.name)/'first.db')
        self.db.execute("INSERT INTO departments (dept_name) VALUES ('Computing')")
        _read.clear()

    def tearDown(self):
        _read.clear()
        self.tmp.cleanup()

    def test_repeated_reads_hit_cache_and_return_independent_copies(self):
        with patch.object(self.db,'execute',wraps=self.db.execute) as query:
            rows=reference_rows(self.db,'departments')
            rows[0]['dept_name']='Changed in UI'
            self.assertEqual(reference_rows(self.db,'departments')[0]['dept_name'],'Computing')
            query.assert_called_once()

    def test_invalidation_shows_new_reference_immediately(self):
        reference_rows(self.db,'departments')
        self.db.execute("INSERT INTO departments (dept_name) VALUES ('Engineering')")
        invalidate_references(self.db,'departments')
        self.assertEqual(len(reference_rows(self.db,'departments')),2)

    def test_databases_cannot_share_reference_results(self):
        other=DatabaseHandler(Path(self.tmp.name)/'other.db')
        reference_rows(self.db,'departments')
        self.assertEqual(reference_rows(other,'departments'),[])

    def test_only_reference_tables_can_be_cached(self):
        with self.assertRaises(ValueError):
            reference_rows(self.db,'users')
