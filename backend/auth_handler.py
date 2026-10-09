from backend.errors import ValidationError, report_error
import time
import bcrypt
from backend.database import DatabaseHandler
from backend.config import local_now

def password_hash(password):
    size = len(password.encode('utf-8'))
    if size < 10 or size > 72:
        raise ValidationError('Password must be at least 10 UTF-8 bytes and at most 72 bytes.')
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

class AuthHandler:
    def __init__(self, db_handler):
        self.db = db_handler

    def create_user(self, username, password, role):
        username = username.strip()
        if not username or len(username) > 100:
            return {'status': False, 'message': 'Enter a username of 1-100 characters.'}
        if role not in ('student', 'teacher', 'faculty', 'chairman'):
            return {'status': False, 'message': 'Invalid role.'}
        try:
            hashed = password_hash(password)
            row = self.db.execute(
                'INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,?,?) '
                'ON CONFLICT (username) DO NOTHING RETURNING user_id',
                (username, hashed, role, local_now().isoformat()), fetchone=True)
            if not row:
                return {'status': False, 'message': 'Username already exists.'}
            return {'status': True, 'message': 'User created successfully.', 'user_id': row['user_id']}
        except ValueError as exc:
            return {'status': False, 'message': str(exc)}

    def login(self, username, password):
        username = username.strip()
        failure = {'status': False, 'message': 'Invalid credentials or account unavailable.'}
        if not username or len(username) > 100 or len(password.encode('utf-8')) > 72:
            return failure
        now = time.time()
        attempt = self.db.execute('SELECT * FROM login_attempts WHERE username=?', (username,), fetchone=True)
        if attempt and attempt['failures'] >= 5 and attempt['blocked_until'] > now:
            return {'status': False, 'message': 'Too many attempts. Try again in 15 minutes.'}
        user = self.db.execute(
            'SELECT user_id,username,password_hash,role FROM users WHERE username=? AND is_active=1',
            (username,), fetchone=True)
        valid = False
        if user:
            hashed = user['password_hash']
            if isinstance(hashed, str):
                hashed = hashed.encode('utf-8')
            try:
                valid = bcrypt.checkpw(password.encode('utf-8'), bytes(hashed))
            except ValueError:
                valid = False
        if not valid:
            self.db.execute(
                'INSERT INTO login_attempts (username,failures,blocked_until) VALUES (?,1,?) '
                'ON CONFLICT (username) DO UPDATE SET '
                'failures=CASE WHEN login_attempts.blocked_until <= ? THEN 1 ELSE login_attempts.failures+1 END, '
                'blocked_until=CASE WHEN login_attempts.blocked_until <= ? THEN ? ELSE login_attempts.blocked_until END',
                (username, now + 900, now, now, now + 900))
            return failure
        self.db.execute('DELETE FROM login_attempts WHERE username=?', (username,))
        return {'status': True, 'user_id': user['user_id'], 'username': user['username'], 'role': user['role'], 'logged_at': time.time()}

    def set_user_active(self, user_id, is_active=True):
        self.db.execute("UPDATE users SET is_active=? WHERE user_id=? AND role != 'chairman'", (int(is_active), user_id))
        return {'status': True, 'message': 'User status updated.'}
