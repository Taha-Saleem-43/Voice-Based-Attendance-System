import streamlit as st
from backend.reference_cache import reference_rows
from backend.reference_handler import add_reference
from backend.errors import ValidationError,report_error

def reference_form(db,table,label,button):
    notice_key=f'reference_notice_{table}'
    notice=st.session_state.pop(notice_key,None)
    if notice:
        getattr(st,notice[0])(notice[1])
    revision=st.session_state.get(f'reference_revision_{table}',0)
    with st.form(f'add_{table}_{revision}',enter_to_submit=True):
        if table=='semesters':
            value=int(st.number_input('Semester Number',min_value=1,max_value=8,step=1))
        else:
            value=st.text_input(f'{label} Name',max_chars=100,placeholder=f'Enter {label.lower()} name')
        st.caption('Press Enter or use the Add button to save. Duplicate records are not added.')
        submitted=st.form_submit_button(button,type='primary',use_container_width=True)
    if submitted:
        try:
            inserted=add_reference(db,st.session_state.user['user_id'],table,value)
        except ValidationError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(report_error('reference-creation',exc))
        else:
            text=f'{label} {str(value).strip()} added successfully.' if inserted else f'{label} {str(value).strip()} already exists. No duplicate was added.'
            st.session_state[notice_key]=('success' if inserted else 'info',text)
            if inserted:
                st.session_state[f'reference_revision_{table}']=revision+1
            st.rerun()

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
