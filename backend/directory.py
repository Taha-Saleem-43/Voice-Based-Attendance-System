"""Explicit projections for account directories; never select credentials."""
from backend.records import page_limit,search_pattern,actor_scope
from backend.errors import ValidationError

def campus_accounts(db,*,actor_id=None,after=0,limit=101,search='',role=None,roles=None,active=None):
    page_limit(limit)
    where=["u.role!='chairman'",'u.user_id>?']
    params=[after]
    if role:
        if role not in ('student','teacher','faculty'): raise ValidationError('Choose a supported role.')
        where.append('u.role=?'); params.append(role)
    if roles:
        if any(value not in ('student','teacher','faculty') for value in roles): raise ValidationError('Choose supported roles.')
        where.append('u.role IN ('+','.join('?' for _ in roles)+')'); params.extend(roles)
    if active is not None:
        where.append('u.is_active=?'); params.append(int(active))
    if search.strip():
        where.append("(LOWER(u.username) LIKE LOWER(?) ESCAPE '!' OR LOWER(COALESCE(s.name,t.name,f.name,u.username)) LIKE LOWER(?) ESCAPE '!' OR LOWER(COALESCE(s.roll_no,'')) LIKE LOWER(?) ESCAPE '!')")
        params.extend([search_pattern(search)]*3)
    with db.transaction() as conn:
        if actor_id is not None and actor_scope(conn,actor_id)!='chairman':
            raise ValidationError('Your account cannot view the campus directory.')
        return [dict(r) for r in conn.execute('''SELECT u.user_id,u.username,u.role,u.is_active,
        COALESCE(s.name,t.name,f.name,u.username) AS name,
        d.dept_name AS department,sem.semester_no AS semester,sec.section_name AS section,
        s.roll_no AS roll_number
        FROM users u LEFT JOIN students s ON u.user_id=s.user_id
        LEFT JOIN teachers t ON u.user_id=t.user_id
        LEFT JOIN faculty f ON u.user_id=f.user_id
        LEFT JOIN departments d ON d.dept_id=COALESCE(s.dept_id,t.dept_id,f.dept_id)
        LEFT JOIN semesters sem ON s.semester_id=sem.semester_id
        LEFT JOIN sections sec ON sec.section_id=COALESCE(s.section_id,t.section_id)
        WHERE '''+' AND '.join(where)+' ORDER BY u.user_id LIMIT ?',(*params,limit)).fetchall()]

def faculty_department(db,user_id):
    return db.execute('SELECT f.dept_id,d.dept_name FROM faculty f JOIN departments d ON f.dept_id=d.dept_id WHERE f.user_id=?',(user_id,),fetchone=True)

def department_students(db,dept_id,*,actor_id=None,after=0,limit=101,search='',active=None):
    page_limit(limit)
    where=['s.dept_id=?','s.user_id>?']; params=[dept_id,after]
    if active is not None:
        where.append('u.is_active=?'); params.append(int(active))
    if search.strip():
        where.append("(LOWER(u.username) LIKE LOWER(?) ESCAPE '!' OR LOWER(s.name) LIKE LOWER(?) ESCAPE '!' OR LOWER(s.roll_no) LIKE LOWER(?) ESCAPE '!')")
        params.extend([search_pattern(search)]*3)
    with db.transaction() as conn:
        if actor_id is not None:
            role=actor_scope(conn,actor_id)
            profile=conn.execute('SELECT dept_id FROM faculty WHERE user_id=?',(actor_id,)).fetchone()
            if role!='faculty' or not profile or profile['dept_id']!=dept_id:
                raise ValidationError('You can view students only in your department.')
        return [dict(r) for r in conn.execute('''SELECT u.user_id,u.username,s.name,s.roll_no AS roll_number,
        u.is_active,sem.semester_no AS semester,sec.section_name AS section
        FROM students s JOIN users u ON s.user_id=u.user_id
        JOIN semesters sem ON s.semester_id=sem.semester_id
        JOIN sections sec ON s.section_id=sec.section_id WHERE '''+' AND '.join(where)+' ORDER BY s.user_id LIMIT ?',(*params,limit)).fetchall()]
