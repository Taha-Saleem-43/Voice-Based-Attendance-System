"""SQLite locally, PostgreSQL when DATABASE_URL is set."""
import sqlite3
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from backend.config import DB_PATH, setting

class Connection:
    def __init__(self, raw, postgres):
        self.raw, self.postgres = raw, postgres

    def execute(self, query, params=()):
        # Application SQL uses positional placeholders, never quoted ? literals.
        return self.raw.execute(query.replace('?', '%s') if self.postgres else query, params)

class DatabaseHandler:
    def __init__(self, db_path=None, database_url=None):
        self.url = database_url if database_url is not None else (None if db_path is not None else setting('DATABASE_URL'))
        self.postgres = bool(self.url)
        if self.postgres and not self.url.startswith(('postgresql://', 'postgres://')):
            raise ValueError('DATABASE_URL must be a PostgreSQL connection URL.')
        self.db_path = str(Path(db_path or DB_PATH).resolve())
        initialize(self.url, self.db_path)

    def _connect(self):
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=15)
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    @contextmanager
    def transaction(self):
        raw = self._connect()
        try:
            yield Connection(raw, self.postgres)
            raw.commit()
        except BaseException:
            raw.rollback()
            raise
        finally:
            raw.close()

    def execute(self, query, params=(), fetch=False, fetchone=False):
        with self.transaction() as conn:
            cursor = conn.execute(query, params)
            if fetchone:
                row = cursor.fetchone()
                return dict(row) if row is not None else None
            if fetch:
                return [dict(row) for row in cursor.fetchall()]
            return None

@lru_cache(maxsize=16)
def initialize(url, path):
    """Create missing tables without replacing existing users or recordings."""
    postgres = bool(url)
    if postgres:
        import psycopg
        raw = psycopg.connect(url, connect_timeout=15)
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(path, timeout=30)
        raw.execute('PRAGMA foreign_keys = ON')
        raw.execute('PRAGMA journal_mode = WAL')
    schema = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
    if postgres:
        schema = schema.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY').replace('BLOB', 'BYTEA')
    try:
        if postgres:
            # Serialize first-run schema setup across simultaneous app sessions.
            raw.execute('SELECT pg_advisory_xact_lock(812734901)')
        for statement in schema.split(';'):
            if statement.strip():
                raw.execute(statement)
        raw.commit()
    except BaseException:
        raw.rollback()
        raise
    finally:
        raw.close()
