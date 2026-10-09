"""Teacher workspace restricted to the assigned student group."""
import streamlit as st
from ui.layout import inject_css,role_guard,logout_button,error_boundary
from ui.workspace import navigation,personal_attendance,records_table
from backend.attendance_handler import AttendanceHandler

st.set_page_config(page_title='Teacher · VBAS',page_icon='👨‍🏫',layout='wide',initial_sidebar_state='collapsed')
inject_css()
db=role_guard('teacher')
view=navigation('teacher','Teacher Dashboard','Your attendance and the records for your assigned students.',['My attendance','Student attendance','Help'])
with error_boundary('teacher-workspace'):
    attendance=AttendanceHandler(db)
    uid=st.session_state.user['user_id']
    if view=='My attendance':
        st.subheader('My attendance')
        personal_attendance(db,uid,'teacher_attendance')
    elif view=='Student attendance':
        st.subheader('Assigned students')
        profile=attendance.get_teacher_info(uid)
        if not profile or profile['section_id'] is None:
            st.info('Ask the chairman to assign your department and section before viewing student records.')
        else:
            rows=attendance.get_teacher_students_attendance(profile['dept_id'],profile['section_id'])
            records_table(rows,'teacher_students','No attendance records for your assigned students yet.')
    else:
        st.subheader('Campus check-in')
        st.write('Open the attendance hub to supervise voice check-ins. Ask the chairman to correct academic assignments; faculty manage student enrollment and voice profiles.')
logout_button('logout_teacher')
