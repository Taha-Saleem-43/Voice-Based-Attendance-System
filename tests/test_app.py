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
        app = AppTest.from_file(str(ROOT/'pages/chairman.py'),default_timeout=20)
        app.session_state.user=self.admin
        app.run()
        self.assertEqual(len(app.exception),0)
        semester=next(widget for widget in app.number_input if widget.label=='Semester Number')
        semester.set_value(2)
        next(button for button in app.button if 'Add Semester' in button.label).click().run()
        self.assertEqual(len(app.exception),0)
        self.assertIsNotNone(self.db.execute('SELECT 1 FROM semesters WHERE semester_no=2',fetchone=True))

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

if __name__ == '__main__':
    unittest.main()
