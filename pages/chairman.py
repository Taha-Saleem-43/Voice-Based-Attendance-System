"""Chairman workspace: one focused section per interaction."""
import streamlit as st
from ui.layout import inject_css,role_guard,logout_button,error_boundary,flash
from ui.workspace import navigation,records_table,enrollment_form,voice_workspace
from backend.attendance_handler import AttendanceHandler
from backend.directory import campus_accounts
from backend.reference_cache import reference_rows,REFERENCE_COLUMNS
from ui.references import reference_form
from backend.management import set_account_state,delete_reference

st.set_page_config(page_title='Chairman · VBAS',page_icon='🏛',layout='wide',initial_sidebar_state='collapsed')
inject_css()
db=role_guard('chairman')
view=navigation('chairman','Chairman Dashboard','Manage academic groups, campus accounts, attendance and voice enrollment.',
                ['Overview','Attendance','Directory','Create account','Academic setup','Voice profiles'])
actor=st.session_state.user['user_id']

with error_boundary('chairman-workspace'):
    if view=='Overview':
        st.subheader('Campus overview')
        counts=db.execute("SELECT role,COUNT(*) AS total FROM users WHERE is_active=1 AND role!='chairman' GROUP BY role",fetch=True)
        totals={r['role']:r['total'] for r in counts}
        for column,role in zip(st.columns(3),('student','teacher','faculty')):
            column.metric(f'Active {role}s',totals.get(role,0))
        st.markdown('### Set up your campus')
        st.write('1. Add departments, sections and semesters in Academic setup.\n2. Create teacher and faculty accounts.\n3. Faculty enroll students and consented voice samples.\n4. Supervise voice check-in from the attendance hub.')
        st.info('Use the workspace navigation above to open one task at a time. Accounts are suspended or reactivated from Directory; attendance history is retained.')
    elif view=='Attendance':
        st.subheader('Campus attendance')
        rows=AttendanceHandler(db).get_all_attendance()
        role=st.selectbox('Role',['All roles','student','teacher','faculty'])
        if role!='All roles': rows=[r for r in rows if r['role']==role]
        records_table(rows,'campus_attendance')
    elif view=='Directory':
        st.subheader('Campus directory')
        people=campus_accounts(db)
        a,b=st.columns(2)
        role=a.selectbox('Role',['All roles','student','teacher','faculty'])
        status=b.selectbox('Account status',['All statuses','Active','Suspended'])
        filtered=[{**p,'status':'Active' if p['is_active'] else 'Suspended'} for p in people if (role=='All roles' or p['role']==role) and (status=='All statuses' or bool(p['is_active'])==(status=='Active'))]
        records_table([{k:v for k,v in p.items() if k!='is_active'} for p in filtered],'campus_directory','No accounts match these filters. Create an account or change the filters.')
        st.subheader('Account access')
        st.caption('Suspension blocks sign-in and voice check-in. It retains academic records and can be reversed.')
        choices={p['user_id']:p for p in filtered}
        uid=st.selectbox('Account to manage',list(choices),index=None,format_func=lambda value:f"{choices[value]['name']} · {choices[value]['username']}",placeholder='Choose an account')
        if uid is not None:
            person=choices[uid]
            action='Suspend' if person['is_active'] else 'Reactivate'
            with st.form(f'account_access_{uid}_{person["is_active"]}',enter_to_submit=False):
                st.write(f"{action} access for {person['username']} ({person['role']})?")
                confirmed=st.checkbox(f'I confirm that I want to {action.lower()} this account.')
                if st.form_submit_button(f'{action} account'):
                    if not confirmed: st.warning('Confirm the account change using the checkbox.')
                    else:
                        set_account_state(db,actor,uid,person['is_active'],not person['is_active'])
                        flash(f"Account {person['username']} {'suspended' if person['is_active'] else 'reactivated'}.")
    elif view=='Create account':
        role=st.radio('Account type',['teacher','faculty'],format_func=str.title,horizontal=True)
        enrollment_form(db,role)
    elif view=='Academic setup':
        st.subheader('Academic groups')
        table=st.radio('Group type',['departments','sections','semesters'],format_func=str.title,horizontal=True,key='academic_type')
        label={'departments':'Department','sections':'Section','semesters':'Semester'}[table]
        rows=reference_rows(db,table)
        st.caption('Existing records are shown below. Changes apply to enrollment forms immediately.')
        records_table(rows,f'academic_{table}',f'No {table} yet. Add the first one below.')
        st.markdown(f'### Add {label.lower()}')
        reference_form(db,table,label,{'departments':'Add Dept','sections':'Add Section','semesters':'Add Semester'}[table])
        if rows:
            with st.expander(f'Remove an unused {label.lower()}'):
                idcol,namecol=REFERENCE_COLUMNS[table]
                choices={r[idcol]:str(r[namecol]) for r in rows}
                selected=st.selectbox('Record to remove',list(choices),index=None,format_func=choices.get,key=f'delete_{table}_choice',placeholder='Choose a record')
                if selected is not None:
                    with st.form(f'delete_{table}_{selected}',enter_to_submit=False):
                        st.warning(f'Remove {label.lower()} “{choices[selected]}”? This cannot be undone. Records that are in use cannot be removed.')
                        confirmed=st.checkbox('I understand and want to remove this record.')
                        if st.form_submit_button('Remove selected record'):
                            if not confirmed: st.warning('Confirm removal using the checkbox.')
                            else:
                                delete_reference(db,actor,table,selected)
                                flash(f'{label} removed.')
    elif view=='Voice profiles':
        people=[p for p in campus_accounts(db) if p['is_active'] and p['role'] in ('teacher','faculty')]
        voice_workspace(db,people,'chairman_voice')

logout_button('logout_chairman')
