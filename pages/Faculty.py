"""Faculty workspace scoped to the current department."""
import streamlit as st
from ui.layout import inject_css,role_guard,logout_button,error_boundary
from ui.workspace import navigation,records_table,personal_attendance,enrollment_form,voice_workspace
from backend.directory import faculty_department,department_students

st.set_page_config(page_title='Faculty · VBAS',page_icon='🧑‍🔬',layout='wide',initial_sidebar_state='collapsed')
inject_css()
db=role_guard('faculty')
view=navigation('faculty','Faculty Dashboard','Enroll students and manage voice profiles within your department.',
                ['My attendance','Students','Enroll student','Voice profiles'])
uid=st.session_state.user['user_id']
with error_boundary('faculty-workspace'):
    department=faculty_department(db,uid)
    if not department:
        st.warning('Your academic department is missing. Ask the chairman to complete your profile.')
    elif view=='My attendance':
        st.subheader('My attendance')
        personal_attendance(db,uid,'faculty_attendance')
    elif view=='Students':
        st.subheader(f"Students · {department['dept_name']}")
        people=department_students(db,department['dept_id'])
        records_table([{**{k:v for k,v in p.items() if k!='is_active'},'status':'Active' if p['is_active'] else 'Suspended'} for p in people],'faculty_students','No students enrolled yet. Open Enroll student to add the first student.')
    elif view=='Enroll student':
        enrollment_form(db,'student',department)
    elif view=='Voice profiles':
        people=[p for p in department_students(db,department['dept_id']) if p['is_active']]
        voice_workspace(db,people,'faculty_voice')
logout_button('logout_faculty')
