"""Authorization and attendance behavior without loading the voice model."""
from unittest.mock import Mock
import unittest
import numpy as np
import test_backend
from backend.checkin import VoiceCheckinService

class CheckinTests(unittest.TestCase):
    setUp=test_backend.BackendTests.setUp
    tearDown=test_backend.BackendTests.tearDown
    student=test_backend.BackendTests.student
    def service(self):
        model=Mock()
        model.generate_embedding.return_value=np.ones(192,dtype=np.float32)
        model.compute_similarity.return_value=0.99
        return VoiceCheckinService(self.db,Mock(),model)

    def test_unauthorized_scan_never_runs_inference(self):
        service=self.service()
        with self.assertRaises(ValueError):
            service.identify(object())
        service.model.generate_embedding.assert_not_called()

    def test_student_cannot_supervise(self):
        uid=self.student()
        service=self.service()
        with self.assertRaises(ValueError):
            service.identify(object(),supervisor_id=uid)
        service.model.generate_embedding.assert_not_called()

    def test_unlocked_checkin_is_idempotent(self):
        uid=self.student()
        self.attendance.add_voice_embedding(uid,np.ones(192,dtype=np.float32))
        service=self.service()
        self.assertTrue(service.identify(object(),kiosk_authorized=True)['status'])
        self.assertFalse(service.identify(object(),kiosk_authorized=True)['status'])
        self.assertEqual(len(self.attendance.get_user_attendance(uid)),1)

    def test_suspended_profile_never_runs_inference(self):
        uid=self.student()
        self.attendance.add_voice_embedding(uid,np.ones(192,dtype=np.float32))
        self.auth.set_user_active(uid,False)
        service=self.service()
        with self.assertRaises(ValueError):
            service.identify(object(),kiosk_authorized=True)
        service.model.generate_embedding.assert_not_called()

    def test_voice_only_ambiguous_match_does_not_mark_anyone(self):
        first=self.student()
        second=self.student('second','R2')
        for uid in (first,second):
            self.attendance.add_voice_embedding(uid,np.ones(192,dtype=np.float32))
        result=self.service().identify(object(),kiosk_authorized=True)
        self.assertFalse(result['status'])
        self.assertIn('uncertain',result['message'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) AS n FROM attendance',fetchone=True)['n'],0)

    def test_manual_fallback_requires_staff_and_audits_duplicate_once(self):
        uid=self.student()
        self.assertFalse(self.attendance.mark_attendance(uid,marked_by='manual')['status'])
        self.auth.create_user('admin',test_backend.PASSWORD,'chairman')
        admin=self.auth.login('admin',test_backend.PASSWORD)['user_id']
        self.assertTrue(self.attendance.mark_attendance(uid,marked_by='manual',supervisor_id=admin)['status'])
        self.assertFalse(self.attendance.mark_attendance(uid,marked_by='manual',supervisor_id=admin)['status'])
        event=self.db.execute("SELECT actor_id,target_id FROM audit_events WHERE operation='attendance.manual'",fetch=True)
        self.assertEqual([(r['actor_id'],r['target_id']) for r in event],[(admin,uid)])

    def test_voice_only_gallery_supports_two_thousand_accounts(self):
        vector=np.ones(192,dtype=np.float32).tobytes()
        with self.db.transaction() as conn:
            for index in range(2000):
                uid=conn.execute("INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,'student','fixture') RETURNING user_id",(f'gallery{index}',b'fixture')).fetchone()['user_id']
                conn.execute('INSERT INTO students (user_id,roll_no,name,dept_id,semester_id,section_id) VALUES (?,?,?,1,1,1)',(uid,f'R{index}','Fixture'))
                conn.execute('INSERT INTO voice_embeddings (user_id,embedding_vector,created_at) VALUES (?,?,?)',(uid,vector,'fixture'))
        service=self.service()
        service.model.compute_similarity.side_effect=[0.99]+[0.1]*1999
        result=service.identify(object(),kiosk_authorized=True)
        self.assertTrue(result['status'])
        self.assertEqual(result['username'],'gallery0')

    def test_manual_fallback_respects_department_and_suspension(self):
        uid=self.student()
        faculty=self.enroll.enroll_faculty('staff',test_backend.PASSWORD,'Staff',2)['user_id']
        self.assertFalse(self.attendance.mark_attendance(uid,marked_by='manual',supervisor_id=faculty)['status'])
        self.db.execute('UPDATE faculty SET dept_id=1 WHERE user_id=?',(faculty,))
        self.auth.set_user_active(faculty,False)
        self.assertFalse(self.attendance.mark_attendance(uid,marked_by='manual',supervisor_id=faculty)['status'])
        self.auth.set_user_active(faculty,True)
        self.assertTrue(self.attendance.mark_attendance(uid,marked_by='manual',supervisor_id=faculty)['status'])
