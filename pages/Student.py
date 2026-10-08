import streamlit as st
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages._ui import inject_css, page_header, section, role_guard, logout_button
from backend.attendance_handler import AttendanceHandler
from backend.config import SPEAKER_VERIFICATION_THRESHOLD
from backend.auth_handler import DatabaseHandler
import pandas as pd

st.set_page_config(
    page_title="Student · VBAS",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed"
)

inject_css()
role_guard("student")

page_header("🎓", "Student Dashboard",
            "Your personal attendance history",
            role="student")

db = DatabaseHandler()
attendance = AttendanceHandler()
user_id = st.session_state.user["user_id"]
username = st.session_state.user["username"]

section("📅 My Attendance Records")

try:
    data = attendance.get_user_attendance(user_id)
    if data:
        df = pd.DataFrame(data)

        # KPIs
        kc1, kc2, kc3 = st.columns(3)
        with kc1:
            st.metric("📋 Total Days Present", len(df))
        with kc2:
            if 'confidence' in df.columns and df['confidence'].notna().any():
                avg_conf = df['confidence'].mean()
                st.metric("🎯 Avg Voice Confidence", f"{avg_conf:.3f}")
            else:
                st.metric("🎯 Avg Voice Confidence", "—")
        with kc3:
            if 'date' in df.columns and len(df) > 0:
                st.metric("📆 Last Marked", str(df['date'].iloc[0]))
            else:
                st.metric("📆 Last Marked", "—")

        st.markdown("<br>", unsafe_allow_html=True)

        # Confidence trend if available
        if 'confidence' in df.columns and df['confidence'].notna().any() and 'date' in df.columns:
            try:
                import plotly.express as px
                df['date'] = pd.to_datetime(df['date'])
                fig = px.line(df.sort_values('date'), x='date', y='confidence',
                              markers=True, template="plotly_dark", height=220,
                              title=None)
                fig.update_traces(line_color='#75F1CF', marker_color='#B3A1FF')
                fig.update_layout(
                    paper_bgcolor='#101827', plot_bgcolor='#101827',
                    font=dict(family="IBM Plex Mono", color="#91A2BB"),
                    xaxis=dict(gridcolor='#243148', title="Date"),
                    yaxis=dict(gridcolor='#243148', title="Similarity"),
                    margin=dict(t=10, b=10)
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                pass

        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥  Download My Attendance", csv, "my_attendance.csv", "text/csv")

        # Simple attendance stats
        st.markdown("<br>", unsafe_allow_html=True)
        section("📈 Voice Biometric Stats")
        if 'confidence' in df.columns and df['confidence'].notna().any():
            stats_col1, stats_col2, stats_col3 = st.columns(3)
            with stats_col1:
                st.metric("↑ Max Similarity", f"{df['confidence'].max():.4f}")
            with stats_col2:
                st.metric("↓ Min Similarity", f"{df['confidence'].min():.4f}")
            with stats_col3:
                above_thresh = (df['confidence'] >= SPEAKER_VERIFICATION_THRESHOLD).sum()
                st.metric("✓ Above Threshold", above_thresh)
        else:
            st.info("No similarity data available.")
    else:
        st.markdown("""
        <div style="text-align:center;padding:3rem 1rem;background:#101827;
             border:1px solid #243148;border-radius:12px;">
            <div style="font-size:2rem;margin-bottom:12px;">📭</div>
            <h3 style="font-family:'IBM Plex Mono',monospace;color:#91A2BB;font-size:0.9rem;">
                NO RECORDS YET
            </h3>
            <p style="color:#2A3550;font-size:0.82rem;">
                Mark your attendance from the main page using voice identification.
            </p>
        </div>
        """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Error fetching attendance: {e}")

logout_button("logout_student")
