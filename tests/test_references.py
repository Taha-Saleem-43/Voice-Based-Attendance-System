import unittest
from concurrent.futures import ThreadPoolExecutor
import test_backend
from backend.reference_handler import add_reference

class ReferenceCreationTests(unittest.TestCase):
    setUp=test_backend.BackendTests.setUp
    tearDown=test_backend.BackendTests.tearDown

    def admin(self):
        return self.auth.create_user('admin',test_backend.PASSWORD,'chairman')['user_id']

    def test_concurrent_double_submit_creates_one_department(self):
        actor=self.admin()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:add_reference(self.db,actor,'departments','  Engineering  '),range(2)))
        self.assertEqual(sum(results),1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) AS n FROM departments WHERE dept_name='Engineering'",fetchone=True)['n'],1)

    def test_repeated_semester_is_noop(self):
        actor=self.admin()
        self.assertTrue(add_reference(self.db,actor,'semesters',2))
        self.assertFalse(add_reference(self.db,actor,'semesters',2))

    def test_invalid_values_and_non_chairman_cannot_insert(self):
        actor=self.admin()
        for table,value in [('departments','  '),('semesters',9),('users','Bad')]:
            with self.assertRaises(ValueError):
                add_reference(self.db,actor,table,value)
        faculty=self.enroll.enroll_faculty('faculty',test_backend.PASSWORD,'Faculty',1)['user_id']
        with self.assertRaises(ValueError):
            add_reference(self.db,faculty,'sections','B')
