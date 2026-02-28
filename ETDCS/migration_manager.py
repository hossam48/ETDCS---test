# =============================================================================
# database/migration_manager.py - Database Schema Migration System
# Task 12 - Phase 3 Architecture
# =============================================================================
# Provides automatic schema migrations for ETDCS database.
# 
# How it works:
# 1. On startup, check current migration version
# 2. Apply all pending migrations in order
# 3. Each migration is wrapped in a transaction
# 4. Migrations are idempotent (safe to run multiple times)
#
# Usage:
#   from database.migration_manager import run_all_migrations
#   
#   # In db_init.py:
#   run_all_migrations(conn)  # Pass existing connection
# =============================================================================

from __future__ import annotations

import sqlite3
from typing import List, Dict, Any, Optional

from config import DB_PATH


# =============================================================================
# MIGRATIONS DEFINITION
# =============================================================================

MIGRATIONS: List[Dict[str, Any]] = [
    # ── Migration 1: Workflow Audit Log (Task 8) ─────────────────────────────
    {
        "version": 1,
        "description": "Add workflow_audit_log table (Task 8)",
        "sql": [
            """CREATE TABLE IF NOT EXISTS workflow_audit_log (
                id INTEGER PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                from_status TEXT NOT NULL,
                to_status TEXT NOT NULL,
                changed_by INTEGER NOT NULL,
                changed_at DATETIME DEFAULT (datetime('now')),
                FOREIGN KEY (changed_by) REFERENCES users(id)
            )""",
            """CREATE INDEX IF NOT EXISTS idx_audit_entity
               ON workflow_audit_log (entity_type, entity_id)""",
        ]
    },
    
    # ── Migration 2: Soft Delete Columns (Task 9) ────────────────────────────
    # Note: SQLite ALTER TABLE ADD COLUMN fails if column exists.
    # This migration uses special handling - see run_migration().
    {
        "version": 2,
        "description": "Add soft delete columns (Task 9)",
        "sql": [],  # Handled specially in run_migration()
        "special": "soft_delete_columns"
    },
    
    # ── Migration 3: Event Log Table (Task 10) ───────────────────────────────
    {
        "version": 3,
        "description": "Add event_log table (Task 10)",
        "sql": [
            """CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                entity_name TEXT,
                project_ref TEXT,
                performed_by INTEGER NOT NULL,
                details TEXT,
                created_at DATETIME DEFAULT (datetime('now')),
                FOREIGN KEY (performed_by) REFERENCES users(id)
            )""",
            """CREATE INDEX IF NOT EXISTS idx_event_project 
               ON event_log (project_ref)""",
            """CREATE INDEX IF NOT EXISTS idx_event_created 
               ON event_log (created_at DESC)""",
        ]
    },
]


# =============================================================================
# SCHEMA MIGRATIONS TABLE SQL
# =============================================================================

SCHEMA_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    description TEXT    NOT NULL,
    applied_at  DATETIME DEFAULT (datetime('now'))
)
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_connection() -> sqlite3.Connection:
    """Get a new database connection."""
    return sqlite3.connect(DB_PATH)


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> List[str]:
    """
    Get list of column names for a table.
    
    Args:
        conn: Database connection
        table_name: Name of the table
    
    Returns:
        List of column names
    """
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def get_current_version(conn: sqlite3.Connection) -> int:
    """
    Get the current migration version from the database.
    
    Args:
        conn: Database connection
    
    Returns:
        Current version number (0 if no migrations applied)
    """
    try:
        # Check if schema_migrations table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        )
        if cursor.fetchone() is None:
            return 0
        
        # Get max version
        cursor = conn.execute("SELECT MAX(version) FROM schema_migrations")
        result = cursor.fetchone()
        return result[0] if result[0] is not None else 0
    
    except Exception:
        return 0


def _run_migration_special_soft_delete(conn: sqlite3.Connection) -> bool:
    """
    Special handler for Migration 2: Add soft delete columns.
    
    SQLite ALTER TABLE ADD COLUMN fails if column already exists,
    so we check first using PRAGMA table_info.
    
    Args:
        conn: Database connection
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check and add deleted_at to deliverables
        deliverables_cols = _get_table_columns(conn, "deliverables")
        if "deleted_at" not in deliverables_cols:
            conn.execute(
                "ALTER TABLE deliverables ADD COLUMN deleted_at DATETIME DEFAULT NULL"
            )
        
        # Check and add deleted_at to tasks
        tasks_cols = _get_table_columns(conn, "tasks")
        if "deleted_at" not in tasks_cols:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN deleted_at DATETIME DEFAULT NULL"
            )
        
        return True
    
    except Exception as e:
        print(f"Migration 2 error: {e}")
        return False


def run_migration(conn: sqlite3.Connection, migration: Dict[str, Any]) -> bool:
    """
    Apply a single migration.
    
    Args:
        conn: Database connection
        migration: Migration dict with version, description, sql
    
    Returns:
        True if successful, False otherwise
    """
    version = migration["version"]
    description = migration["description"]
    
    try:
        # Handle special migrations
        if migration.get("special") == "soft_delete_columns":
            if not _run_migration_special_soft_delete(conn):
                return False
        else:
            # Run regular SQL statements
            for sql in migration.get("sql", []):
                conn.execute(sql)
        
        # Record migration
        conn.execute(
            """INSERT INTO schema_migrations (version, description)
               VALUES (?, ?)""",
            (version, description)
        )
        
        return True
    
    except Exception as e:
        print(f"Migration {version} failed: {e}")
        return False


def run_all_migrations(conn: Optional[sqlite3.Connection] = None) -> int:
    """
    Run all pending migrations.
    
    This is the main entry point. It:
    1. Opens a connection if not provided
    2. Creates schema_migrations table if needed
    3. Gets current version
    4. Applies all migrations with version > current
    5. Returns count of applied migrations
    
    Args:
        conn: Optional existing connection. If None, creates its own.
    
    Returns:
        Number of migrations applied
    """
    _own_conn = conn is None
    if _own_conn:
        conn = get_connection()
    
    applied_count = 0
    
    try:
        # Ensure schema_migrations table exists
        conn.execute(SCHEMA_MIGRATIONS_TABLE_SQL)
        conn.commit()
        
        # Get current version
        current_version = get_current_version(conn)
        
        # Apply pending migrations
        for migration in MIGRATIONS:
            version = migration["version"]
            
            if version <= current_version:
                continue  # Already applied
            
            # Begin transaction for this migration
            try:
                if run_migration(conn, migration):
                    conn.commit()
                    applied_count += 1
                    print(f"✓ Migration {version}: {migration['description']}")
                else:
                    conn.rollback()
                    print(f"✗ Migration {version} failed, rolling back")
                    break  # Stop on failure
            
            except Exception as e:
                conn.rollback()
                print(f"✗ Migration {version} error: {e}")
                break
        
        return applied_count
    
    finally:
        if _own_conn:
            conn.close()


def get_migration_status(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """
    Get status of all migrations.
    
    Args:
        conn: Optional existing connection
    
    Returns:
        List of migration status dicts:
        [{
            "version": int,
            "description": str,
            "applied": bool,
            "applied_at": str or None,
        }]
    """
    _own_conn = conn is None
    if _own_conn:
        conn = get_connection()
    
    try:
        # Get applied migrations
        applied = {}
        try:
            cursor = conn.execute(
                "SELECT version, applied_at FROM schema_migrations"
            )
            for row in cursor.fetchall():
                applied[row[0]] = row[1]
        except Exception:
            pass  # Table doesn't exist yet
        
        # Build status list
        status = []
        for migration in MIGRATIONS:
            version = migration["version"]
            status.append({
                "version": version,
                "description": migration["description"],
                "applied": version in applied,
                "applied_at": applied.get(version),
            })
        
        return status
    
    finally:
        if _own_conn:
            conn.close()


def get_pending_migrations(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """
    Get list of pending (not yet applied) migrations.
    
    Args:
        conn: Optional existing connection
    
    Returns:
        List of pending migration dicts
    """
    status = get_migration_status(conn)
    return [m for m in status if not m["applied"]]


def get_applied_migrations(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """
    Get list of applied migrations.
    
    Args:
        conn: Optional existing connection
    
    Returns:
        List of applied migration dicts
    """
    status = get_migration_status(conn)
    return [m for m in status if m["applied"]]


# =============================================================================
# INITIALIZATION
# =============================================================================

# When module is imported, we don't auto-run migrations.
# Migrations should be run explicitly from db_init.py
