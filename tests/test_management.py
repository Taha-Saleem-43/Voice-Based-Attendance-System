import unittest
import test_backend
from backend.management import delete_reference,set_account_state,delete_voice_sample
from backend.errors import ValidationError,report_error
from backend.reference_cache import reference_rows
import numpy as np

class ManagementTests(unittest.TestCase):
    setUp=test_backend.BackendTests.setUp
    tearDown=test_backend.BackendTests.tearDown
    student=test_backend.BackendTests.student

    def admin(self):
        return self.auth.create_user('admin',test_backend.PASSWORD,'chairman')['user_id']

    def test_delete_unused_reference_invalidates_cache(self):
        actor=self.admin()
        reference_rows(self.db,'departments')
        delete_reference(self.db,actor,'departments',2)
        self.assertEqual(len(reference_rows(self.db,'departments')),1)

    def test_referenced_department_is_preserved(self):
        actor=self.admin()
        uid=self.student()
        with self.assertRaisesRegex(ValidationError,'in use'):
            delete_reference(self.db,actor,'departments',1)
        self.assertIsNotNone(self.db.execute('SELECT 1 FROM students WHERE user_id=?',(uid,),fetchone=True))

    def test_account_action_checks_authority_and_stale_state(self):
        actor=self.admin()
        uid=self.student()
        with self.assertRaises(ValidationError):
            set_account_state(self.db,uid,uid,1,False)
        set_account_state(self.db,actor,uid,1,False)
        with self.assertRaises(ValidationError):
            set_account_state(self.db,actor,uid,1,False)
        self.assertFalse(self.auth.login('student',test_backend.PASSWORD)['status'])
        with self.assertRaises(ValidationError):
            set_account_state(self.db,actor,actor,1,False)

    def test_voice_removal_enforces_department_and_retains_attendance(self):
        actor=self.admin()
        uid=self.student()
        self.attendance.add_voice_embedding(uid,np.ones(192,dtype=np.float32))
        self.attendance.mark_attendance(uid,confidence=.9)
        foreign=self.enroll.enroll_faculty('foreign',test_backend.PASSWORD,'Foreign',2)['user_id']
        sample=self.db.execute('SELECT embedding_id FROM voice_embeddings',fetchone=True)['embedding_id']
        with self.assertRaises(ValidationError):
            delete_voice_sample(self.db,foreign,sample)
        delete_voice_sample(self.db,actor,sample)
        self.assertEqual(self.attendance.get_voice_embeddings(uid),[])
        self.assertEqual(len(self.attendance.get_user_attendance(uid)),1)

    def test_error_diagnostics_exclude_exception_payloads(self):
        payload='postgresql://user:password@host SELECT secret CERTIFICATE PRIVATE KEY'
        with self.assertLogs(level='ERROR') as logs:
            message=report_error('test-operation',RuntimeError(payload))
        self.assertNotIn(payload,message)
        self.assertNotIn(payload,' '.join(logs.output))
        self.assertIn('reference',message)
