from backend.errors import ValidationError
"""Secure first-run administrator creation from deployment secrets."""
from backend.config import setting
from backend.auth_handler import AuthHandler

def ensure_admin(db):
    if db.execute("SELECT 1 FROM users WHERE role='chairman' AND is_active=1", fetchone=True):
        return
    username = setting('ADMIN_USERNAME')
    password = setting('ADMIN_PASSWORD')
    if not username or not password or password == 'REPLACE_WITH_A_LONG_UNIQUE_PASSWORD':
        raise ValidationError('Set ADMIN_USERNAME and ADMIN_PASSWORD in deployment secrets, then restart.')
    result = AuthHandler(db).create_user(username, password, 'chairman')
    if not result['status']:
        # Handle simultaneous first visits without resetting existing passwords.
        if not db.execute("SELECT 1 FROM users WHERE role='chairman' AND is_active=1", fetchone=True):
            raise ValidationError(result['message'])
