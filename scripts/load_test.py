"""Reproducible synthetic local test. Never connects to the deployed database.

Measures database operations, not browser sessions or real voice inference.
"""
import argparse
import json
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.database import DatabaseHandler
from backend.records import attendance_page
from backend.directory import campus_accounts
from backend.attendance_handler import AttendanceHandler

def run(students=20000,days=30,workers=20,requests=400):
    if not 100<=students<=100000 or not 1<=days<=365 or not 1<=workers<=100:
        raise ValueError('Use 100–100000 students, 1–365 days, and 1–100 workers.')
    with tempfile.TemporaryDirectory() as folder:
        db=DatabaseHandler(Path(folder)/'synthetic.db')
        seed_start=time.perf_counter()
        with db.transaction() as conn:
            conn.raw.executemany('INSERT INTO departments (dept_id,dept_name) VALUES (?,?)',[(i,f'Department {i}') for i in range(1,5)])
            conn.execute("INSERT INTO semesters (semester_no) VALUES (1)")
            conn.execute("INSERT INTO sections (section_name) VALUES ('A')")
            conn.execute("INSERT INTO users (user_id,username,password_hash,role,created_at) VALUES (1,'fixture-admin',?,'chairman','fixture')",(b'synthetic-not-a-login',))
            conn.raw.executemany("INSERT INTO users (user_id,username,password_hash,role,created_at) VALUES (?,?,?,'student','fixture')",((i+2,f'fixture{i:06d}',b'synthetic-not-a-login') for i in range(students)))
            conn.raw.executemany('INSERT INTO students (user_id,roll_no,name,dept_id,semester_id,section_id) VALUES (?,?,?,?,1,1)',((i+2,f'R{i:06d}',f'Synthetic Student {i}',i%4+1) for i in range(students)))
            vector=(np.ones(192,dtype=np.float32)/np.sqrt(192)).tobytes()
            conn.raw.executemany("INSERT INTO voice_embeddings (user_id,embedding_vector,created_at) VALUES (?,?,'fixture')",((i+2,vector) for i in range(students)))
            for day in range(days):
                value=(date(2025,1,1)+timedelta(days=day)).isoformat()
                conn.raw.executemany("INSERT INTO attendance (user_id,role,dept_id,semester_id,section_id,date,time,confidence) VALUES (?,'student',?,1,1,?,'09:00:00',.9)",((i+2,i%4+1,value) for i in range(students)))
        seed_seconds=time.perf_counter()-seed_start
        def read(number):
            started=time.perf_counter()
            if number%3==0:
                rows=attendance_page(db,1,limit=101)
            elif number%3==1:
                rows=attendance_page(db,number%students+2,limit=101)
                assert all(r['username']==f'fixture{number%students:06d}' for r in rows)
            else:
                rows=campus_accounts(db,actor_id=1,search=f'fixture{number%students:06d}',limit=101)
            assert len(rows)<=101
            return time.perf_counter()-started
        started=time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            timings=list(pool.map(read,range(requests)))
        read_seconds=time.perf_counter()-started
        handler=AttendanceHandler(db)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            duplicates=list(pool.map(lambda _:handler.mark_attendance(2),range(workers)))
        success=sum(bool(r['status']) for r in duplicates)
        assert success==1,'Concurrent duplicate attendance created more than one row.'
        with ThreadPoolExecutor(max_workers=workers) as pool:
            independent=list(pool.map(lambda uid:handler.mark_attendance(uid),range(3,workers+3)))
        assert all(r['status'] for r in independent)
        return {'kind':'local SQLite synthetic database operations; browser/network/authentication/inference excluded',
                'students':students,'historical_attendance_rows':students*days,'synthetic_voice_profiles':students,
                'concurrent_workers':workers,'read_requests':requests,'read_failures':0,
                'seed_seconds':round(seed_seconds,3),'read_elapsed_seconds':round(read_seconds,3),
                'read_p50_ms':round(float(np.percentile(timings,50))*1000,2),
                'read_p95_ms':round(float(np.percentile(timings,95))*1000,2),
                'read_max_ms':round(max(timings)*1000,2),'duplicate_write_requests':workers,
                'duplicate_write_successes':success,'independent_write_successes':len(independent),
                'database_bytes':Path(db.db_path).stat().st_size,
                'voice_capacity':'one active inference and at most two waiting; overload returns retry message'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--students',type=int,default=20000)
    parser.add_argument('--days',type=int,default=30)
    parser.add_argument('--workers',type=int,default=20)
    parser.add_argument('--requests',type=int,default=400)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=run(args.students,args.days,args.workers,args.requests)
    text=json.dumps(result,indent=2)
    if args.output: args.output.write_text(text,encoding='utf-8')
    print(text)
