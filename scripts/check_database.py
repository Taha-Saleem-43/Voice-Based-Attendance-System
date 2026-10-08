"""Initialize configured storage and verify a connection, without printing credentials."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.database import DatabaseHandler

def main():
    try:
        db = DatabaseHandler()
        assert db.execute('SELECT 1 AS healthy',fetchone=True)['healthy'] == 1
    except Exception:
        print('Database check failed. Verify connection settings and network access.')
        raise SystemExit(1)
    print('Database initialized and reachable:', 'PostgreSQL' if db.postgres else 'local SQLite')

if __name__ == '__main__':
    main()
