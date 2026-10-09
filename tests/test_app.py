"""Streamlit page wiring, using temporary data and a stub for expensive model loading."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.database import DatabaseHandler
from backend.auth_handler import AuthHandler
from backend.enrollment_handler import EnrollmentHandler
from backend.reference_cache import reference_rows

class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'test.db'
        self.db = DatabaseHandler(self.path)
        self.auth = AuthHandler(self.db)
        self.auth.create_user('admin','Test-password-42','chairman')
        self.admin = self.auth.login('admin','Test-password-42')
        self.db.execute("INSERT INTO departments (dept_name) VALUES ('Computing')")
        self.db.execute("INSERT INTO semesters (semester_no) VALUES (1)")
        self.db.execute("INSERT INTO sections (section_name) VALUES ('A')")
        self.path_patch = patch('backend.database.DB_PATH',self.path)
        self.path_patch.start()
        self.url_patch = patch('backend.database.setting',return_value=None)
        self.url_patch.start()
        self.model_patch = patch('backend.resources.load_models',return_value=(object(),object()))
        self.model_loader = self.model_patch.start()

    def tearDown(self):
        self.model_patch.stop()
        self.url_patch.stop()
        self.path_patch.stop()
        self.tmp.cleanup()

    def test_home_and_login(self):
        app = AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
        self.assertEqual(len(app.exception),0)
        app.text_input[0].set_value('admin')
        app.text_input[1].set_value('Test-password-42')
        login=next(button for button in app.button if 'Login' in button.label)
        with patch('streamlit.switch_page') as switch:
            login.click().run()
        switch.assert_called_once_with('pages/chairman.py')
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.session_state.user['role'],'chairman')
        self.model_loader.assert_not_called()

    def test_chairman_and_semester_form(self):
        reference_rows(self.db,'semesters')
        app = AppTest.from_file(str(ROOT/'pages/chairman.py'),default_timeout=20)
        app.session_state.user=self.admin
        app.session_state.chairman_view='Academic setup'
        app.session_state.academic_type='semesters'
        app.run()
        self.assertEqual(len(app.exception),0)
        semester=next(widget for widget in app.number_input if widget.label=='Semester Number')
        semester.set_value(2)
        next(button for button in app.button if 'Add Semester' in button.label).click().run()
        self.assertEqual(len(app.exception),0)
        self.assertIsNotNone(self.db.execute('SELECT 1 FROM semesters WHERE semester_no=2',fetchone=True))
        self.assertTrue(any(row['semester_no']==2 for row in reference_rows(self.db,'semesters')))
        self.assertTrue(any('added successfully' in item.value for item in app.success))
        next(widget for widget in app.number_input if widget.label=='Semester Number').set_value(2)
        next(button for button in app.button if 'Add Semester' in button.label).click().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('already exists' in item.value for item in app.info))

    def test_all_role_pages(self):
        enroll=EnrollmentHandler(self.db)
        enroll.enroll_faculty('faculty','Test-password-42','Faculty',1)
        enroll.enroll_teacher('teacher','Test-password-42','Teacher',1,section_id=1)
        enroll.enroll_student('student','Test-password-42','R1','Student',1,1,1)
        for role,filename in [('faculty','Faculty.py'),('teacher','teacher.py'),('student','Student.py')]:
            with self.subTest(role=role):
                app=AppTest.from_file(str(ROOT/'pages'/filename),default_timeout=20)
                app.session_state.user=self.auth.login(role,'Test-password-42')
                app.run()
                self.assertEqual(len(app.exception),0)
                self.model_loader.assert_not_called()

    def test_login_redirects_each_campus_role(self):
        enroll=EnrollmentHandler(self.db)
        enroll.enroll_faculty('faculty','Test-password-42','Faculty',1)
        enroll.enroll_teacher('teacher','Test-password-42','Teacher',1,section_id=1)
        enroll.enroll_student('student','Test-password-42','R1','Student',1,1,1)
        for role in ('faculty','teacher','student'):
            with self.subTest(role=role):
                app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
                app.text_input[0].set_value(role)
                app.text_input[1].set_value('Test-password-42')
                with patch('streamlit.switch_page') as switch:
                    next(button for button in app.button if 'Login' in button.label).click().run()
                self.assertEqual(len(app.exception),0)
                filename={'faculty':'Faculty.py','teacher':'teacher.py','student':'Student.py'}[role]
                switch.assert_called_once_with(f'pages/{filename}')
                self.model_loader.assert_not_called()

    def test_student_cannot_open_chairman_page(self):
        EnrollmentHandler(self.db).enroll_student('student','Test-password-42','R1','Student',1,1,1)
        app=AppTest.from_file(str(ROOT/'pages/chairman.py'),default_timeout=20)
        app.session_state.user=self.auth.login('student','Test-password-42')
        app.run()
        self.assertEqual(len(app.exception),0)
        self.assertFalse(any('Create Teacher' in button.label for button in app.button))

    def test_model_failure_does_not_break_admin_forms(self):
        with patch('backend.resources.load_models',side_effect=RuntimeError('model unavailable')):
            app=AppTest.from_file(str(ROOT/'pages/chairman.py'),default_timeout=20)
            app.session_state.user=self.admin
            app.session_state.chairman_view='Create account'
            app.run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('Create Teacher' in button.label for button in app.button))

    def test_suspended_session_is_cleared(self):
        result=EnrollmentHandler(self.db).enroll_faculty('faculty','Test-password-42','Faculty',1)
        session=self.auth.login('faculty','Test-password-42')
        self.auth.set_user_active(result['user_id'],False)
        app=AppTest.from_file(str(ROOT/'pages/Faculty.py'),default_timeout=20)
        app.session_state.user=session
        app.run()
        self.assertEqual(len(app.exception),0)
        self.assertIsNone(app.session_state.user)

    def test_all_workspace_sections_render_without_loading_model(self):
        enroll=EnrollmentHandler(self.db)
        enroll.enroll_faculty('faculty','Test-password-42','Faculty',1)
        enroll.enroll_teacher('teacher','Test-password-42','Teacher',1,section_id=1)
        enroll.enroll_student('student','Test-password-42','R1','Student',1,1,1)
        cases=[('chairman','chairman.py',self.admin,['Overview','Attendance','Directory','Create account','Academic setup','Voice profiles']),
               ('faculty','Faculty.py',self.auth.login('faculty','Test-password-42'),['My attendance','Students','Enroll student','Voice profiles']),
               ('teacher','teacher.py',self.auth.login('teacher','Test-password-42'),['My attendance','Student attendance','Help']),
               ('student','Student.py',self.auth.login('student','Test-password-42'),['My attendance','Help'])]
        for role,filename,session,views in cases:
            for view in views:
                with self.subTest(role=role,view=view):
                    app=AppTest.from_file(str(ROOT/'pages'/filename),default_timeout=60)
                    app.session_state.user=session
                    app.session_state[f'{role}_view']=view
                    app.run()
                    self.assertEqual(len(app.exception),0)
                    self.assertEqual(len(app.error),0)
                    self.model_loader.assert_not_called()

    def test_database_error_never_displays_sensitive_payload(self):
        app=AppTest.from_file(str(ROOT/'pages/chairman.py'),default_timeout=60)
        app.session_state.user=self.admin
        app.session_state.chairman_view='Directory'
        payload='postgresql://secret-user:secret-password@private-host SELECT password_hash certificate PRIVATE KEY'
        with patch('backend.directory.campus_accounts',side_effect=RuntimeError(payload)),self.assertLogs(level='ERROR') as logs:
            app.run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('reference' in item.value for item in app.error))
        self.assertNotIn(payload,' '.join(item.value for item in app.error))
        self.assertNotIn(payload,' '.join(logs.output))

    def test_enrollment_preserves_invalid_inputs_and_clears_success(self):
        app=AppTest.from_file(str(ROOT/'pages/chairman.py'),default_timeout=60)
        app.session_state.user=self.admin
        app.session_state.chairman_view='Create account'
        app.run()
        next(w for w in app.text_input if w.label=='Username').set_value('newteacher')
        next(w for w in app.text_input if w.label=='Full name').set_value('New Teacher')
        next(w for w in app.text_input if w.label=='Password').set_value('Test-password-42')
        next(w for w in app.text_input if w.label=='Confirm password').set_value('wrong')
        next(w for w in app.button if w.label=='Create Teacher').click().run()
        self.assertTrue(any('do not match' in item.value for item in app.warning))
        self.assertEqual(next(w for w in app.text_input if w.label=='Username').value,'newteacher')
        self.assertIsNone(self.db.execute("SELECT 1 FROM users WHERE username='newteacher'",fetchone=True))
        next(w for w in app.text_input if w.label=='Confirm password').set_value('Test-password-42')
        next(w for w in app.button if w.label=='Create Teacher').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('was created' in item.value for item in app.success))
        self.assertEqual(next(w for w in app.text_input if w.label=='Password').value,'')

    def test_removal_requires_confirmation(self):
        self.db.execute("INSERT INTO departments (dept_name) VALUES ('Unused')")
        app=AppTest.from_file(str(ROOT/'pages/chairman.py'),default_timeout=60)
        app.session_state.user=self.admin
        app.session_state.chairman_view='Academic setup'
        app.run()
        next(w for w in app.selectbox if w.label=='Record to remove').set_value(2).run()
        next(w for w in app.button if w.label=='Remove selected record').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('Confirm removal' in item.value for item in app.warning))
        self.assertIsNotNone(self.db.execute('SELECT 1 FROM departments WHERE dept_id=2',fetchone=True))

    def test_directory_navigation_is_bounded_and_search_resets_cursor(self):
        with self.db.transaction() as conn:
            for i in range(160):
                conn.execute("INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,'student','fixture')",(f'qa{i:03d}',b'fixture'))
        app=AppTest.from_file(str(ROOT/'pages/chairman.py'),default_timeout=60)
        app.session_state.user=self.admin
        app.session_state.chairman_view='Directory'
        app.run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.error),0,[item.value for item in app.error])
        self.assertEqual(len(app.dataframe[0].value),100)
        next(b for b in app.button if b.label=='Next page').click().run()
        self.assertEqual(len(app.dataframe[0].value),60)
        next(w for w in app.text_input if w.label=='Search all records').set_value('qa155').run()
        self.assertEqual(len(app.dataframe[0].value),1)
        self.assertEqual(app.dataframe[0].value.iloc[0]['Username'],'qa155')
        self.assertTrue(any('Page 1' in c.value for c in app.caption))

if __name__ == '__main__':
    unittest.main()
