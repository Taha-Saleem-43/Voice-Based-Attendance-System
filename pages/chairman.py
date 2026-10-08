import streamlit as st
import warnings
import os
import sys

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Allow imports from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages._ui import inject_css, page_header, section, role_guard, logout_button
from backend.auth_handler import DatabaseHandler, AuthHandler
from backend.attendance_handler import AttendanceHandler
from backend.enrollment_handler import EnrollmentHandler
from backend.resources import load_models
from html import escape
from backend.reference_ui import reference_select

st.set_page_config(
    page_title="Chairman · VBAS",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="collapsed"
)

inject_css()
role_guard("chairman")

page_header("🏛", "Chairman Dashboard",
            "Full system oversight — attendance, users, enrollment & embeddings",
            role="chairman")

db = DatabaseHandler()
auth = AuthHandler(db)
attendance = AttendanceHandler(db)
enroll = EnrollmentHandler(db, actor_user_id=st.session_state.user["user_id"])


try:
    audio_proc, spk_model = load_models()
    model_load_error = None
except Exception:
    import logging
    logging.exception('Speaker model startup failed')
    audio_proc, spk_model = None, None
    model_load_error = 'Check the deployment logs and model download connection.'


# ─── Tabs ────────────────────────────────────────────────────────────────────
tab_view, tab_manage = st.tabs(["📊  Analytics & Records", "✏️  Manage System"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — VIEW & ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
with tab_view:
    # ── Attendance Overview ──────────────────────────────────────────────────
    section("📊 Attendance Analytics")
    try:
        data = attendance.get_all_attendance()
        if data:
            import pandas as pd
            df = pd.DataFrame(data)

            # KPI row
            total = len(df)
            roles = df['role'].value_counts()
            kpi_cols = st.columns(4)
            kpi_vals = [
                ("Total Records", total, "📋"),
                ("Students", roles.get("student", 0), "🎓"),
                ("Teachers", roles.get("teacher", 0), "👨‍🏫"),
                ("Faculty", roles.get("faculty", 0), "🧑‍🔬"),
            ]
            for col, (label, val, icon) in zip(kpi_cols, kpi_vals):
                with col:
                    st.metric(f"{icon} {label}", val)

            st.markdown("<br>", unsafe_allow_html=True)
            chart_tab1, chart_tab2, chart_tab3 = st.tabs(["Role Distribution", "Trend Over Time", "Raw Data"])

            with chart_tab1:
                role_stats = df['role'].value_counts().reset_index()
                role_stats.columns = ['role', 'count']
                try:
                    import plotly.express as px
                    fig = px.bar(role_stats, x='role', y='count',
                                 color='role', text_auto=True,
                                 color_discrete_sequence=["#75F1CF", "#B3A1FF", "#00FF88", "#FFB300"],
                                 template="plotly_dark", height=320)
                    fig.update_layout(
                        paper_bgcolor='#101827', plot_bgcolor='#101827',
                        showlegend=False, xaxis_title="Role", yaxis_title="Count",
                        font=dict(family="IBM Plex Mono", color="#91A2BB"),
                        xaxis=dict(gridcolor='#243148'), yaxis=dict(gridcolor='#243148')
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.bar_chart(role_stats.set_index('role')['count'])

                st.markdown("<br>", unsafe_allow_html=True)
                all_roles = ["All Roles", "student", "teacher", "faculty"]
                selected_role = st.selectbox("Filter by Role", all_roles)
                filtered_df = df if selected_role == "All Roles" else df[df['role'] == selected_role]
                if not filtered_df.empty:
                    user_counts = filtered_df['username'].value_counts().head(10)
                    try:
                        import plotly.express as px
                        fig2 = px.bar(x=user_counts.index, y=user_counts.values,
                                      text_auto=True, template="plotly_dark", height=280,
                                      labels={'x': 'Username', 'y': 'Count'},
                                      color_discrete_sequence=["#75F1CF"])
                        fig2.update_layout(
                            paper_bgcolor='#101827', plot_bgcolor='#101827',
                            font=dict(family="IBM Plex Mono", color="#91A2BB"),
                            xaxis=dict(gridcolor='#243148'), yaxis=dict(gridcolor='#243148')
                        )
                        st.plotly_chart(fig2, use_container_width=True)
                    except ImportError:
                        st.bar_chart(user_counts)

            with chart_tab2:
                df['date'] = pd.to_datetime(df['date'])
                att_by_date = df.groupby('date').size().reset_index(name='count')
                try:
                    import plotly.express as px
                    fig3 = px.line(att_by_date, x='date', y='count',
                                   markers=True, template="plotly_dark", height=300)
                    fig3.update_traces(line_color='#75F1CF', marker_color='#B3A1FF')
                    fig3.update_layout(
                        paper_bgcolor='#101827', plot_bgcolor='#101827',
                        font=dict(family="IBM Plex Mono", color="#91A2BB"),
                        xaxis=dict(gridcolor='#243148'), yaxis=dict(gridcolor='#243148')
                    )
                    st.plotly_chart(fig3, use_container_width=True)
                except ImportError:
                    st.line_chart(att_by_date.set_index('date'))

            with chart_tab3:
                st.dataframe(df, use_container_width=True, hide_index=True)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥  Export CSV", csv, "attendance_all.csv", "text/csv")
        else:
            st.info("No attendance records yet.")
    except Exception as e:
        st.error(f"Error fetching attendance: {e}")

    # ── Faculty Info ─────────────────────────────────────────────────────────
    section("🧑‍🔬 Faculty Members")
    try:
        departments = db.execute("SELECT dept_id, dept_name FROM departments ORDER BY dept_name", fetch=True)
        dept_options = ["All Departments"] + [d["dept_name"] for d in departments]
        dept_map = {"All Departments": None}
        for d in departments:
            dept_map[d["dept_name"]] = d["dept_id"]
        sel_dept = st.selectbox("Filter by Department", dept_options, key="faculty_dept_filter")
        sel_dept_id = dept_map[sel_dept]
        if sel_dept_id is None:
            query = """SELECT f.user_id, u.username, f.name, f.designation, d.dept_name
                       FROM faculty f JOIN users u ON f.user_id=u.user_id
                       LEFT JOIN departments d ON f.dept_id=d.dept_id ORDER BY f.name"""
            params = ()
        else:
            query = """SELECT f.user_id, u.username, f.name, f.designation, d.dept_name
                       FROM faculty f JOIN users u ON f.user_id=u.user_id
                       LEFT JOIN departments d ON f.dept_id=d.dept_id
                       WHERE f.dept_id=? ORDER BY f.name"""
            params = (sel_dept_id,)
        faculty_list = db.execute(query, params, fetch=True)
        if faculty_list:
            import pandas as pd
            st.dataframe([dict(r) for r in faculty_list], use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(faculty_list)} faculty members")
        else:
            st.info("No faculty found.")
    except Exception as e:
        st.error(f"Error: {e}")

    # ── Teacher Info ─────────────────────────────────────────────────────────
    section("👨‍🏫 Teachers")
    try:
        departments = db.execute("SELECT dept_id, dept_name FROM departments ORDER BY dept_name", fetch=True)
        dept_options2 = ["All Departments"] + [d["dept_name"] for d in departments]
        dept_map2 = {"All Departments": None}
        for d in departments:
            dept_map2[d["dept_name"]] = d["dept_id"]
        sel_dept2 = st.selectbox("Filter by Department", dept_options2, key="teacher_dept_filter")
        sel_dept_id2 = dept_map2[sel_dept2]
        if sel_dept_id2 is None:
            query = """SELECT t.user_id, u.username, t.name, d.dept_name, s.section_name
                       FROM teachers t JOIN users u ON t.user_id=u.user_id
                       LEFT JOIN departments d ON t.dept_id=d.dept_id
                       LEFT JOIN sections s ON t.section_id=s.section_id ORDER BY t.name"""
            params = ()
        else:
            query = """SELECT t.user_id, u.username, t.name, d.dept_name, s.section_name
                       FROM teachers t JOIN users u ON t.user_id=u.user_id
                       LEFT JOIN departments d ON t.dept_id=d.dept_id
                       LEFT JOIN sections s ON t.section_id=s.section_id
                       WHERE t.dept_id=? ORDER BY t.name"""
            params = (sel_dept_id2,)
        teacher_list = db.execute(query, params, fetch=True)
        if teacher_list:
            st.dataframe([dict(r) for r in teacher_list], use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(teacher_list)} teachers")
        else:
            st.info("No teachers found.")
    except Exception as e:
        st.error(f"Error: {e}")

    # ── Student Info ─────────────────────────────────────────────────────────
    section("🎓 Students")
    try:
        departments = db.execute("SELECT dept_id, dept_name FROM departments ORDER BY dept_name", fetch=True)
        sections_list = db.execute("SELECT section_id, section_name FROM sections ORDER BY section_name", fetch=True)
        dept_options3 = ["All Departments"] + [d["dept_name"] for d in departments]
        section_options3 = ["All Sections"] + [s["section_name"] for s in sections_list]
        dept_map3 = {"All Departments": None}
        for d in departments:
            dept_map3[d["dept_name"]] = d["dept_id"]
        section_map3 = {"All Sections": None}
        for s in sections_list:
            section_map3[s["section_name"]] = s["section_id"]
        c1, c2 = st.columns(2)
        with c1:
            sel_dept3 = st.selectbox("Filter by Department", dept_options3, key="student_dept_filter")
        with c2:
            sel_sec3 = st.selectbox("Filter by Section", section_options3, key="student_section_filter")
        sel_dept_id3 = dept_map3[sel_dept3]
        sel_sec_id3 = section_map3[sel_sec3]
        query = """SELECT s.user_id, u.username, s.name, s.roll_no, d.dept_name, sec.section_name
                   FROM students s JOIN users u ON s.user_id=u.user_id
                   LEFT JOIN departments d ON s.dept_id=d.dept_id
                   LEFT JOIN sections sec ON s.section_id=sec.section_id WHERE 1=1"""
        params = []
        if sel_dept_id3 is not None:
            query += " AND s.dept_id=?"
            params.append(sel_dept_id3)
        if sel_sec_id3 is not None:
            query += " AND s.section_id=?"
            params.append(sel_sec_id3)
        query += " ORDER BY s.name"
        student_list = db.execute(query, tuple(params), fetch=True)
        if student_list:
            st.dataframe([dict(r) for r in student_list], use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(student_list)} students")
        else:
            st.info("No students found.")
    except Exception as e:
        st.error(f"Error: {e}")

    logout_button("logout_view")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — MANAGE SYSTEM
# ════════════════════════════════════════════════════════════════════════════
with tab_manage:

    # ── Reference Data ────────────────────────────────────────────────────────
    section("🏢 Add Reference Data")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<small style='color:#91A2BB;font-family:IBM Plex Mono,monospace;letter-spacing:.08em;'>DEPARTMENT</small>", unsafe_allow_html=True)
        dept_name = st.text_input("Department Name", label_visibility="collapsed", placeholder="e.g. Computer Science")
        if st.button("➕ Add Dept"):
            if dept_name.strip():
                try:
                    db.execute("INSERT INTO departments (dept_name) VALUES (?)", (dept_name,))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.error("Enter a department name")

    with c2:
        st.markdown("<small style='color:#91A2BB;font-family:IBM Plex Mono,monospace;letter-spacing:.08em;'>SECTION</small>", unsafe_allow_html=True)
        section_name = st.text_input("Section Name", label_visibility="collapsed", placeholder="e.g. A, B, C")
        if st.button("➕ Add Section"):
            if section_name.strip():
                try:
                    db.execute("INSERT INTO sections (section_name) VALUES (?)", (section_name,))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.error("Enter a section name")

    with c3:
        st.markdown("<small style='color:#91A2BB;font-family:IBM Plex Mono,monospace;letter-spacing:.08em;'>SEMESTER</small>", unsafe_allow_html=True)
        semester_no = st.number_input("Semester Number", min_value=1, max_value=8, step=1)
        if st.button("➕ Add Semester"):
            if semester_no:
                try:
                    db.execute("INSERT INTO semesters (semester_no) VALUES (?)", (int(semester_no),))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.error("Choose a semester number")



    # ── User Activation ──────────────────────────────────────────────────────
    section("🔒 Activate / Suspend Users")
    try:
        users = db.execute(
            "SELECT user_id, username, is_active, role FROM users WHERE role != 'chairman'",
            fetch=True
        )
        if users:
            for u in users:
                role_cls = f"role-{u['role']}"
                active_color = "#00FF88" if u["is_active"] else "#FF4455"
                active_label = "ACTIVE" if u["is_active"] else "SUSPENDED"
                col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
                with col1:
                    st.markdown(f"<span style='font-weight:500'>{escape(u['username'])}</span>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f'<span class="role-badge {role_cls}">{u["role"]}</span>', unsafe_allow_html=True)
                with col3:
                    st.markdown(f"""<span style='font-family:IBM Plex Mono,monospace;font-size:0.65rem;
                        color:{active_color};letter-spacing:0.1em;'>● {active_label}</span>""",
                        unsafe_allow_html=True)
                with col4:
                    if st.button("Toggle", key=f"toggle_{u['user_id']}"):
                        auth.set_user_active(u["user_id"], not u["is_active"])
                        st.rerun()
                st.markdown("<hr style='margin:6px 0;border-color:#243148'>", unsafe_allow_html=True)
        else:
            st.info("No users found.")
    except Exception as e:
        st.error(f"Error: {e}")

    # ── Add Teacher ───────────────────────────────────────────────────────────
    section("➕ Add Teacher")
    with st.form("add_teacher"):
        c1, c2 = st.columns(2)
        with c1:
            t_username = st.text_input("Username")
            t_name = st.text_input("Full Name")
            t_dept = reference_select(db, "Department", "departments", "dept_id", "dept_name", key="t_dept")
        with c2:
            t_password = st.text_input("Password", type="password")
            t_section = reference_select(db, "Section", "sections", "section_id", "section_name", key="t_section")
        if st.form_submit_button("✔  Create Teacher", type="primary", disabled=t_dept is None or t_section is None):
            res = enroll.enroll_teacher(
                username=t_username, password=t_password,
                name=t_name, dept_id=t_dept, section_id=t_section
            )
            if res["status"]:
                st.success(res["message"])
            else:
                st.error(res["message"])

    # ── Add Faculty ───────────────────────────────────────────────────────────
    section("➕ Add Faculty")
    with st.form("add_faculty"):
        c1, c2 = st.columns(2)
        with c1:
            f_username = st.text_input("Username")
            f_name = st.text_input("Full Name")
        with c2:
            f_password = st.text_input("Password", type="password")
            f_dept = reference_select(db, "Department", "departments", "dept_id", "dept_name", key="f_dept")
        if st.form_submit_button("✔  Create Faculty", type="primary", disabled=f_dept is None):
            res = enroll.enroll_faculty(
                username=f_username, password=f_password,
                name=f_name, dept_id=f_dept
            )
            if res["status"]:
                st.success(res["message"])
            else:
                st.error(res["message"])

    # ── Voice Embeddings ──────────────────────────────────────────────────────
    section("🎙 Add Voice Embeddings (Teacher / Faculty)")
    if spk_model is None:
        st.error(f"Speaker model failed to load: {model_load_error}")
    else:
        role_option = st.selectbox("Select Role", ["teacher", "faculty"])
        table_name = "teachers" if role_option == "teacher" else "faculty"
        user_list = db.execute(
            f"SELECT u.user_id, u.username, t.name FROM users u "
            f"JOIN {table_name} t ON u.user_id=t.user_id WHERE u.role=?",
            (role_option,), fetch=True
        )
        if not user_list:
            st.warning(f"No {role_option}s found.")
        else:
            user_map = {f"{u['name']} ({escape(u['username'])})": u["user_id"] for u in user_list}
            selected_user = st.selectbox("Select User", list(user_map.keys()))
            audio_files = st.file_uploader(
                "Upload voice samples (.wav)", type=["wav"],
                accept_multiple_files=True
            )
            if st.button("🎙  Add Embeddings", type="primary"):
                if not audio_files:
                    st.error("Upload at least one .wav file.")
                else:
                    user_id = user_map[selected_user]
                    ok, err = 0, 0
                    error_details = []
                    prog = st.progress(0)
                    for i, af in enumerate(audio_files):
                        try:
                            prog.progress((i + 1) / len(audio_files))
                            audio_np = audio_proc.process_file(af)
                            embedding = spk_model.generate_embedding(audio_np)
                            result = attendance.add_voice_embedding(user_id, embedding, "enrollment")
                            if result.get("status"):
                                ok += 1
                            else:
                                err += 1
                                error_details.append(f"{escape(af.name)}: {result.get('message', 'Unknown error')}")
                        except Exception as e:
                            err += 1
                            error_details.append(f"{escape(af.name)}: {str(e)[:80]}")
                    prog.empty()
                    if ok:
                        st.success(f"✓ {ok} embedding(s) added for {selected_user}")
                        st.balloons()
                    if err:
                        st.error(f"✗ {err} failed:")
                        for d in error_details:
                            st.caption(f"  • {d}")

    logout_button("logout_manage")
