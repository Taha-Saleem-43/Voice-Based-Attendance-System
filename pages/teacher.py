import streamlit as st
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages._ui import inject_css, page_header, section, role_guard, logout_button
from backend.attendance_handler import AttendanceHandler
from backend.auth_handler import DatabaseHandler
from backend.enrollment_handler import EnrollmentHandler
import pandas as pd

st.set_page_config(
    page_title="Teacher · VBAS",
    page_icon="👨‍🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

inject_css()
role_guard("teacher")

page_header("👨‍🏫", "Teacher Dashboard",
            "View your attendance and manage student records",
            role="teacher")

db = DatabaseHandler()
attendance = AttendanceHandler()
enroll = EnrollmentHandler(db)
user_id = st.session_state.user["user_id"]
username = st.session_state.user["username"]

# ─── My Attendance ────────────────────────────────────────────────────────────
section("📅 My Attendance Records")
try:
    data = attendance.get_user_attendance(user_id)
    if data:
        df = pd.DataFrame(data)
        # KPI
        kc1, kc2, kc3 = st.columns(3)
        with kc1:
            st.metric("📋 Total Days", len(df))
        with kc2:
            if 'confidence' in df.columns and df['confidence'].notna().any():
                avg_conf = df['confidence'].mean()
                st.metric("🎯 Avg Similarity", f"{avg_conf:.3f}")
        with kc3:
            if 'date' in df.columns:
                last = df['date'].iloc[0] if len(df) > 0 else "—"
                st.metric("📆 Last Marked", str(last))

        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥  Export My Attendance", csv, "my_attendance.csv", "text/csv")
    else:
        st.info("No attendance records found yet. Mark attendance from the main page.")
except Exception as e:
    st.error(f"Error fetching attendance: {e}")

# ─── Students Attendance ──────────────────────────────────────────────────────
section("📝 My Students' Attendance")
teacher_info = attendance.get_teacher_info(user_id)
if not teacher_info:
    st.warning("Your teacher profile is not fully set up. Contact the chairman to assign a department and section.")
    logout_button("logout_1")
    st.stop()

try:
    students_attendance = attendance.get_teacher_students_attendance(
        dept_id=teacher_info["dept_id"],
        section_id=teacher_info["section_id"]
    )

    if students_attendance:
        df_s = pd.DataFrame(students_attendance)

        # Stats
        kc1, kc2 = st.columns(2)
        with kc1:
            st.metric("👥 Total Records", len(df_s))
        with kc2:
            unique_students = df_s['roll_no'].nunique() if 'roll_no' in df_s.columns else 0
            st.metric("🎓 Unique Students", unique_students)

        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 You can view this table — for edits please contact the chairman.")
        st.dataframe(df_s, use_container_width=True, hide_index=True)

        csv_s = df_s.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥  Download Students CSV",
            csv_s,
            "students_attendance.csv",
            "text/csv"
        )
    else:
        st.info("No attendance records found for your assigned students yet.")
except Exception as e:
    st.error(f"Error fetching student attendance: {e}")

logout_button("logout_teacher")
