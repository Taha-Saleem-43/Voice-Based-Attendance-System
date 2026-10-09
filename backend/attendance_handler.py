"""Attendance and voice enrollment storage."""
import numpy as np
from backend.database import DatabaseHandler
from backend.config import local_now
from backend.audit import audit_event

class AttendanceHandler:
    def __init__(self, db_handler=None):
        self.db = db_handler or DatabaseHandler()

    def mark_attendance(self, user_id, role=None, dept_id=None, semester_id=None,
                        section_id=None, confidence=None, marked_by='voice',supervisor_id=None):
        if marked_by == 'manual' and supervisor_id is None:
            return {'status':False,'message':'An assigned staff account must confirm manual attendance.'}
        if confidence is not None and (not np.isfinite(confidence) or not -1 <= confidence <= 1):
            return {'status': False, 'message': 'Invalid similarity score.'}
        if marked_by not in ('voice', 'manual'):
            return {'status': False, 'message': 'Invalid attendance method.'}
        now = local_now()
        with self.db.transaction() as conn:
            # PostgreSQL row lock orders suspension and attendance updates.
            lock = ' FOR UPDATE' if self.db.postgres else ''
            if supervisor_id is not None:
                # Lock in identifier order to avoid crossed staff check-in deadlocks.
                locked=conn.execute('SELECT user_id,role,is_active FROM users WHERE user_id IN (?,?) ORDER BY user_id'+lock,(user_id,supervisor_id)).fetchall()
                accounts={r['user_id']:r for r in locked}
                supervisor=accounts.get(supervisor_id)
                if not supervisor or not supervisor['is_active'] or supervisor['role'] not in ('chairman','teacher','faculty'):
                    return {'status':False,'message':'The supervising account is no longer available. Sign in again.'}
                user=accounts.get(user_id)
            else:
                user = conn.execute('SELECT role,is_active FROM users WHERE user_id=?' + lock, (user_id,)).fetchone()
            if not user or not user['is_active'] or user['role'] not in ('student','teacher','faculty'):
                return {'status': False, 'message': 'Account is unavailable for attendance.'}
            role = user['role']
            table = {'student':'students','teacher':'teachers','faculty':'faculty'}[role]
            profile = conn.execute(f'SELECT * FROM {table} WHERE user_id=?', (user_id,)).fetchone()
            if not profile:
                return {'status': False, 'message': 'Profile is incomplete. Contact the administrator.'}
            profile = dict(profile)
            if marked_by == 'manual':
                if supervisor_id == user_id:
                    return {'status':False,'message':'Ask another assigned staff member to confirm your attendance.'}
                if supervisor['role'] != 'chairman':
                    staff_table = 'faculty' if supervisor['role']=='faculty' else 'teachers'
                    staff_profile = conn.execute(f'SELECT * FROM {staff_table} WHERE user_id=?',(supervisor_id,)).fetchone()
                    if role != 'student' or not staff_profile or staff_profile['dept_id'] != profile['dept_id'] or (supervisor['role']=='teacher' and staff_profile['section_id'] != profile['section_id']):
                        return {'status':False,'message':'You can confirm attendance only for students assigned to you.'}
            inserted = conn.execute(
                'INSERT INTO attendance (user_id,role,dept_id,semester_id,section_id,date,time,confidence,marked_by) '
                'VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT (user_id,date) DO NOTHING RETURNING attendance_id',
                (user_id,role,profile['dept_id'],profile.get('semester_id'),profile.get('section_id'),
                 now.date().isoformat(),now.time().isoformat(),confidence,marked_by)).fetchone()
            if not inserted:
                return {'status': False, 'message': 'Attendance already marked today.'}
            if marked_by == 'manual':
                audit_event(conn,supervisor_id,'attendance.manual',user_id)
        return {'status': True, 'message': 'Attendance marked successfully.'}

    def get_active_voice_profiles(self,username=None):
        return self.db.execute(
            "SELECT e.user_id,e.embedding_vector,u.username,u.role FROM voice_embeddings e "
            "JOIN users u ON u.user_id=e.user_id WHERE u.is_active=1 AND u.role IN ('student','teacher','faculty')"+
            (' AND u.username=?' if username is not None else '')+' ORDER BY e.embedding_id LIMIT ?',
            (username,11) if username is not None else (20001,),fetch=True)

    # ==================================================
    # DASHBOARD-SPECIFIC FETCH FUNCTIONS
    # ==================================================

    # -------------------------------
    # Student/Faculty → own attendance only
    # -------------------------------
    def get_user_attendance(self, user_id):
        rows = self.db.execute(
            """
            SELECT date, time, confidence, marked_by
            FROM attendance
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 100
            """,
            (user_id,),
            fetch=True
        )
        return [dict(r) for r in rows]

    # -------------------------------
    # Teacher → students of dept + section
    # -------------------------------
    def get_teacher_info(self, user_id):
        row = self.db.execute(
            """
            SELECT dept_id, section_id
            FROM teachers
            WHERE user_id = ?
            """,
            (user_id,),
            fetchone=True
        )
        return dict(row) if row else None

    def get_teacher_students_attendance(self, dept_id, section_id):
        rows = self.db.execute(
            """
            SELECT
                s.roll_no,
                s.name,
                a.date,
                a.time,
                a.confidence
            FROM attendance a
            JOIN students s ON a.user_id = s.user_id
            WHERE s.dept_id = ?
              AND s.section_id = ?
            ORDER BY a.date DESC
            LIMIT 100
            """,
            (dept_id, section_id),
            fetch=True
        )
        return [dict(r) for r in rows]

    # -------------------------------
    # Chairman → all attendance
    # -------------------------------
    def get_all_attendance(self):
        rows = self.db.execute(
            """
            SELECT
                u.username,
                a.role,
                a.date,
                a.time,
                a.confidence,
                a.marked_by
            FROM attendance a
            JOIN users u ON a.user_id = u.user_id
            ORDER BY a.date DESC
            LIMIT 100
            """,
            fetch=True
        )
        return [dict(r) for r in rows]

    # ==================================================
    # VOICE EMBEDDING FUNCTIONS
    # ==================================================

    def add_voice_embedding(self, user_id, embedding_vector, sample_type='enrollment',actor_id=None):
        if not isinstance(embedding_vector, np.ndarray) or embedding_vector.shape != (192,):
            return {'status': False, 'message': 'Expected a 192-dimensional speaker embedding.'}
        if not np.isfinite(embedding_vector).all() or np.linalg.norm(embedding_vector) < 1e-8:
            return {'status': False, 'message': 'Embedding must be finite and nonzero.'}
        if sample_type not in ('enrollment', 'retrain'):
            return {'status': False, 'message': 'Invalid sample type.'}
        try:
            with self.db.transaction() as conn:
                lock = ' FOR UPDATE' if self.db.postgres else ''
                if actor_id is not None:
                    from backend.errors import ValidationError
                    accounts={r['user_id']:r for r in conn.execute('SELECT user_id,role,is_active FROM users WHERE user_id IN (?,?) ORDER BY user_id'+lock,(actor_id,user_id)).fetchall()}
                    actor=accounts.get(actor_id); user=accounts.get(user_id)
                    if not actor or not actor['is_active'] or actor['role'] not in ('chairman','faculty'):
                        raise ValidationError('Your account cannot enroll voice samples.')
                    if actor['role']=='faculty':
                        scoped=conn.execute('SELECT 1 FROM students s JOIN faculty f ON s.dept_id=f.dept_id WHERE s.user_id=? AND f.user_id=?',(user_id,actor_id)).fetchone()
                        if not scoped: raise ValidationError('You can enroll voices only for students in your department.')
                else:
                    user = conn.execute('SELECT role,is_active FROM users WHERE user_id=?' + lock, (user_id,)).fetchone()
                if not user or not user['is_active'] or user['role'] not in ('student','teacher','faculty'):
                    return {'status': False, 'message': 'Choose an active student, teacher, or faculty account.'}
                rows = conn.execute('SELECT embedding_vector FROM voice_embeddings WHERE user_id=?', (user_id,)).fetchall()
                if len(rows)>=10:
                    return {'status':False,'message':'This account already has 10 voice samples. Remove an obsolete sample before adding another.'}
                vector = embedding_vector.astype(np.float32)
                normalized = vector / np.linalg.norm(vector)
                for row in rows:
                    previous = np.frombuffer(row['embedding_vector'], dtype=np.float32)
                    if previous.shape != (192,) or not np.isfinite(previous).all():
                        continue
                    similarity = float(np.dot(normalized, previous / (np.linalg.norm(previous) + 1e-9)))
                    if similarity > .98:
                        return {'status': False, 'message': 'A nearly identical voice sample is already enrolled.'}
                conn.execute(
                    'INSERT INTO voice_embeddings (user_id,embedding_vector,sample_type,created_at) VALUES (?,?,?,?)',
                    (user_id,vector.tobytes(),sample_type,local_now().isoformat()))
                audit_event(conn,actor_id,'voice-sample-enrolled',user_id)
            return {'status': True, 'message': 'Voice embedding saved successfully.'}
        except Exception as exc:
            from backend.errors import ValidationError
            if isinstance(exc,ValidationError):
                return {'status':False,'message':str(exc)}
            from backend.errors import report_error
            report_error('voice-enrollment',exc)
            return {'status': False, 'message': 'Voice enrollment failed. Contact the administrator.'}

    def get_voice_embeddings(self, user_id):
        rows = self.db.execute(
            """
            SELECT embedding_vector
            FROM voice_embeddings
            WHERE user_id = ?
            """,
            (user_id,),
            fetch=True
        )
        return [np.frombuffer(r["embedding_vector"], dtype=np.float32) for r in rows]

    # -------------------------------
    # Utility
    # -------------------------------
    def user_exists(self, user_id):
        row = self.db.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user_id,),
            fetchone=True
        )
        return bool(row)
