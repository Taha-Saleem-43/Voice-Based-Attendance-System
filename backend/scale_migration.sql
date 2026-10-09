-- Additive production migration. Contains no campus records or credentials.
CREATE INDEX IF NOT EXISTS students_section_idx ON public.students(section_id);
CREATE INDEX IF NOT EXISTS students_semester_idx ON public.students(semester_id);
CREATE INDEX IF NOT EXISTS teachers_dept_idx ON public.teachers(dept_id);
CREATE INDEX IF NOT EXISTS teachers_section_idx ON public.teachers(section_id);
CREATE INDEX IF NOT EXISTS faculty_dept_idx ON public.faculty(dept_id);
CREATE INDEX IF NOT EXISTS attendance_dept_date_idx ON public.attendance(dept_id,date,attendance_id);
CREATE INDEX IF NOT EXISTS attendance_section_idx ON public.attendance(section_id);
CREATE INDEX IF NOT EXISTS attendance_semester_idx ON public.attendance(semester_id);
CREATE INDEX IF NOT EXISTS attendance_date_page_idx ON public.attendance(date DESC,attendance_id DESC);
CREATE TABLE IF NOT EXISTS public.audit_events (
 event_id SERIAL PRIMARY KEY,
 actor_id INTEGER REFERENCES public.users(user_id),
 operation TEXT NOT NULL,
 target_id INTEGER,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_created_idx ON public.audit_events(created_at);
CREATE INDEX IF NOT EXISTS audit_actor_idx ON public.audit_events(actor_id);
ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.audit_events FROM anon,authenticated;
