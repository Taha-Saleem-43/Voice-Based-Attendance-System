"""Shared workspace components: navigation, records, forms and voice profiles."""
import streamlit as st
import pandas as pd
from datetime import date,timedelta
from backend.config import local_now
from backend.attendance_handler import AttendanceHandler
from backend.enrollment_handler import EnrollmentHandler
from ui.references import reference_select
from backend.errors import ValidationError,report_error
from backend.management import delete_voice_sample
from ui.layout import page_header,show_notice,flash,error_boundary

def csv_safe(value):
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):
        return "'"+value
    return value

def navigation(role,title,subtitle,views):
    page_header('',title,subtitle,role)
    show_notice()
    return st.radio('Workspace section',views,horizontal=True,key=f'{role}_view')

def records_table(rows,key,empty='No records yet. Records appear here after your first successful check-in.',filters=True):
    if not rows:
        st.info(empty)
        return
    df=pd.DataFrame(rows)
    with st.container(border=True):
        search=st.text_input('Search records',key=f'{key}_search',placeholder='Search names, usernames or record details') if filters else ''
        if search.strip():
            mask=df.astype(str).apply(lambda column:column.str.contains(search.strip(),case=False,regex=False)).any(axis=1)
            df=df[mask]
        if filters and 'date' in df.columns:
            dates=sorted(df['date'].astype(str).unique(),reverse=True)
            date=st.selectbox('Attendance date',['All dates',*dates],key=f'{key}_date')
            if date!='All dates':
                df=df[df['date'].astype(str)==date]
        st.caption(f'{len(df)} matching record(s)')
        if df.empty:
            st.info('No records match these filters. Try a different search.')
        else:
            # Internal identifiers and voice vectors are not part of display/export.
            df=df.drop(columns=[c for c in df if c.endswith('_id') or c.startswith('_') or c in ('password_hash','embedding_vector')])
            df=df.rename(columns={c:c.replace('_',' ').title() for c in df})
            # Prevent spreadsheet formula injection in CSV exports.
            export=df.map(csv_safe)
            # Streamlit's own table download must use the safe values too.
            st.dataframe(export,use_container_width=True,hide_index=True)
            st.download_button('Download filtered CSV',export.to_csv(index=False).encode('utf-8'),f'{key}.csv','text/csv',key=f'{key}_download')

def paginated_records(loader,key,*,attendance=False,signature=(),transform=None):
    search=st.text_input('Search all records',max_chars=100,key=f'{key}_server_search',placeholder='Search usernames, names or roll numbers')
    start=end=None
    if attendance:
        a,b=st.columns(2)
        start=a.date_input('From date',local_now().date()-timedelta(days=30),key=f'{key}_from')
        end=b.date_input('To date',local_now().date(),key=f'{key}_to')
        if start>end:
            st.warning('Choose a start date before the end date.'); return []
    token=(search,str(start),str(end),*signature)
    state=st.session_state.get(f'{key}_paging')
    if not state or state['signature']!=token:
        state={'signature':token,'cursors':[None]}
        st.session_state[f'{key}_paging']=state
    rows=loader(search=search,start=start,end=end,after=state['cursors'][-1],limit=101)
    visible=rows[:100]
    records_table(transform(visible) if transform else visible,key,'No records match this view. Try different filters or dates.',filters=False)
    st.caption(f'Page {len(state["cursors"])} · Up to 100 records per page. CSV exports this page only.')
    a,b=st.columns(2)
    if a.button('Previous page',key=f'{key}_previous',disabled=len(state['cursors'])==1):
        state['cursors'].pop(); st.rerun()
    if b.button('Next page',key=f'{key}_next',disabled=len(rows)<=100):
        last=visible[-1]
        state['cursors'].append((last['date'],last['_record_id']) if attendance else last['user_id'])
        st.rerun()
    return visible

def attendance_records(db,user_id,key,*,own=False,role=None):
    from backend.records import attendance_page
    return paginated_records(lambda **args:attendance_page(db,user_id,own=own,role=role,**args),key,attendance=True,signature=(role,own))

def personal_attendance(db,user_id,key):
    from backend.records import attendance_summary
    summary=attendance_summary(db,user_id)
    a,b=st.columns(2)
    a.metric('Recorded attendance days',summary['total'])
    b.metric('Latest check-in',summary['latest'] or 'Not yet')
    attendance_records(db,user_id,key,own=True)

def voice_people(db,actor_id,key,department=None):
    from backend.directory import campus_accounts,department_students
    query=st.text_input('Find an account',max_chars=100,key=f'{key}_find',placeholder='Enter at least 2 characters of a username, name or roll number')
    if len(query.strip())<2:
        st.info('Search for an account to manage its voice profile.'); return []
    if department is not None:
        rows=department_students(db,department,actor_id=actor_id,search=query,active=True,limit=101)
    else:
        rows=campus_accounts(db,actor_id=actor_id,search=query,active=True,roles=('teacher','faculty'),limit=101)
    if len(rows)>100:
        st.info('More than 100 accounts match. Refine the search to find the intended account.')
    return rows[:100]

def enrollment_form(db,role,department=None):
    title=f'Create {role.title()}' if role!='student' else 'Enroll Student'
    st.subheader(title)
    st.caption('All fields are required unless marked optional. Nothing is saved until you submit.')
    revision=st.session_state.get(f'{role}_form_revision',0)
    prefix=f'{role}_enrollment_{revision}'
    with st.form(prefix,enter_to_submit=True):
        st.markdown('**Account details**')
        username=st.text_input('Username',max_chars=100,key=f'{prefix}_username',help='Unique campus username, up to 100 characters.')
        name=st.text_input('Full name',max_chars=150,key=f'{prefix}_name')
        password=st.text_input('Password',type='password',key=f'{prefix}_password',help='Use 10–72 UTF-8 bytes. Choose a unique password and share it privately with the account owner.')
        confirm=st.text_input('Confirm password',type='password',key=f'{prefix}_confirm')
        st.markdown('**Academic assignment**')
        if department is None:
            dept=reference_select(db,'Department','departments','dept_id','dept_name',key=f'{prefix}_dept')
        else:
            dept=department['dept_id']
            st.caption(f"Department: {department['dept_name']}")
        semester=section=None
        roll=''
        if role=='student':
            roll=st.text_input('Roll number',max_chars=100,key=f'{prefix}_roll')
            semester=reference_select(db,'Semester','semesters','semester_id','semester_no',key=f'{prefix}_semester')
        if role in ('student','teacher'):
            section=reference_select(db,'Section','sections','section_id','section_name',key=f'{prefix}_section')
        ready=dept is not None and (role not in ('student','teacher') or section is not None) and (role!='student' or semester is not None)
        if not ready:
            st.info('Academic groups must be added by the chairman before creating this account.')
        st.caption('Press Enter or use the button below to submit. If validation fails, your entries remain available to correct.')
        submitted=st.form_submit_button(title,type='primary',disabled=not ready,use_container_width=True)
    if submitted:
        errors=[]
        if not username.strip(): errors.append('Enter a username.')
        if not name.strip(): errors.append('Enter the full name.')
        if not 10<=len(password.encode('utf-8'))<=72: errors.append('Password must contain 10–72 UTF-8 bytes.')
        if password!=confirm: errors.append('The passwords do not match.')
        if role=='student' and not roll.strip(): errors.append('Enter the roll number.')
        if errors:
            for message in errors: st.warning(message)
            return
        handler=EnrollmentHandler(db,actor_user_id=st.session_state.user['user_id'])
        with st.spinner('Saving account…'):
            if role=='student':
                result=handler.enroll_student(username,password,roll,name,dept,semester,section)
            elif role=='teacher':
                result=handler.enroll_teacher(username,password,name,dept,section_id=section)
            else:
                result=handler.enroll_faculty(username,password,name,dept)
        if result['status']:
            st.session_state[f'{role}_form_revision']=revision+1
            flash(f'{role.title()} account for {username.strip()} was created. You can find it in the directory.')
        else:
            st.warning(result['message'])

def voice_workspace(db,people,key):
    st.subheader('Voice profiles')
    st.caption('Choose an account to view, enroll or remove voice samples. Attendance history is retained when a sample is removed.')
    if not people:
        st.info('No eligible accounts yet. Create an account before enrolling voice samples.')
        return
    choices={p['user_id']:f"{p['name']} · {p['username']}" for p in people}
    uid=st.selectbox('Account',list(choices),format_func=choices.get,key=f'{key}_account',index=None,placeholder='Choose an account')
    if uid is None: return
    samples=db.execute('SELECT embedding_id,created_at,sample_type FROM voice_embeddings WHERE user_id=? ORDER BY embedding_id',(uid,),fetch=True)
    st.metric('Enrolled voice samples',len(samples))
    if samples:
        st.dataframe([{'Sample':i+1,'Enrolled':r['created_at'],'Type':r['sample_type']} for i,r in enumerate(samples)],hide_index=True,use_container_width=True)
    revision=st.session_state.get(f'{key}_voice_revision',0)
    with st.form(f'{key}_voice_upload_{uid}_{revision}',enter_to_submit=False):
        st.markdown('**Add samples**')
        st.caption('Upload independent WAV recordings, 2–30 seconds each, up to 10 MB per file. Up to 5 files per submission.')
        files=st.file_uploader('Voice recordings',type=['wav'],accept_multiple_files=True)
        consent=st.checkbox('The account owner has consented to voice enrollment.')
        submitted=st.form_submit_button('Save voice samples',type='primary',use_container_width=True)
    if submitted:
        if not consent: st.warning('Confirm consent before enrolling voice samples.')
        elif not files: st.warning('Select at least one WAV recording.')
        elif len(files)>5 or any(f.size>10*1024*1024 for f in files): st.warning('Select up to 5 files, each no larger than 10 MB.')
        else:
            from backend.resources import load_models
            with st.spinner('Processing voice samples. First use may take longer…'):
                processor,model=load_models()
                saved=0
                messages=[]
                for number,file in enumerate(files,1):
                    try:
                        vector=model.generate_embedding(processor.process_file(file))
                        result=AttendanceHandler(db).add_voice_embedding(uid,vector,actor_id=st.session_state.user['user_id'])
                        if result['status']: saved+=1
                        else: messages.append(f"Sample {number}: {result['message']}")
                    except ValidationError as exc:
                        messages.append(f'Sample {number}: {exc}')
                    except Exception as exc:
                        messages.append(f'Sample {number}: {report_error("voice-processing",exc)}')
            if saved:
                st.session_state[f'{key}_voice_revision']=revision+1
                st.session_state[f'{key}_voice_result']=(saved,messages)
                st.rerun()
            for message in messages: st.warning(message)
    result=st.session_state.pop(f'{key}_voice_result',None)
    if result:
        st.success(f'{result[0]} voice sample(s) saved.')
        for message in result[1]: st.warning(message)
    if samples:
        with st.expander('Remove a voice sample'):
            labels={r['embedding_id']:f"Sample {i+1} · {r['created_at']}" for i,r in enumerate(samples)}
            selected=st.selectbox('Sample to remove',list(labels),format_func=labels.get,index=None,key=f'{key}_remove_sample')
            if selected is not None:
                with st.form(f'{key}_delete_sample_{selected}',enter_to_submit=False):
                    st.warning('This permanently removes the selected biometric sample. It does not remove attendance history. Removing the final sample prevents voice recognition until enrollment is repeated.')
                    confirmed=st.checkbox('I understand and want to remove this sample.')
                    if st.form_submit_button('Remove selected sample'):
                        if not confirmed: st.warning('Confirm removal using the checkbox.')
                        else:
                            delete_voice_sample(db,st.session_state.user['user_id'],selected)
                            flash('Voice sample removed.')
