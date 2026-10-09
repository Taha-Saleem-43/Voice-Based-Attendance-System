"""Bounded PostgreSQL connections shared by Streamlit sessions in this process."""
import atexit
import logging
from threading import Lock
from backend.config import setting

_pools = {}
_lock = Lock()

def postgres_pool(url):
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    with _lock:
        if url not in _pools:
            maximum = max(1, min(20, int(setting('DB_POOL_SIZE', '4'))))
            # Pool worker logs may include connection details on failure.
            logging.getLogger('psycopg.pool').disabled = True
            pool = ConnectionPool(
                conninfo=url, min_size=0, max_size=maximum, max_waiting=32,
                timeout=10, max_idle=120, max_lifetime=1800, open=True,
                kwargs={'row_factory': dict_row, 'connect_timeout': 10,
                        'prepare_threshold': None,
                        'options': '-c statement_timeout=15000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=20000'},
                check=ConnectionPool.check_connection)
            _pools[url] = pool
            atexit.register(pool.close)
        return _pools[url]
