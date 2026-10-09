"""Security and capacity boundaries, independent of pretrained inference."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock,patch
import numpy as np
import test_backend
from backend.records import attendance_page
from backend.directory import campus_accounts,department_students
from backend.errors import ValidationError
from backend.checkin import VoiceCheckinService
from backend.inference_capacity import InferenceCapacity

class ScaleTests(unittest.TestCase):
    setUp=test_backend.BackendTests.setUp
    tearDown=test_backend.BackendTests.tearDown
    student=test_backend.BackendTests.student

    def admin(self):
        return self.auth.create_user('admin',test_backend.PASSWORD,'chairman')['user_id']

    def test_directory_pages_are_bounded_and_do_not_skip_or_repeat(self):
        admin=self.admin()
        with self.db.transaction() as conn:
            for i in range(235):
                conn.execute("INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,'student','fixture')",(f'fixture{i}',b'fixture'))
        first=campus_accounts(self.db,actor_id=admin,limit=100)
        second=campus_accounts(self.db,actor_id=admin,limit=100,after=first[-1]['user_id'])
        third=campus_accounts(self.db,actor_id=admin,limit=100,after=second[-1]['user_id'])
        self.assertEqual([len(first),len(second),len(third)],[100,100,35])
        self.assertEqual(len({r['user_id'] for r in first+second+third}),235)
        self.assertFalse(any('password_hash' in r for r in first))
        with self.assertRaises(ValidationError): campus_accounts(self.db,actor_id=admin,limit=10000)

    def test_search_treats_wildcards_as_literal_input(self):
        admin=self.admin(); self.student('percent%name')
        self.student('ordinary','R2')
        rows=campus_accounts(self.db,actor_id=admin,search='%')
        self.assertEqual([r['username'] for r in rows],['percent%name'])

    def test_read_scope_is_enforced_at_data_boundary(self):
        admin=self.admin(); own=self.student()
        foreign=self.enroll.enroll_student('foreign',test_backend.PASSWORD,'R2','Other',2,1,1)['user_id']
        teacher=self.enroll.enroll_teacher('teacher',test_backend.PASSWORD,'Teacher',1,section_id=1)['user_id']
        faculty=self.enroll.enroll_faculty('faculty',test_backend.PASSWORD,'Faculty',1)['user_id']
        for uid in (own,foreign): self.attendance.mark_attendance(uid)
        self.assertEqual(len(attendance_page(self.db,admin)),2)
        self.assertEqual([r['username'] for r in attendance_page(self.db,teacher)],['student'])
        self.assertEqual([r['username'] for r in attendance_page(self.db,own)],['student'])
        with self.assertRaises(ValidationError): campus_accounts(self.db,actor_id=own)
        with self.assertRaises(ValidationError): department_students(self.db,2,actor_id=faculty)
        self.auth.set_user_active(teacher,False)
        with self.assertRaises(ValidationError): attendance_page(self.db,teacher)

    def test_attendance_cursor_handles_equal_dates_without_duplicates(self):
        admin=self.admin()
        for i in range(5): self.attendance.mark_attendance(self.student(f's{i}',f'R{i}'))
        first=attendance_page(self.db,admin,limit=3)
        last=first[-1]
        second=attendance_page(self.db,admin,limit=3,after=(last['date'],last['_record_id']))
        self.assertEqual(len(first+second),5)
        self.assertEqual(len({r['_record_id'] for r in first+second}),5)

    def test_username_verification_does_not_match_someone_else(self):
        admin=self.admin(); own=self.student()
        self.attendance.add_voice_embedding(own,np.ones(192,dtype=np.float32))
        model=Mock(); model.generate_embedding.return_value=np.ones(192,dtype=np.float32)
        model.compute_similarity.return_value=.99
        service=VoiceCheckinService(self.db,Mock(),model)
        with self.assertRaises(ValidationError): service.identify(object(),supervisor_id=admin,claimed_username='not-enrolled')
        model.generate_embedding.assert_not_called()
        self.assertTrue(service.identify(object(),supervisor_id=admin,claimed_username='student')['status'])

    def test_supervisor_suspension_during_inference_blocks_write(self):
        actor=self.enroll.enroll_faculty('faculty',test_backend.PASSWORD,'Faculty',1)['user_id']
        uid=self.student(); self.attendance.add_voice_embedding(uid,np.ones(192,dtype=np.float32))
        model=Mock()
        def infer(*args):
            self.auth.set_user_active(actor,False)
            return np.ones(192,dtype=np.float32)
        model.generate_embedding.side_effect=infer; model.compute_similarity.return_value=.99
        result=VoiceCheckinService(self.db,Mock(),model).identify(object(),supervisor_id=actor,claimed_username='student')
        self.assertFalse(result['status'])
        self.assertEqual(self.attendance.get_user_attendance(uid),[])

    def test_voice_enrollment_checks_current_actor_department_and_audits(self):
        uid=self.student()
        foreign=self.enroll.enroll_faculty('foreign',test_backend.PASSWORD,'Foreign',2)['user_id']
        self.assertFalse(self.attendance.add_voice_embedding(uid,np.ones(192,dtype=np.float32),actor_id=foreign)['status'])
        admin=self.admin()
        self.assertTrue(self.attendance.add_voice_embedding(uid,np.ones(192,dtype=np.float32),actor_id=admin)['status'])
        event=self.db.execute("SELECT actor_id,target_id FROM audit_events WHERE operation='voice-sample-enrolled'",fetchone=True)
        self.assertEqual(event,{'actor_id':admin,'target_id':uid})

    def test_overload_is_bounded_and_recovers_after_failure(self):
        capacity=InferenceCapacity(maximum=1,timeout=.1)
        with capacity.acquire():
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaises(ValidationError): pool.submit(lambda:self.use_capacity(capacity)).result()
        with self.assertRaises(RuntimeError):
            with capacity.acquire(): raise RuntimeError('fixture')
        self.use_capacity(capacity)

    @staticmethod
    def use_capacity(capacity):
        with capacity.acquire(): return True

    def test_pool_configuration_is_shared_bounded_and_prepared_statements_disabled(self):
        from backend.connection_pool import postgres_pool,_pools
        fake='postgresql://fixture.invalid/fixture'
        with patch('psycopg_pool.ConnectionPool') as constructor:
            first=postgres_pool(fake); second=postgres_pool(fake)
            self.assertIs(first,second); constructor.assert_called_once()
            kwargs=constructor.call_args.kwargs
            self.assertEqual(kwargs['max_size'],4)
            self.assertEqual(kwargs['max_waiting'],32)
            self.assertIsNone(kwargs['kwargs']['prepare_threshold'])
        _pools.pop(fake,None)
