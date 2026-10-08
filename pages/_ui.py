"""Shared campus product design and role access guards."""
from pathlib import Path
from html import escape
from functools import lru_cache
import streamlit as st
from backend.config import ROOT, setting

@lru_cache(maxsize=4)
def _theme_css(path,modified_ns):
    return Path(path).read_text(encoding='utf-8')

def inject_css():
    path=ROOT/'static/theme.css'
    st.markdown('<style>'+_theme_css(str(path),path.stat().st_mtime_ns)+'</style>',unsafe_allow_html=True)

def brandbar(label='University attendance platform'):
    university=escape(str(setting('UNIVERSITY_NAME','Campus Intelligence')))
    st.markdown(f'<div class="brandbar"><div class="brand"><div class="brandmark">V</div><div class="brandname">VBAS<span>{university}</span></div></div><div class="status-pill"><i></i>{escape(label)}</div></div>',unsafe_allow_html=True)

def page_header(icon: str, title: str, subtitle: str='', role: str=''):
    brandbar('Campus workspace')
    st.markdown(f'<div class="workspace-header"><div><div class="eyebrow">Your campus. Connected.</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div><span class="role-badge">{escape(role)}</span></div>',unsafe_allow_html=True)
    if st.button('← Attendance hub',key='return_hub'):
        st.switch_page('app.py')

def section(label: str):
    st.markdown(f'<div class="sec-header">{escape(label)}</div>',unsafe_allow_html=True)

def footer():
    st.markdown('<div class="product-footer"><span>VBAS · Built for the rhythm of campus life.</span><span>Voice identity · Academic workspaces · Attendance intelligence</span></div>',unsafe_allow_html=True)

def role_guard(required_role: str):
    """Check current database account status and required role."""
    from backend.database import DatabaseHandler
    from backend.session import refresh_session
    refresh_session(DatabaseHandler())
    if "user" not in st.session_state or st.session_state.user is None:
        inject_css()
        st.markdown("""
        <div style="text-align:center;padding:4rem 2rem;">
            <div style="font-family:'Space Mono',monospace;font-size:2rem;margin-bottom:12px;">🔒</div>
            <h2 style="font-family:'Space Mono',monospace;color:#FF4455;">ACCESS DENIED</h2>
            <p style="color:#6B7A99;">Please log in from the main page to continue.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("← Return to Login"):
            st.switch_page("app.py")
        st.stop()

    if st.session_state.user["role"] != required_role:
        inject_css()
        st.markdown("""
        <div style="text-align:center;padding:4rem 2rem;">
            <div style="font-family:'Space Mono',monospace;font-size:2rem;margin-bottom:12px;">⛔</div>
            <h2 style="font-family:'Space Mono',monospace;color:#FF4455;">UNAUTHORIZED</h2>
            <p style="color:#6B7A99;">Your role does not have access to this dashboard.</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()


def logout_button(key="logout"):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<hr>', unsafe_allow_html=True)
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("⏻  Logout", key=key, use_container_width=True):
            st.session_state.user = None
            st.session_state.pop("kiosk_unlocked", None)
            st.switch_page("app.py")
    footer()

