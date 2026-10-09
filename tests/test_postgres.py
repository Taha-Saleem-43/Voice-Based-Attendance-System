"""Integration tests run only against the disposable CI PostgreSQL service."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from backend.database import DatabaseHandler
from backend.auth_handler import AuthHandler
from backend.enrollment_handler import EnrollmentHandler
from backend.attendance_handler import AttendanceHandler
from backend.records import attendance_page
from backend.management import set_account_state
from backend.connection_pool import postgres_pool

URL=os.environ.get('TEST_POSTGRES_URL')

@unittest.skipUnless(URL,'Disposable PostgreSQL integration service is not configured.')
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from psycopg.conninfo import conninfo_to_dict
        config=conninfo_to_dict(URL)
        if config.get('host') not in ('localhost','127.0.0.1') or config.get('dbname')!='vbas_test':
            raise RuntimeError('Integration tests require localhost and the disposable vbas_test database.')
        import psycopg
        with psycopg.connect(URL) as conn:
            for role in ('anon','authenticated'):
                if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():
                    conn.execute(f'CREATE ROLE {role} NOLOGIN')
            # Reproduce Supabase-style default API grants in the CI fixture.
            conn.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon,authenticated')
        cls.db=DatabaseHandler(database_url=URL)

    def setUp(self):
        self.db.execute('TRUNCATE audit_events,attendance,voice_embeddings,students,teachers,faculty,users,departments,semesters,sections,login_attempts RESTART IDENTITY CASCADE')
        self.auth=AuthHandler(self.db)
        self.admin=self.auth.create_user('fixture-admin','Fixture-password-42','chairman')['user_id']
        self.db.execute("INSERT INTO departments (dept_name) VALUES ('Fixture')")
        self.db.execute('INSERT INTO semesters (semester_no) VALUES (1)')
        self.db.execute("INSERT INTO sections (section_name) VALUES ('A')")
        result=EnrollmentHandler(self.db,self.admin).enroll_student('fixture-student','Fixture-password-42','R1','Fixture Student',1,1,1)
        self.assertTrue(result['status'],result)
        self.student=result['user_id']

    def test_concurrent_writes_are_idempotent(self):
        with ThreadPoolExecutor(max_workers=20) as pool:
            results=list(pool.map(lambda _:AttendanceHandler(self.db).mark_attendance(self.student,supervisor_id=self.admin),range(20)))
        self.assertEqual(sum(r['status'] for r in results),1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) AS n FROM attendance',fetchone=True)['n'],1)

    def test_pool_is_bounded_and_transactions_roll_back(self):
        with self.assertRaises(RuntimeError):
            with self.db.transaction() as conn:
                conn.execute("INSERT INTO departments (dept_name) VALUES ('Must Roll Back')")
                raise RuntimeError('fixture rollback')
        self.assertIsNone(self.db.execute("SELECT 1 FROM departments WHERE dept_name='Must Roll Back'",fetchone=True))
        with ThreadPoolExecutor(max_workers=12) as pool:
            rows=list(pool.map(lambda _:self.db.execute('SELECT 1 AS value,pg_sleep(0.01)',fetchone=True),range(36)))
        self.assertTrue(all(r['value']==1 for r in rows))
        self.assertLessEqual(postgres_pool(URL).get_stats()['pool_size'],4)

    def test_postgres_scoped_reads_and_suspension(self):
        AttendanceHandler(self.db).mark_attendance(self.student,supervisor_id=self.admin)
        rows=attendance_page(self.db,self.student,limit=101)
        self.assertEqual([r['username'] for r in rows],['fixture-student'])
        set_account_state(self.db,self.admin,self.student,1,False)
        self.assertFalse(AttendanceHandler(self.db).mark_attendance(self.student)['status'])
        self.assertFalse(self.auth.login('fixture-student','Fixture-password-42')['status'])
        self.assertEqual(self.db.execute("SELECT COUNT(*) AS n FROM audit_events WHERE operation='account-suspended'",fetchone=True)['n'],1)

    def test_postgres_cursor_search_and_foreign_keys(self):
        AttendanceHandler(self.db).mark_attendance(self.student)
        rows=attendance_page(self.db,self.admin,search='fixture-student',limit=1)
        self.assertEqual(len(rows),1)
        after=(rows[0]['date'],rows[0]['_record_id'])
        self.assertEqual(attendance_page(self.db,self.admin,after=after),[])
        from backend.management import delete_reference
        from backend.errors import ValidationError
        with self.assertRaises(ValidationError): delete_reference(self.db,self.admin,'departments',1)

    def test_schema_initialization_protects_tables_from_public_api_roles(self):
        rows=self.db.execute("SELECT tablename,rowsecurity FROM pg_tables WHERE schemaname='public'",fetch=True)
        self.assertEqual(len(rows),11)
        self.assertTrue(all(r['rowsecurity'] for r in rows))
        grants=self.db.execute("SELECT COUNT(*) AS n FROM information_schema.role_table_grants WHERE table_schema='public' AND grantee IN ('anon','authenticated')",fetchone=True)
        self.assertEqual(grants['n'],0)
