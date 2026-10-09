"""Authorized administrative mutations with stale-state checks."""
import sqlite3
from backend.errors import ValidationError
from backend.reference_cache import REFERENCE_COLUMNS,invalidate_references
from backend.audit import audit_event

def _chairman(conn,actor_id):
    actor=conn.execute("SELECT 1 FROM users WHERE user_id=? AND role='chairman' AND is_active=1"+(' FOR SHARE' if conn.postgres else ''),(actor_id,)).fetchone()
    if not actor:
        raise ValidationError('Your account cannot perform this action. Sign in again.')

def set_account_state(db,actor_id,user_id,expected_active,active):
    with db.transaction() as conn:
        _chairman(conn,actor_id)
        row=conn.execute("UPDATE users SET is_active=? WHERE user_id=? AND is_active=? AND role!='chairman' RETURNING user_id",(int(active),user_id,int(expected_active))).fetchone()
        if not row:
            raise ValidationError('This account changed or is unavailable. Refresh the directory and try again.')
        audit_event(conn,actor_id,'account-reactivated' if active else 'account-suspended',user_id)

def delete_reference(db,actor_id,table,record_id):
    if table not in REFERENCE_COLUMNS:
        raise ValidationError('Choose a supported academic group.')
    id_column,_=REFERENCE_COLUMNS[table]
    try:
        with db.transaction() as conn:
            _chairman(conn,actor_id)
            row=conn.execute(f'DELETE FROM {table} WHERE {id_column}=? RETURNING {id_column}',(record_id,)).fetchone()
            if not row:
                raise ValidationError('This record was already removed. Refresh the list.')
            audit_event(conn,actor_id,f'{table}-removed',record_id)
    except Exception as exc:
        if isinstance(exc,sqlite3.IntegrityError) or getattr(exc,'sqlstate',None)=='23503':
            raise ValidationError('This record is in use by campus accounts or attendance. Reassign those records before removing it.') from None
        raise
    invalidate_references(db,table)

def delete_voice_sample(db,actor_id,embedding_id):
    with db.transaction() as conn:
        actor=conn.execute('SELECT role,is_active FROM users WHERE user_id=?',(actor_id,)).fetchone()
        if not actor or not actor['is_active'] or actor['role'] not in ('chairman','faculty'):
            raise ValidationError('Your account cannot remove this voice sample.')
        row=conn.execute('SELECT user_id FROM voice_embeddings WHERE embedding_id=?',(embedding_id,)).fetchone()
        if not row:
            raise ValidationError('This voice sample was already removed. Refresh the list.')
        if actor['role']=='faculty':
            allowed=conn.execute('SELECT 1 FROM students s JOIN faculty f ON s.dept_id=f.dept_id WHERE s.user_id=? AND f.user_id=?',(row['user_id'],actor_id)).fetchone()
            if not allowed:
                raise ValidationError('You can manage voice samples only for students in your department.')
        conn.execute('DELETE FROM voice_embeddings WHERE embedding_id=?',(embedding_id,))
        audit_event(conn,actor_id,'voice-sample-removed',embedding_id)
