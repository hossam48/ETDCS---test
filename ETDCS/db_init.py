# =============================================================================
# database/db_init.py - Database Initialization
# Updated: Task 12 — integrated migration manager
# =============================================================================
# This module handles:
# 1. Creating essential tables (users, deliverables, tasks, documents)
# 2. Creating default admin user
# 3. Running schema migrations via migration_manager
# =============================================================================

import sqlite3
import os
from auth import hash_password

DB_PATH = os.path.join("database", "etdcs_v7.db")
FILES_DIR = "files"


def init_directories():
    """Create necessary directories."""
    os.makedirs(FILES_DIR, exist_ok=True)
    os.makedirs("database", exist_ok=True)


def init_db():
    """
    Initialize database schema and default admin user.
    
    Core tables are created here. Additional tables and schema changes
    are handled by the migration_manager.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Core Tables (always created) ──────────────────────────────────────────
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, full_name TEXT, email TEXT UNIQUE,
                  password TEXT, role TEXT, discipline TEXT, join_date DATE)''')

    c.execute('''CREATE TABLE IF NOT EXISTS deliverables
                 (id INTEGER PRIMARY KEY, project_ref TEXT, station TEXT,
                  discipline TEXT, type TEXT, name TEXT,
                  planned_start_date DATE, planned_finish_date DATE,
                  status TEXT DEFAULT 'Planned', mdl_synced INTEGER)''')

    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id INTEGER PRIMARY KEY, project_ref TEXT, station TEXT,
                  deliverable_id INTEGER, name TEXT,
                  assigned_engineer_id INTEGER, priority TEXT, due_date DATE,
                  description TEXT, progress INTEGER DEFAULT 0,
                  status TEXT DEFAULT 'Not Started')''')

    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY, project_ref TEXT, station TEXT,
                  task_id INTEGER, title TEXT, type TEXT,
                  file_path TEXT, uploaded_by INTEGER, upload_date DATE)''')

    # ── Default Admin User ────────────────────────────────────────────────────
    
    if c.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
        c.execute(
            "INSERT INTO users (full_name, email, password, role, discipline, join_date) "
            "VALUES (?, ?, ?, ?, ?, DATE('now'))",
            ("Admin Manager", "admin@elsewedy.com", hash_password("123456"), "Manager", "All"),
        )

    conn.commit()

    # ── Task 12: Run Schema Migrations ────────────────────────────────────────
    # This handles all additional tables and schema changes:
    # - Migration 1: workflow_audit_log table
    # - Migration 2: soft delete columns (deleted_at)
    # - Migration 3: event_log table
    # - Future migrations...
    
    from database.migration_manager import run_all_migrations
    applied = run_all_migrations(conn)
    if applied > 0:
        print(f"✓ Applied {applied} migration(s)")
    # ─────────────────────────────────────────────────────────────────────────

    conn.close()


def get_db_connection() -> sqlite3.Connection:
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)


# =============================================================================
# LEGACY COMPATIBILITY - deprecated functions kept for backward compatibility
# =============================================================================

def migrate_soft_delete(conn):
    """
    Deprecated: Soft delete migration is now handled by migration_manager.
    Kept for backward compatibility - does nothing.
    """
    pass  # Now handled by migration_manager


# =============================================================================
# INITIALIZATION ON IMPORT
# =============================================================================

init_directories()
init_db()
