CREATE TABLE IF NOT EXISTS departments (
 dept_id INTEGER PRIMARY KEY AUTOINCREMENT, dept_name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS semesters (
 semester_id INTEGER PRIMARY KEY AUTOINCREMENT,
 semester_no INTEGER NOT NULL UNIQUE CHECK (semester_no BETWEEN 1 AND 8)
);
CREATE TABLE IF NOT EXISTS sections (
 section_id INTEGER PRIMARY KEY AUTOINCREMENT, section_name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS users (
 user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
 password_hash BLOB NOT NULL,
 role TEXT NOT NULL CHECK (role IN ('student','teacher','faculty','chairman')),
 is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS students (
 user_id INTEGER PRIMARY KEY REFERENCES users(user_id), roll_no TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL, dept_id INTEGER NOT NULL REFERENCES departments(dept_id),
 semester_id INTEGER NOT NULL REFERENCES semesters(semester_id),
 section_id INTEGER NOT NULL REFERENCES sections(section_id)
);
CREATE TABLE IF NOT EXISTS teachers (
 user_id INTEGER PRIMARY KEY REFERENCES users(user_id), name TEXT NOT NULL,
 dept_id INTEGER NOT NULL REFERENCES departments(dept_id), designation TEXT,
 section_id INTEGER REFERENCES sections(section_id)
);
CREATE TABLE IF NOT EXISTS faculty (
 user_id INTEGER PRIMARY KEY REFERENCES users(user_id), name TEXT NOT NULL,
 dept_id INTEGER NOT NULL REFERENCES departments(dept_id), designation TEXT
);
CREATE TABLE IF NOT EXISTS voice_embeddings (
 embedding_id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(user_id), embedding_vector BLOB NOT NULL,
 sample_type TEXT NOT NULL DEFAULT 'enrollment' CHECK (sample_type IN ('enrollment','retrain')),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance (
 attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(user_id),
 role TEXT NOT NULL CHECK (role IN ('student','teacher','faculty')),
 dept_id INTEGER REFERENCES departments(dept_id),
 semester_id INTEGER REFERENCES semesters(semester_id),
 section_id INTEGER REFERENCES sections(section_id),
 date TEXT NOT NULL, time TEXT NOT NULL, confidence REAL,
 marked_by TEXT NOT NULL DEFAULT 'voice' CHECK (marked_by IN ('voice','manual')),
 UNIQUE (user_id,date)
);
CREATE TABLE IF NOT EXISTS login_attempts (
 username TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0,
 blocked_until REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS embeddings_user_idx ON voice_embeddings(user_id);
CREATE INDEX IF NOT EXISTS students_group_idx ON students(dept_id,section_id);
CREATE INDEX IF NOT EXISTS students_section_idx ON students(section_id);
CREATE INDEX IF NOT EXISTS students_semester_idx ON students(semester_id);
CREATE INDEX IF NOT EXISTS teachers_dept_idx ON teachers(dept_id);
CREATE INDEX IF NOT EXISTS teachers_section_idx ON teachers(section_id);
CREATE INDEX IF NOT EXISTS faculty_dept_idx ON faculty(dept_id);
CREATE INDEX IF NOT EXISTS attendance_dept_date_idx ON attendance(dept_id,date,attendance_id);
CREATE INDEX IF NOT EXISTS attendance_section_idx ON attendance(section_id);
CREATE INDEX IF NOT EXISTS attendance_semester_idx ON attendance(semester_id);
CREATE INDEX IF NOT EXISTS attendance_date_page_idx ON attendance(date DESC,attendance_id DESC);
CREATE TABLE IF NOT EXISTS audit_events (
 event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 actor_id INTEGER REFERENCES users(user_id),
 operation TEXT NOT NULL,
 target_id INTEGER,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_created_idx ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS audit_actor_idx ON audit_events(actor_id);
