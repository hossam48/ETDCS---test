# =============================================================================
# event_log.py - Domain Event Logging System
# Task 10 - Phase 3 Architecture
# =============================================================================
# Provides centralized logging for all important domain events:
# - Task creation, deletion, restoration, progress updates
# - Deliverable creation, deletion, restoration
# - MDL imports
# - User creation
#
# Usage:
#   from event_log import log_event, EventType
#
#   log_event(
#       event_type=EventType.TASK_CREATED,
#       entity_type="task",
#       entity_id=new_task_id,
#       entity_name="Task Name",
#       project_ref="Project Name",
#       performed_by=user_id,
#       details={"priority": "High", "assigned_to": "Engineer Name"},
#   )
# =============================================================================

from __future__ import annotations

import json
import sqlite3
from typing import Optional, List, Dict, Any, Union

from config import DB_PATH


# =============================================================================
# EVENT TYPE CONSTANTS
# =============================================================================

class EventType:
    """
    Constants for all supported event types.
    Use these when calling log_event() to ensure consistency.
    """
    # Task events
    TASK_CREATED = "task.created"
    TASK_DELETED = "task.deleted"
    TASK_RESTORED = "task.restored"
    TASK_PROGRESS = "task.progress_updated"

    # Deliverable events
    DELIVERABLE_CREATED = "deliverable.created"
    DELIVERABLE_DELETED = "deliverable.deleted"
    DELIVERABLE_RESTORED = "deliverable.restored"

    # MDL events
    MDL_IMPORTED = "mdl.imported"

    # User events
    USER_CREATED = "user.created"


# =============================================================================
# TABLE SCHEMA
# =============================================================================

EVENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS event_log (
    id           INTEGER PRIMARY KEY,
    event_type   TEXT    NOT NULL,
    entity_type  TEXT    NOT NULL,
    entity_id    INTEGER,
    entity_name  TEXT,
    project_ref  TEXT,
    performed_by INTEGER NOT NULL,
    details      TEXT,
    created_at   DATETIME DEFAULT (datetime('now')),
    FOREIGN KEY (performed_by) REFERENCES users(id)
)
"""

EVENT_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_event_project
ON event_log (project_ref)
"""

EVENT_INDEX_DATE_SQL = """
CREATE INDEX IF NOT EXISTS idx_event_created
ON event_log (created_at DESC)
"""


# =============================================================================
# TABLE INITIALIZATION
# =============================================================================

def ensure_event_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create event_log table and indexes if they don't exist.
    
    Safe to call multiple times. Should be called on app startup.
    
    Args:
        conn: Optional existing connection. If None, creates its own.
    """
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)
    
    try:
        conn.execute(EVENT_TABLE_SQL)
        conn.execute(EVENT_INDEX_SQL)
        conn.execute(EVENT_INDEX_DATE_SQL)
        conn.commit()
    finally:
        if _own_conn:
            conn.close()


# =============================================================================
# CORE LOGGING FUNCTION
# =============================================================================

def log_event(
    event_type: str,
    entity_type: str,
    performed_by: int,
    entity_id: Optional[int] = None,
    entity_name: Optional[str] = None,
    project_ref: Optional[str] = None,
    details: Optional[Union[str, Dict[str, Any]]] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """
    Write an event to the event_log table.
    
    This function is designed to never raise exceptions - logging failures
    should not interrupt the main application flow.
    
    Args:
        event_type:   One of EventType constants (e.g., EventType.TASK_CREATED)
        entity_type:  Type of entity (e.g., "task", "deliverable", "user")
        performed_by: ID of the user who performed the action
        entity_id:    Optional ID of the affected entity
        entity_name:  Optional name/title of the affected entity
        project_ref:  Optional project reference (for project-scoped events)
        details:      Optional details - can be a dict (will be JSON-encoded) or string
        conn:         Optional existing connection (for transaction participation)
    
    Note:
        - If conn is provided, this function does NOT commit (caller manages transaction)
        - If conn is None, this function creates its own connection and commits
        - Failures are silently ignored to prevent disrupting the application
    """
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)
    
    try:
        # Convert details to JSON string if it's a dict
        details_str: Optional[str] = None
        if details is not None:
            if isinstance(details, dict):
                details_str = json.dumps(details)
            else:
                details_str = str(details)
        
        conn.execute(
            """INSERT INTO event_log
               (event_type, entity_type, entity_id, entity_name, 
                project_ref, performed_by, details)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_type, entity_type, entity_id, entity_name,
             project_ref, performed_by, details_str),
        )
        
        # Only commit if we opened our own connection
        if _own_conn:
            conn.commit()
    
    except Exception:
        # Silently ignore logging failures
        # Event logging should never break the main application
        pass
    
    finally:
        if _own_conn:
            conn.close()


# =============================================================================
# QUERY FUNCTIONS
# =============================================================================

def get_project_events(
    project_ref: str,
    limit: int = 100,
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    """
    Return recent events for a specific project.
    
    Args:
        project_ref: Project reference to filter by
        limit:       Maximum number of events to return (default: 100)
        conn:        Optional existing connection
    
    Returns:
        List of event dicts with keys:
        - id, event_type, entity_type, entity_id, entity_name,
        - performed_by_name (user's full name), details, created_at
    """
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)
    
    try:
        rows = conn.execute(
            """SELECT e.id, e.event_type, e.entity_type, e.entity_id,
                      e.entity_name, u.full_name, e.details, e.created_at
               FROM event_log e
               JOIN users u ON e.performed_by = u.id
               WHERE e.project_ref = ?
               ORDER BY e.created_at DESC
               LIMIT ?""",
            (project_ref, limit),
        ).fetchall()
        
        return [
            {
                "id":              r[0],
                "event_type":      r[1],
                "entity_type":     r[2],
                "entity_id":       r[3],
                "entity_name":     r[4],
                "performed_by_name": r[5],
                "details":         r[6],
                "created_at":      r[7],
            }
            for r in rows
        ]
    
    finally:
        if _own_conn:
            conn.close()


def get_recent_events(
    limit: int = 50,
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    """
    Return recent events across all projects (system-wide).
    
    Args:
        limit: Maximum number of events to return (default: 50)
        conn:  Optional existing connection
    
    Returns:
        List of event dicts with same format as get_project_events(),
        plus project_ref field.
    """
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)
    
    try:
        rows = conn.execute(
            """SELECT e.id, e.event_type, e.entity_type, e.entity_id,
                      e.entity_name, e.project_ref, u.full_name, e.details, 
                      e.created_at
               FROM event_log e
               JOIN users u ON e.performed_by = u.id
               ORDER BY e.created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        
        return [
            {
                "id":              r[0],
                "event_type":      r[1],
                "entity_type":     r[2],
                "entity_id":       r[3],
                "entity_name":     r[4],
                "project_ref":     r[5],
                "performed_by_name": r[6],
                "details":         r[7],
                "created_at":      r[8],
            }
            for r in rows
        ]
    
    finally:
        if _own_conn:
            conn.close()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_event_count(
    project_ref: Optional[str] = None,
    event_type: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """
    Count events, optionally filtered by project and/or event type.
    
    Args:
        project_ref: Optional project filter
        event_type:  Optional event type filter
        conn:        Optional existing connection
    
    Returns:
        Count of matching events
    """
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)
    
    try:
        where_clauses = []
        params = []
        
        if project_ref:
            where_clauses.append("project_ref = ?")
            params.append(project_ref)
        
        if event_type:
            where_clauses.append("event_type = ?")
            params.append(event_type)
        
        sql = "SELECT COUNT(*) FROM event_log"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        
        return conn.execute(sql, params).fetchone()[0]
    
    finally:
        if _own_conn:
            conn.close()


def get_user_activity(
    user_id: int,
    limit: int = 50,
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    """
    Return recent activity by a specific user.
    
    Args:
        user_id: User ID to filter by
        limit:   Maximum number of events to return
        conn:    Optional existing connection
    
    Returns:
        List of event dicts
    """
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)
    
    try:
        rows = conn.execute(
            """SELECT id, event_type, entity_type, entity_id, entity_name,
                      project_ref, details, created_at
               FROM event_log
               WHERE performed_by = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        
        return [
            {
                "id":          r[0],
                "event_type":  r[1],
                "entity_type": r[2],
                "entity_id":   r[3],
                "entity_name": r[4],
                "project_ref": r[5],
                "details":     r[6],
                "created_at":  r[7],
            }
            for r in rows
        ]
    
    finally:
        if _own_conn:
            conn.close()


# =============================================================================
# INITIALIZATION ON IMPORT
# =============================================================================

# Ensure table exists when module is imported
ensure_event_table()
