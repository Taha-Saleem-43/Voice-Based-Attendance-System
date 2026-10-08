"""Run python -m backend.add_chairman after setting ADMIN_USERNAME and ADMIN_PASSWORD."""
from backend.database import DatabaseHandler
from backend.bootstrap import ensure_admin

if __name__ == '__main__':
    ensure_admin(DatabaseHandler())
    print('Administrator setup complete.')
