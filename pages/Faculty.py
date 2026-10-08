import streamlit as st
import warnings
import os
import sys

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages._ui import inject_css, page_header, section, role_guard, logout_button
from backend.attendance_handler import AttendanceHandler
from backend.auth_handler import DatabaseHandler
from backend.enrollment_handler import EnrollmentHandler
from backend.resources import load_models
from html import escape
from backend.reference_ui import reference_select
import pandas as pd

st.set_page_config(
    page_title="Faculty · VBAS",
    page_icon="🧑‍🔬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

inject_css()
role_guard("faculty")

page_header("🧑‍🔬", "Faculty Dashboard",
            "Manage student enrollment and voice biometric profiles",
            role="faculty")

db = DatabaseHandler()
attendance = AttendanceHandler(db)
enroll = EnrollmentHandler(db, actor_user_id=st.session_state.user["user_id"])
user_id = st.session_state.user["user_id"]





# ─── My Attendance ─────────────────────────────────────────────────────────
section("📅 My Attendance")
try:
    data = attendance.get_user_attendance(user_id)
    if data:
        df = pd.DataFrame(data)
        kc1, kc2, kc3 = st.columns(3)
        with kc1:
            st.metric("📋 Total Days", len(df))
        with kc2:
            if 'confidence' in df.columns and df['confidence'].notna().any():
                st.metric("🎯 Avg Similarity", f"{df['confidence'].mean():.3f}")
        with kc3:
            if 'date' in df.columns and len(df) > 0:
                st.metric("📆 Last Marked", str(df['date'].iloc[0]))
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No attendance records yet. Mark attendance from the main page.")
except Exception as e:
    st.error(f"Error: {e}")

# ─── Faculty Info ─────────────────────────────────────────────────────────
faculty_info = db.execute(
    "SELECT dept_id FROM faculty WHERE user_id = ?",
    (user_id,), fetchone=True
)
if not faculty_info:
    st.error("Faculty profile not found. Contact the chairman.")
    logout_button("logout_0")
    st.stop()

# ─── Enroll Student ───────────────────────────────────────────────────────
section("➕ Enroll New Student")
with st.form("add_student"):
    c1, c2, c3 = st.columns(3)
    with c1:
        s_username = st.text_input("Username")
        s_roll = st.text_input("Roll No")
        s_dept = int(faculty_info["dept_id"])
        st.caption(f"Department ID: {s_dept}")
    with c2:
        s_password = st.text_input("Password", type="password")
        s_name = st.text_input("Student Full Name")
        s_sem = reference_select(db, "Semester", "semesters", "semester_id", "semester_no", key="s_sem")
    with c3:
        s_section = reference_select(db, "Section", "sections", "section_id", "section_name", key="s_section")

    submitted = st.form_submit_button("✔  Enroll Student", type="primary")
    if submitted:
        if not all([s_username, s_password, s_roll, s_name, s_sem, s_section]):
            st.error("Please fill in all required fields.")
        else:
            res = enroll.enroll_student(
                username=s_username, password=s_password,
                roll_no=s_roll, name=s_name,
                dept_id=int(s_dept), semester_id=int(s_sem),
                section_id=int(s_section)
            )
            if res["status"]:
                st.success(f"✓ {res['message']} — User ID: {res.get('user_id', '—')}")
            else:
                st.error(res["message"])

# ─── Voice Embeddings ─────────────────────────────────────────────────────
section("🎙 Add Voice Embeddings for Students")

students = db.execute(
    "SELECT s.user_id, s.name, u.username FROM students s "
    "JOIN users u ON s.user_id=u.user_id WHERE s.dept_id=?",
    (faculty_info["dept_id"],), fetch=True
)

if not students:
    st.info("No students found in your department yet. Enroll students first.")
else:
    student_map = {f"{s['name']} ({s['username']})": s["user_id"] for s in students}
    c1, c2 = st.columns([1, 2])
    with c1:
        selected_student = st.selectbox("Select Student", list(student_map.keys()))
    with c2:
        audio_files = st.file_uploader(
            "Upload voice samples (.wav)", type=["wav"],
            accept_multiple_files=True
        )

    st.markdown("""
    <p style="color:#91A2BB;font-size:0.82rem;margin-bottom:1rem;">
    Upload 3–5 voice samples per student for best accuracy. Files must be WAV format, 
    at least 2 seconds long.
    </p>
    """, unsafe_allow_html=True)

    if st.button("🎙  Process & Save Embeddings", type="primary"):
        if not audio_files:
            st.error("Please upload at least one .wav file.")
        elif not selected_student:
            st.error("Please select a student.")
        else:
            student_id = student_map[selected_student]
            ok, err = 0, 0
            error_details = []
            prog = st.progress(0)
            status_text = st.empty()

            for i, af in enumerate(audio_files):
                status_text.markdown(
                    f"<small style='color:#91A2BB'>Processing {escape(af.name)}...</small>",
                    unsafe_allow_html=True
                )
                prog.progress((i + 1) / len(audio_files))
                try:
                    audio_proc, spk_model = load_models()
                    audio_np = audio_proc.process_file(af)
                    embedding = spk_model.generate_embedding(audio_np)
                    res = attendance.add_voice_embedding(student_id, embedding, "enrollment")
                    if res.get("status"):
                        ok += 1
                    else:
                        err += 1
                        error_details.append(f"{escape(af.name)}: {res.get('message', 'Unknown error')}")
                except Exception as e:
                    err += 1
                    error_details.append(f"{escape(af.name)}: {str(e)[:80]}")

            prog.empty()
            status_text.empty()

            if ok:
                st.success(f"✓ {ok} embedding(s) successfully saved for {selected_student}")
                st.balloons()
            if err:
                st.error(f"✗ {err} file(s) failed:")
                for d in error_details:
                    st.caption(f"  • {d}")

logout_button("logout_faculty")
