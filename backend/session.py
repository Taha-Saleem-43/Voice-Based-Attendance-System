"""Revalidate accounts, expire workspaces and unattended kiosk sessions."""
import time
import streamlit as st

def refresh_session(db):
    now=time.time()
    if st.session_state.get('kiosk_unlocked') and now-st.session_state.get('kiosk_unlocked_at',0)>3600:
        st.session_state.pop('kiosk_unlocked',None)
    user=st.session_state.get('user')
    if user:
        logged_at=user.get('logged_at',now)
        current=db.execute('SELECT user_id,username,role FROM users WHERE user_id=? AND is_active=1',(user['user_id'],),fetchone=True)
        if current and current['role']==user['role'] and now-logged_at<28800:
            st.session_state.user={'status':True,**current,'logged_at':logged_at}
        else:
            st.session_state.user=None
            st.session_state.pop('kiosk_unlocked',None)
