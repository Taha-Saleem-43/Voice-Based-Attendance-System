"""VBAS campus attendance hub. Frozen pretrained voice recognition."""
import hmac
import logging
import time
from html import escape
import streamlit as st
from backend.auth_handler import DatabaseHandler,AuthHandler
from backend.attendance_handler import AttendanceHandler
from backend.bootstrap import ensure_admin
from backend.resources import load_models
from backend.session import refresh_session
from backend.config import local_now,setting
from backend.checkin import VoiceCheckinService
from ui.layout import inject_css,brandbar,footer
from backend.errors import ValidationError,report_error
from backend.records import attendance_summary

def safe_login(auth,username,password):
    try:
        return auth.login(username,password)
    except Exception as exc:
        return {'status':False,'message':report_error('login',exc)}

st.set_page_config(page_title='VBAS | Campus Intelligence',page_icon='◈',layout='wide',initial_sidebar_state='collapsed')
inject_css()
brandbar()
try:
    db=DatabaseHandler()
    ensure_admin(db)
except ValidationError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:
    st.error(report_error('hub-startup',exc))
    st.stop()
auth=AuthHandler(db)
attendance=AttendanceHandler(db)
if 'user' not in st.session_state:
    st.session_state.user=None
try:
    refresh_session(db)
except Exception as exc:
    st.error(report_error("hub-session",exc))
    st.stop()

st.markdown("""<section class="hero"><div><div class="eyebrow">A smarter way to show up</div><h1>A campus in sync.<br><em>One voice at a time.</em></h1><p>Less time taking attendance. More time making progress. A connected workspace for students, educators, and the people who keep a university moving.</p><div class="tag-row"><span class="tag">Voice check-in</span><span class="tag">Role-based workspaces</span><span class="tag">Academic records</span></div></div><div class="hero-art" aria-label="Animated illustration of a voice waveform"><div class="orbit"></div><div class="orbit"></div><div class="voice-core"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div><div class="art-label">VOICE → IDENTITY → PRESENCE</div><div class="float-note"><b>Your voice. Your presence.</b><small>Designed for supervised campus check-in</small></div></div></section>""",unsafe_allow_html=True)

st.markdown("""<div class="overview-grid"><div class="overview-card"><div class="eyebrow">01 / Check in</div><div class="value">Speak. Match. Done.</div><p>A guided voice check-in at your campus station.</p></div><div class="overview-card"><div class="eyebrow">02 / Stay connected</div><div class="value">Your own workspace.</div><p>The right records and tools for every campus role.</p></div><div class="overview-card"><div class="eyebrow">03 / Keep perspective</div><div class="value">Attendance, in focus.</div><p>Clear history, department views, and exportable reports.</p></div></div>""",unsafe_allow_html=True)

checkin_tab,workspace_tab,guide_tab=st.tabs(['Voice check-in','Campus workspace','Getting started'])
with checkin_tab:
    left,right=st.columns([1.65,1],gap='large')
    with left:
        with st.container(border=True):
            st.markdown('<div class="section-title">Make your presence count.</div><div class="section-sub">A staff member unlocks the station. You provide the voice.</div>',unsafe_allow_html=True)
            user=st.session_state.user
            is_staff=bool(user and user['role'] in ('chairman','faculty','teacher'))
            code=setting('KIOSK_ACCESS_CODE')
            unlocked=bool(is_staff or st.session_state.get('kiosk_unlocked'))
            if not unlocked:
                st.info('Staff: sign in under Campus workspace to begin a supervised check-in.')
                if code:
                    with st.form('unlock_station'):
                        entered=st.text_input('Station access code',type='password')
                        if st.form_submit_button('Unlock station',type='primary'):
                            failures=st.session_state.get('kiosk_failures',0)
                            if time.time()>=st.session_state.get('kiosk_blocked_until',0):
                                failures=0
                            if failures>=5 and time.time()<st.session_state.get('kiosk_blocked_until',0):
                                st.error('Too many attempts. Try again in 15 minutes.')
                            elif hmac.compare_digest(entered.encode(),str(code).encode()):
                                st.session_state.kiosk_unlocked=True
                                st.session_state.kiosk_unlocked_at=time.time()
                                st.session_state.kiosk_failures=0
                                st.rerun()
                            else:
                                st.session_state.kiosk_failures=failures+1
                                st.session_state.kiosk_blocked_until=time.time()+900
                                st.error('Incorrect station code.')
            else:
                st.markdown('<div class="pulse-ring"><span class="pulse-dot"></span> STATION READY</div>',unsafe_allow_html=True)
                st.caption('Record 3–8 seconds of clear speech. Keep your microphone close.')
                claimed_username=st.text_input('Campus username for check-in',max_chars=100,placeholder='Enter the enrolled person’s username',key='voice_claim')
                st.caption('Voice verification checks this account only. Staff must confirm the person and username.')
                audio=st.audio_input('Record your voice',sample_rate=16000,key=f"voice_{st.session_state.get('voice_revision',0)}")
                verify,clear=st.columns([2,1])
                if verify.button('Verify & Mark Attendance',type='primary',use_container_width=True,disabled=audio is None or not claimed_username.strip()):
                    try:
                        if time.monotonic()-st.session_state.get('last_voice_attempt',0)<3:
                            raise ValidationError('Wait a few seconds before another attempt.')
                        st.session_state.last_voice_attempt=time.monotonic()
                        with st.spinner('Matching your voice securely...'):
                            processor,model=load_models()
                            result=VoiceCheckinService(db,processor,model).identify(audio,supervisor_id=user['user_id'] if is_staff else None,kiosk_authorized=bool(st.session_state.get('kiosk_unlocked')),claimed_username=claimed_username)
                        if result['status']:
                            st.success(f"Attendance recorded for {result['username']}.")
                            st.caption(f"{local_now().strftime('%d %b %Y · %I:%M %p')} · Similarity {result['similarity']:.3f}")
                        elif result.get('matched'):
                            st.warning(result['message'])
                        else:
                            st.error(result['message'])
                    except ValidationError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(report_error('voice-checkin',exc))
                if clear.button('New recording',use_container_width=True):
                    st.session_state.voice_revision=st.session_state.get('voice_revision',0)+1
                    st.rerun()
                if not is_staff and st.button('Lock station',key='lock_station'):
                    st.session_state.pop('kiosk_unlocked',None)
                    st.rerun()
    with right:
        st.markdown('<div class="eyebrow">A moment of presence</div><div class="step"><span class="step-index">01</span><div><b>Find your campus station</b><p>Your teacher or faculty member starts the check-in.</p></div></div><div class="step"><span class="step-index">02</span><div><b>Speak naturally</b><p>A few seconds of speech are matched to your enrolled voice profile.</p></div></div><div class="step"><span class="step-index">03</span><div><b>See your confirmation</b><p>Successful check-ins appear in your personal attendance history.</p></div></div><div class="callout">Supervised pilot: voice matching cannot yet detect a replayed or synthetic voice. Staff presence is required.</div>',unsafe_allow_html=True)

with workspace_tab:
    left,right=st.columns([1.1,1],gap='large')
    with left:
        with st.container(border=True):
            if st.session_state.user is None:
                st.markdown('<div class="eyebrow">Welcome back</div><div class="section-title">Your campus starts here.</div><div class="section-sub">Sign in with the account issued by your university.</div>',unsafe_allow_html=True)
                with st.form('login_form'):
                    username=st.text_input('Username',placeholder='Your university username')
                    password=st.text_input('Password',type='password',placeholder='Your password')
                    st.caption('Press Enter or select Login to workspace to sign in.')
                    if st.form_submit_button('Login to workspace',type='primary',use_container_width=True):
                        if not username or not password:
                            st.error('Enter your username and password.')
                        else:
                            result=safe_login(auth,username,password)
                            if result['status']:
                                st.session_state.user=result
                                destinations={'chairman':'pages/chairman.py','teacher':'pages/teacher.py','faculty':'pages/Faculty.py','student':'pages/Student.py'}
                                st.switch_page(destinations[result['role']])
                            else:
                                st.error(result['message'])
            else:
                user=st.session_state.user
                st.markdown(f'<div class="eyebrow">Your campus workspace</div><div class="section-title">Welcome, {escape(user["username"])}.</div><div class="section-sub">A focused space for your day on campus.</div><span class="role-badge">{escape(user["role"])}</span>',unsafe_allow_html=True)
                try:
                    summary=attendance_summary(db,user['user_id'])
                except Exception as exc:
                    st.error(report_error('hub-history',exc))
                    st.stop()
                if user['role']!='chairman':
                    a,b=st.columns(2)
                    a.metric('Recorded days',summary['total'])
                    b.metric('Latest check-in',summary['latest'] or 'Not yet')
                destinations={'chairman':'pages/chairman.py','teacher':'pages/teacher.py','faculty':'pages/Faculty.py','student':'pages/Student.py'}
                st.markdown('')
                if st.button('Open my workspace →',type='primary',key='open_dashboard',use_container_width=True):
                    st.switch_page(destinations[user['role']])
                if st.button('Log out',key='logout_hub'):
                    st.session_state.user=None
                    st.session_state.pop('kiosk_unlocked',None)
                    st.rerun()
    with right:
        st.markdown('<div class="eyebrow">A place for every role</div><div class="step"><span class="step-index">ST</span><div><b>Students</b><p>Follow your attendance history and download your records.</p></div></div><div class="step"><span class="step-index">ED</span><div><b>Teachers & faculty</b><p>Supervise check-ins, view your students, and enroll voice profiles.</p></div></div><div class="step"><span class="step-index">AD</span><div><b>Chairman & administrators</b><p>Manage campus access, academic groups, enrollment, and reports.</p></div></div>',unsafe_allow_html=True)

with guide_tab:
    st.markdown('### From enrollment to everyday attendance')
    a,b,c=st.columns(3)
    with a:
        with st.container(border=True):
            st.markdown('**01 · Set up your campus**')
            st.write('The chairman creates departments, sections, and semesters, then issues faculty and teacher accounts.')
    with b:
        with st.container(border=True):
            st.markdown('**02 · Enroll your voice**')
            st.write('Faculty enroll students and upload independent voice samples. WAV recordings should contain 2–30 seconds of clear speech.')
    with c:
        with st.container(border=True):
            st.markdown('**03 · Make every day count**')
            st.write('An authorized staff member opens the station. Voice identification records attendance once per calendar day.')
    with st.expander('Privacy and attendance support'):
        st.write('The system stores voice embeddings and attendance history. University staff should obtain consent, define retention, and provide a manual alternative before collecting biometric data. Contact your faculty if a voice check-in fails.')
        st.write('This pilot uses pretrained voice matching. Recognition quality must be validated on your campus; it is not a replacement for staff supervision.')
footer()
