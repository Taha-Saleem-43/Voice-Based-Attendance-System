"""Explicit projections for account directories; never select credentials."""
def campus_accounts(db):
    return db.execute('''SELECT u.user_id,u.username,u.role,u.is_active,
        COALESCE(s.name,t.name,f.name,u.username) AS name,
        d.dept_name AS department,sem.semester_no AS semester,sec.section_name AS section,
        s.roll_no AS roll_number
        FROM users u LEFT JOIN students s ON u.user_id=s.user_id
        LEFT JOIN teachers t ON u.user_id=t.user_id
        LEFT JOIN faculty f ON u.user_id=f.user_id
        LEFT JOIN departments d ON d.dept_id=COALESCE(s.dept_id,t.dept_id,f.dept_id)
        LEFT JOIN semesters sem ON s.semester_id=sem.semester_id
        LEFT JOIN sections sec ON sec.section_id=COALESCE(s.section_id,t.section_id)
        WHERE u.role!='chairman' ORDER BY name''',fetch=True)

def faculty_department(db,user_id):
    return db.execute('SELECT f.dept_id,d.dept_name FROM faculty f JOIN departments d ON f.dept_id=d.dept_id WHERE f.user_id=?',(user_id,),fetchone=True)

def department_students(db,dept_id):
    return db.execute('''SELECT u.user_id,u.username,s.name,s.roll_no AS roll_number,
        u.is_active,sem.semester_no AS semester,sec.section_name AS section
        FROM students s JOIN users u ON s.user_id=u.user_id
        JOIN semesters sem ON s.semester_id=sem.semester_id
        JOIN sections sec ON s.section_id=sec.section_id WHERE s.dept_id=? ORDER BY s.name''',(dept_id,),fetch=True)
