from backend.errors import ValidationError, report_error
"""Atomic, duplicate-safe academic reference creation."""
from backend.reference_cache import REFERENCE_COLUMNS,invalidate_references
from backend.audit import audit_event

def add_reference(db,actor_id,table,value):
    if table not in REFERENCE_COLUMNS:
        raise ValidationError('Unsupported reference table.')
    if table=='semesters':
        if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=8:
            raise ValidationError('Choose a semester from 1 to 8.')
    else:
        value=' '.join(str(value).split())
        if not value or len(value)>100:
            raise ValidationError('Enter a name of 1–100 characters.')
    id_column,name_column=REFERENCE_COLUMNS[table]
    with db.transaction() as conn:
        actor=conn.execute("SELECT 1 FROM users WHERE user_id=? AND role='chairman' AND is_active=1",(actor_id,)).fetchone()
        if not actor:
            raise ValidationError('An active chairman account is required.')
        row=conn.execute(f'INSERT INTO {table} ({name_column}) VALUES (?) ON CONFLICT ({name_column}) DO NOTHING RETURNING {id_column}',(value,)).fetchone()
        if row: audit_event(conn,actor_id,f'{table}-created',row[id_column])
    invalidate_references(db,table)
    return bool(row)
