"""Bounded attendance reads with authorization checked at the data boundary."""
from datetime import date
from backend.errors import ValidationError

def page_limit(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 200:
        raise ValidationError('Choose a page size from 1 to 200.')
    return value

def search_pattern(value):
    text=str(value).strip()
    if len(text)>100:
        raise ValidationError('Search must be at most 100 characters.')
    return '%' + text.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'

def actor_scope(conn, actor_id):
    actor=conn.execute('SELECT role FROM users WHERE user_id=? AND is_active=1',(actor_id,)).fetchone()
    if not actor:
        raise ValidationError('Your account is unavailable. Sign in again.')
    return actor['role']

def attendance_page(db,actor_id,*,own=False,search='',role=None,start=None,end=None,after=None,limit=101):
    page_limit(limit)
    where=[]
    params=[]
    with db.transaction() as conn:
        actor=actor_scope(conn,actor_id)
        if own or actor in ('student','faculty'):
            where.append('a.user_id=?'); params.append(actor_id)
        elif actor=='teacher':
            profile=conn.execute('SELECT dept_id,section_id FROM teachers WHERE user_id=?',(actor_id,)).fetchone()
            if not profile or profile['section_id'] is None:
                return []
            where.extend(["a.role='student'",'s.dept_id=?','s.section_id=?'])
            params.extend([profile['dept_id'],profile['section_id']])
        elif actor!='chairman':
            raise ValidationError('Attendance access is not permitted.')
        if role:
            if role not in ('student','teacher','faculty'):
                raise ValidationError('Choose a supported role.')
            where.append('a.role=?'); params.append(role)
        for value,operator in ((start,'>='),(end,'<=')):
            if value:
                date.fromisoformat(str(value))
                where.append(f'a.date {operator} ?'); params.append(str(value))
        if start and end and str(start)>str(end):
            raise ValidationError('The start date must be before the end date.')
        if search.strip():
            where.append("(LOWER(u.username) LIKE LOWER(?) ESCAPE '!' OR LOWER(COALESCE(s.name,t.name,f.name,'')) LIKE LOWER(?) ESCAPE '!' OR LOWER(COALESCE(s.roll_no,'')) LIKE LOWER(?) ESCAPE '!')")
            params.extend([search_pattern(search)]*3)
        if after:
            where.append('(a.date,a.attendance_id)<(?,?)'); params.extend(after)
        clause=' AND '.join(where) or '1=1'
        return [dict(r) for r in conn.execute(f'''SELECT a.attendance_id AS _record_id,
            u.username,COALESCE(s.name,t.name,f.name,u.username) AS name,s.roll_no,
            a.role,a.date,a.time,a.confidence,a.marked_by
            FROM attendance a JOIN users u ON a.user_id=u.user_id
            LEFT JOIN students s ON s.user_id=a.user_id
            LEFT JOIN teachers t ON t.user_id=a.user_id
            LEFT JOIN faculty f ON f.user_id=a.user_id
            WHERE {clause} ORDER BY a.date DESC,a.attendance_id DESC LIMIT ?''',(*params,limit)).fetchall()]

def attendance_summary(db,user_id):
    return db.execute('SELECT COUNT(*) AS total,MAX(date) AS latest FROM attendance WHERE user_id=?',(user_id,),fetchone=True)
