"""Personal student attendance workspace."""
import streamlit as st
from ui.layout import inject_css,role_guard,logout_button,error_boundary
from ui.workspace import navigation,personal_attendance

st.set_page_config(page_title='Student · VBAS',page_icon='🎓',layout='wide',initial_sidebar_state='collapsed')
inject_css()
db=role_guard('student')
view=navigation('student','Student Dashboard','View and export your own attendance records.',['My attendance','Help'])
with error_boundary('student-workspace'):
    if view=='My attendance':
        st.subheader('My attendance')
        personal_attendance(db,st.session_state.user['user_id'],'student_attendance')
    else:
        st.subheader('Attendance support')
        st.write('Visit a supervised campus station to check in. Your faculty member can help with enrollment or a failed voice match.')
        st.info('If an attendance record is missing, contact your faculty member. Voice similarity is a matching score, not an attendance percentage.')
logout_button('logout_student')
