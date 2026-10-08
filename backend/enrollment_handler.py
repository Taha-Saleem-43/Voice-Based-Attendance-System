"""Atomic enrollment with faculty scope checked against the database."""
import logging
from backend.auth_handler import password_hash
from backend.config import local_now

class EnrollmentHandler:
    def __init__(self, db_handler, actor_user_id=None):
        self.db = db_handler
        self.actor_user_id = actor_user_id

    def _enroll(self, username, password, role, fields):
        username = username.strip()
        if not username or len(username) > 100 or not str(fields.get('name', '')).strip():
            return {'status': False, 'message': 'Username and full name are required (username: 1-100 characters).'}
        if role == 'student' and not fields['roll_no'].strip():
            return {'status': False, 'message': 'Roll number is required.'}
        try:
            hashed = password_hash(password)
            with self.db.transaction() as conn:
                if self.actor_user_id is not None:
                    actor = conn.execute('SELECT role,is_active FROM users WHERE user_id=?', (self.actor_user_id,)).fetchone()
                    if not actor or not actor['is_active']:
                        raise ValueError('Your account is unavailable. Log in again.')
                    if actor['role'] == 'faculty':
                        profile = conn.execute('SELECT dept_id FROM faculty WHERE user_id=?', (self.actor_user_id,)).fetchone()
                        if role != 'student' or not profile or profile['dept_id'] != fields['dept_id']:
                            raise ValueError('Faculty may enroll students only in their own department.')
                    elif actor['role'] != 'chairman':
                        raise ValueError('Enrollment is not permitted for your role.')
                for key, table, column in (
                    ('dept_id', 'departments', 'dept_id'),
                    ('section_id', 'sections', 'section_id'),
                    ('semester_id', 'semesters', 'semester_id'),
                ):
                    if key in fields and fields[key] is not None:
                        if not conn.execute(f'SELECT 1 FROM {table} WHERE {column}=?', (fields[key],)).fetchone():
                            raise ValueError(f'Choose an existing {key.removesuffix("_id")}.')
                if conn.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
                    raise ValueError('Username already exists.')
                if role == 'student' and conn.execute('SELECT 1 FROM students WHERE roll_no=?', (fields['roll_no'].strip(),)).fetchone():
                    raise ValueError('Roll number already exists.')
                user = conn.execute(
                    'INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,?,?) RETURNING user_id',
                    (username, hashed, role, local_now().isoformat())).fetchone()
                user_id = user['user_id']
                table = {'student': 'students', 'teacher': 'teachers', 'faculty': 'faculty'}[role]
                columns = ['user_id', *fields]
                values = [user_id, *(v.strip() if isinstance(v, str) else v for v in fields.values())]
                conn.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', values)
            return {'status': True, 'message': f'{role.title()} enrolled successfully.', 'user_id': user_id}
        except ValueError as exc:
            return {'status': False, 'message': str(exc)}
        except Exception:
            logging.exception('Enrollment failed; transaction rolled back')
            return {'status': False, 'message': 'Enrollment failed. Check for duplicate usernames or roll numbers.'}

    def enroll_student(self, username, password, roll_no, name, dept_id, semester_id, section_id):
        return self._enroll(username, password, 'student', dict(roll_no=roll_no, name=name, dept_id=dept_id, semester_id=semester_id, section_id=section_id))

    def enroll_teacher(self, username, password, name, dept_id, designation=None, section_id=None):
        return self._enroll(username, password, 'teacher', dict(name=name, dept_id=dept_id, designation=designation, section_id=section_id))

    def enroll_faculty(self, username, password, name, dept_id, designation=None):
        return self._enroll(username, password, 'faculty', dict(name=name, dept_id=dept_id, designation=designation))
