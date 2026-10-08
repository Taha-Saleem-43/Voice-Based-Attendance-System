import streamlit as st
from backend.reference_cache import reference_rows

def reference_select(db, label, table, id_column, name_column, key):
    allowed = {('departments','dept_id','dept_name'), ('sections','section_id','section_name'), ('semesters','semester_id','semester_no')}
    if (table,id_column,name_column) not in allowed:
        raise ValueError('Unsupported reference table.')
    rows = reference_rows(db,table)
    choices = {row[id_column]: str(row[name_column]) for row in rows}
    if not choices:
        st.caption(f'Ask the chairman to add {label.lower()} records first.')
        return None
    return st.selectbox(label, list(choices), format_func=choices.get, key=key)
