"""Bounded cache for public campus reference lists, isolated by database."""
import hashlib
import streamlit as st

REFERENCE_COLUMNS={
    'departments':('dept_id','dept_name'),
    'sections':('section_id','section_name'),
    'semesters':('semester_id','semester_no'),
}

def _identity(db):
    return hashlib.sha256((db.url or db.db_path).encode()).hexdigest()

@st.cache_data(ttl=60,max_entries=48,show_spinner=False)
def _read(identity,table,_db):
    id_column,name_column=REFERENCE_COLUMNS[table]
    return _db.execute(f'SELECT {id_column},{name_column} FROM {table} ORDER BY {name_column}',fetch=True)

def reference_rows(db,table):
    if table not in REFERENCE_COLUMNS:
        raise ValueError('Unsupported reference table.')
    return _read(_identity(db),table,db)

def invalidate_references(db,table):
    if table not in REFERENCE_COLUMNS:
        raise ValueError('Unsupported reference table.')
    _read.clear(_identity(db),table,db)
