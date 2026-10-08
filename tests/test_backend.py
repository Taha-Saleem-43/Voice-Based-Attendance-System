import io
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.database import DatabaseHandler
from backend.auth_handler import AuthHandler
from backend.enrollment_handler import EnrollmentHandler
from backend.attendance_handler import AttendanceHandler
from backend.bootstrap import ensure_admin
from backend.audio_processor import AudioProcessor

PASSWORD = 'Test-password-42'

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = DatabaseHandler(Path(self.tmp.name)/'attendance.db')
        self.auth = AuthHandler(self.db)
        self.enroll = EnrollmentHandler(self.db)
        self.attendance = AttendanceHandler(self.db)
        self.db.execute("INSERT INTO departments (dept_name) VALUES ('Computing'),('Other')")
        self.db.execute("INSERT INTO semesters (semester_no) VALUES (1)")
        self.db.execute("INSERT INTO sections (section_name) VALUES ('A')")

    def tearDown(self):
        self.tmp.cleanup()

    def student(self, username='student', roll='R1'):
        result = self.enroll.enroll_student(username,PASSWORD,roll,'Student',1,1,1)
        self.assertTrue(result['status'], result)
        return result['user_id']

    def test_bootstrap_and_existing_admin_not_reset(self):
        with patch('backend.bootstrap.setting', side_effect=lambda name: {'ADMIN_USERNAME':'admin','ADMIN_PASSWORD':PASSWORD}.get(name)):
            ensure_admin(self.db)
            ensure_admin(self.db)
        self.assertTrue(self.auth.login('admin',PASSWORD)['status'])
        self.assertEqual(self.db.execute("SELECT COUNT(*) AS n FROM users WHERE role='chairman'",fetchone=True)['n'],1)

    def test_bootstrap_requires_secrets(self):
        with patch('backend.bootstrap.setting',return_value=None), self.assertRaises(ValueError):
            ensure_admin(self.db)

    def test_new_password_policy(self):
        self.assertFalse(self.auth.create_user('weak','123','chairman')['status'])
        self.assertFalse(self.auth.create_user('long','x'*73,'chairman')['status'])

    def test_login_and_disabled_user(self):
        uid = self.student()
        self.assertTrue(self.auth.login('student',PASSWORD)['status'])
        self.auth.set_user_active(uid,False)
        self.assertFalse(self.auth.login('student',PASSWORD)['status'])

    def test_login_limit_and_expiry(self):
        self.student()
        with patch('backend.auth_handler.time.time',return_value=1000):
            for _ in range(5):
                self.assertFalse(self.auth.login('student','wrong')['status'])
            self.assertIn('Too many',self.auth.login('student',PASSWORD)['message'])
        with patch('backend.auth_handler.time.time',return_value=1901):
            self.assertTrue(self.auth.login('student',PASSWORD)['status'])

    def test_enrollment_rejects_missing_reference(self):
        result = self.enroll.enroll_student('bad',PASSWORD,'bad','Bad',999,1,1)
        self.assertFalse(result['status'])
        self.assertIsNone(self.db.execute("SELECT 1 FROM users WHERE username='bad'",fetchone=True))

    def test_enrollment_rolls_back_after_profile_insert_failure(self):
        # A database-side failure after users INSERT must roll back that INSERT.
        self.db.execute("CREATE TRIGGER reject_student BEFORE INSERT ON students BEGIN SELECT RAISE(ABORT, 'test rejection'); END")
        result = self.enroll.enroll_student('rollback',PASSWORD,'R1','Bad',1,1,1)
        self.assertFalse(result['status'])
        self.assertIsNone(self.db.execute("SELECT 1 FROM users WHERE username='rollback'",fetchone=True))

    def test_duplicate_roll_does_not_leave_account(self):
        self.student()
        result = self.enroll.enroll_student('duplicate',PASSWORD,'R1','Duplicate',1,1,1)
        self.assertFalse(result['status'])
        self.assertIsNone(self.db.execute("SELECT 1 FROM users WHERE username='duplicate'",fetchone=True))

    def test_faculty_scope_enforced_in_backend(self):
        result = self.enroll.enroll_faculty('faculty',PASSWORD,'Faculty',1)
        self.assertTrue(result['status'])
        scoped = EnrollmentHandler(self.db,actor_user_id=result['user_id'])
        self.assertFalse(scoped.enroll_student('cross',PASSWORD,'R2','Cross',2,1,1)['status'])
        self.assertTrue(scoped.enroll_student('same',PASSWORD,'R2','Same',1,1,1)['status'])
        self.assertFalse(scoped.enroll_teacher('teacher',PASSWORD,'Teacher',1,section_id=1)['status'])

    def test_foreign_keys_enabled(self):
        with self.assertRaises(Exception):
            self.db.execute("INSERT INTO students (user_id,roll_no,name,dept_id,semester_id,section_id) VALUES (999,'x','x',1,1,1)")

    def test_daily_attendance_unique_and_profile_metadata(self):
        uid=self.student()
        self.assertTrue(self.attendance.mark_attendance(uid,role='teacher',dept_id=999,confidence=.8)['status'])
        self.assertFalse(self.attendance.mark_attendance(uid,confidence=.8)['status'])
        row=self.db.execute('SELECT * FROM attendance',fetchone=True)
        self.assertEqual((row['role'],row['dept_id'],row['semester_id'],row['section_id']),('student',1,1,1))

    def test_concurrent_marking_is_idempotent(self):
        uid=self.student()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.attendance.mark_attendance(uid,confidence=.8),range(4)))
        self.assertEqual(sum(result['status'] for result in results),1)

    def test_disabled_profile_not_matched_or_marked(self):
        uid=self.student()
        vector=np.ones(192,dtype=np.float32)
        self.assertTrue(self.attendance.add_voice_embedding(uid,vector)['status'])
        self.assertEqual(len(self.attendance.get_active_voice_profiles()),1)
        self.auth.set_user_active(uid,False)
        self.assertEqual(self.attendance.get_active_voice_profiles(),[])
        self.assertFalse(self.attendance.mark_attendance(uid,confidence=.9)['status'])

    def test_attendance_uses_configured_calendar_day(self):
        uid=self.student()
        instant=datetime.fromisoformat('2026-10-09T00:05:00+05:00')
        with patch('backend.attendance_handler.local_now',return_value=instant):
            self.attendance.mark_attendance(uid,confidence=.8)
        self.assertEqual(self.db.execute('SELECT date FROM attendance',fetchone=True)['date'],'2026-10-09')

    def test_enrollment_and_embeddings_persist_across_connections(self):
        uid=self.student()
        vector=np.arange(1,193,dtype=np.float32)
        self.assertTrue(self.attendance.add_voice_embedding(uid,vector)['status'])
        reopened=DatabaseHandler(Path(self.tmp.name)/'attendance.db')
        np.testing.assert_array_equal(AttendanceHandler(reopened).get_voice_embeddings(uid)[0],vector)
        self.assertFalse(self.attendance.add_voice_embedding(uid,vector)['status'])

    def test_invalid_embeddings_and_scores(self):
        uid=self.student()
        for vector in (np.zeros(192,dtype=np.float32),np.ones(10,dtype=np.float32),np.full(192,np.nan,dtype=np.float32)):
            self.assertFalse(self.attendance.add_voice_embedding(uid,vector)['status'])
        self.assertFalse(self.attendance.mark_attendance(uid,confidence=float('nan'))['status'])

class AudioTests(unittest.TestCase):
    def wav(self, seconds, sr=16000, silent=False):
        t=np.arange(int(sr*seconds))/sr
        audio=np.zeros_like(t) if silent else .2*np.sin(2*np.pi*220*t)
        buffer=io.BytesIO()
        sf.write(buffer,audio,sr,format='WAV')
        buffer.seek(0)
        return buffer

    def test_duration_and_silence_rejected(self):
        processor=AudioProcessor()
        for audio in (self.wav(.5),self.wav(31),self.wav(3,silent=True)):
            with self.assertRaises(ValueError): processor.process_file(audio)

    def test_resample_and_valid_audio(self):
        processed=AudioProcessor().process_file(self.wav(3,sr=48000))
        self.assertEqual(len(processed),48000)
        self.assertTrue(np.isfinite(processed).all())
        self.assertAlmostEqual(float(processed.std()),1,places=4)

if __name__ == '__main__':
    unittest.main()
