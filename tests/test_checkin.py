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
