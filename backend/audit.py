"""Mutation audit metadata only: no names, passwords, recordings or vectors."""
from backend.config import local_now

def audit_event(conn,actor_id,operation,target_id):
    conn.execute('INSERT INTO audit_events (actor_id,operation,target_id,created_at) VALUES (?,?,?,?)',
                 (actor_id,operation,target_id,local_now().isoformat()))
