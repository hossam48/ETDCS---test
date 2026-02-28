# =============================================================================
# workflow_engine.py - Status Workflow State Machine
# Task 8 - Phase 3 Architecture
# =============================================================================
# Enforces valid status transitions for Deliverables and Tasks.
# No status can be set arbitrarily — every transition must be defined here.
#
# Deliverable flow:
#   Planned → In Progress → Under Review → Approved
#                  ↕              ↕
#               On Hold       Cancelled
#
# Task flow:
#   Not Started → In Progress → Under Review → Completed
#                     ↕              ↕
#                  On Hold       Cancelled
#
# Role permissions:
#   Engineer : forward transitions only (start work, submit for review)
#   Lead     : forward + reject back to In Progress + put On Hold
#   Manager  : all transitions including Approve and Cancel
# =============================================================================

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Tuple

from config import DB_PATH


# =============================================================================
# TRANSITION TABLES
# =============================================================================

# Each key is (from_status, to_status) → minimum role required
# Role hierarchy: Engineer < Lead < Manager

_DELIVERABLE_TRANSITIONS: Dict[Tuple[str, str], str] = {
    # Normal forward flow
    ("Planned",        "In Progress"):    "Engineer",
    ("In Progress",    "Under Review"):   "Engineer",
    ("Under Review",   "Approved"):       "Manager",
    # Rejection (back to In Progress)
    ("Under Review",   "In Progress"):    "Lead",
    # Hold / resume
    ("In Progress",    "On Hold"):        "Lead",
    ("Under Review",   "On Hold"):        "Lead",
    ("On Hold",        "In Progress"):    "Lead",
    # Cancel (from any active state)
    ("Planned",        "Cancelled"):      "Manager",
    ("In Progress",    "Cancelled"):      "Manager",
    ("Under Review",   "Cancelled"):      "Manager",
    ("On Hold",        "Cancelled"):      "Manager",
    # Re-open cancelled (Manager only)
    ("Cancelled",      "Planned"):        "Manager",
}

_TASK_TRANSITIONS: Dict[Tuple[str, str], str] = {
    # Normal forward flow
    ("Not Started",    "In Progress"):    "Engineer",
    ("In Progress",    "Under Review"):   "Engineer",
    ("Under Review",   "Completed"):      "Lead",
    # Rejection (back to In Progress)
    ("Under Review",   "In Progress"):    "Lead",
    # Hold / resume
    ("In Progress",    "On Hold"):        "Lead",
    ("Under Review",   "On Hold"):        "Lead",
    ("On Hold",        "In Progress"):    "Lead",
    # Cancel
    ("Not Started",    "Cancelled"):      "Manager",
    ("In Progress",    "Cancelled"):      "Manager",
    ("Under Review",   "Cancelled"):      "Manager",
    ("On Hold",        "Cancelled"):      "Manager",
    # Re-open
    ("Cancelled",      "Not Started"):    "Manager",
    ("Completed",      "In Progress"):    "Manager",
}

# Role hierarchy for permission checking
_ROLE_RANK: Dict[str, int] = {
    "Engineer": 1,
    "Lead":     2,
    "Manager": 3,
}


# =============================================================================
# RESULT TYPE
# =============================================================================

@dataclass
class TransitionResult:
    """Result of an attempted status transition."""
    success: bool
    message: str
    old_status: str
    new_status: Optional[str] = None


# =============================================================================
# CORE ENGINE
# =============================================================================

def get_allowed_transitions(
    entity_type: str,       # "deliverable" or "task"
    current_status: str,
    user_role: str,
) -> List[str]:
    """
    Return list of statuses the user can transition to from current_status.

    Args:
        entity_type:    "deliverable" or "task"
        current_status: Current status string
        user_role:      User's role ("Engineer", "Lead", "Manager")

    Returns:
        List of valid next statuses for this role
    """
    table = _DELIVERABLE_TRANSITIONS if entity_type == "deliverable" else _TASK_TRANSITIONS
    user_rank = _ROLE_RANK.get(user_role, 0)

    allowed = []
    for (from_st, to_st), required_role in table.items():
        if from_st == current_status:
            if user_rank >= _ROLE_RANK.get(required_role, 99):
                allowed.append(to_st)

    return sorted(allowed)


def can_transition(
    entity_type: str,
    current_status: str,
    new_status: str,
    user_role: str,
) -> Tuple[bool, str]:
    """
    Check if a transition is allowed for this role.

    Returns:
        (allowed: bool, reason: str)
    """
    table = _DELIVERABLE_TRANSITIONS if entity_type == "deliverable" else _TASK_TRANSITIONS
    key = (current_status, new_status)

    if key not in table:
        return False, f"Transition '{current_status}' → '{new_status}' is not defined."

    required_role = table[key]
    user_rank = _ROLE_RANK.get(user_role, 0)
    required_rank = _ROLE_RANK.get(required_role, 99)

    if user_rank < required_rank:
        return False, (
            f"Requires '{required_role}' role or above. "
            f"Your role '{user_role}' is not permitted."
        )

    return True, "OK"


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def transition_deliverable(
    deliverable_id: int,
    new_status: str,
    user_id: int,
    user_role: str,
    conn: Optional[sqlite3.Connection] = None,
) -> TransitionResult:
    """
    Attempt to transition a deliverable to a new status.

    Args:
        deliverable_id: ID of the deliverable
        new_status:     Target status
        user_id:        ID of the user performing the action
        user_role:      Role of the user
        conn:           Optional existing connection (will create one if None)

    Returns:
        TransitionResult with success flag and message
    """
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)

    try:
        row = conn.execute(
            "SELECT status FROM deliverables WHERE id=?", (deliverable_id,)
        ).fetchone()

        if row is None:
            return TransitionResult(False, "Deliverable not found.", "")

        current_status = row[0]

        allowed, reason = can_transition("deliverable", current_status, new_status, user_role)
        if not allowed:
            return TransitionResult(False, reason, current_status)

        conn.execute(
            "UPDATE deliverables SET status=? WHERE id=?",
            (new_status, deliverable_id),
        )

        # Write to audit log
        _log_transition(
            conn, "deliverable", deliverable_id,
            current_status, new_status, user_id
        )

        conn.commit()
        return TransitionResult(True, f"Status updated: {current_status} → {new_status}", current_status, new_status)

    except Exception as e:
        return TransitionResult(False, f"Database error: {e}", "")

    finally:
        if _own_conn:
            conn.close()


def transition_task(
    task_id: int,
    new_status: str,
    user_id: int,
    user_role: str,
    conn: Optional[sqlite3.Connection] = None,
) -> TransitionResult:
    """
    Attempt to transition a task to a new status.

    Args:
        task_id:    ID of the task
        new_status: Target status
        user_id:    ID of the user performing the action
        user_role:  Role of the user
        conn:       Optional existing connection

    Returns:
        TransitionResult with success flag and message
    """
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)

    try:
        row = conn.execute(
            "SELECT status, assigned_engineer_id FROM tasks WHERE id=?", (task_id,)
        ).fetchone()

        if row is None:
            return TransitionResult(False, "Task not found.", "")

        current_status, assigned_id = row

        # Engineers can only transition their own tasks
        if user_role == "Engineer" and assigned_id != user_id:
            return TransitionResult(
                False,
                "Engineers can only update their own tasks.",
                current_status,
            )

        allowed, reason = can_transition("task", current_status, new_status, user_role)
        if not allowed:
            return TransitionResult(False, reason, current_status)

        conn.execute(
            "UPDATE tasks SET status=? WHERE id=?",
            (new_status, task_id),
        )

        # Auto-set progress when completing
        if new_status == "Completed":
            conn.execute(
                "UPDATE tasks SET progress=100 WHERE id=?", (task_id,)
            )

        # Auto-clear progress when re-opening
        if new_status in ("Not Started", "In Progress") and current_status == "Completed":
            conn.execute(
                "UPDATE tasks SET progress=0 WHERE id=?", (task_id,)
            )

        _log_transition(conn, "task", task_id, current_status, new_status, user_id)

        conn.commit()
        return TransitionResult(True, f"Status updated: {current_status} → {new_status}", current_status, new_status)

    except Exception as e:
        return TransitionResult(False, f"Database error: {e}", "")

    finally:
        if _own_conn:
            conn.close()


# =============================================================================
# AUDIT LOG
# =============================================================================

AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS workflow_audit_log (
    id              INTEGER PRIMARY KEY,
    entity_type     TEXT NOT NULL,
    entity_id       INTEGER NOT NULL,
    from_status     TEXT NOT NULL,
    to_status       TEXT NOT NULL,
    changed_by      INTEGER NOT NULL,
    changed_at      DATETIME DEFAULT (datetime('now')),
    FOREIGN KEY (changed_by) REFERENCES users(id)
)
"""


def ensure_audit_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create workflow_audit_log table if it doesn't exist."""
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(AUDIT_TABLE_SQL)
        conn.commit()
    finally:
        if _own_conn:
            conn.close()


def _log_transition(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    from_status: str,
    to_status: str,
    user_id: int,
) -> None:
    """Insert a row into the audit log (called inside an open transaction)."""
    try:
        conn.execute(
            """INSERT INTO workflow_audit_log
               (entity_type, entity_id, from_status, to_status, changed_by)
               VALUES (?, ?, ?, ?, ?)""",
            (entity_type, entity_id, from_status, to_status, user_id),
        )
    except Exception:
        pass  # Audit failure should never block the main operation


def get_audit_history(
    entity_type: str,
    entity_id: int,
    conn: Optional[sqlite3.Connection] = None,
) -> list:
    """
    Return the status transition history for an entity.

    Returns:
        List of dicts: {from_status, to_status, changed_by_name, changed_at}
    """
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)

    try:
        rows = conn.execute(
            """SELECT a.from_status, a.to_status, u.full_name, a.changed_at
               FROM workflow_audit_log a
               JOIN users u ON a.changed_by = u.id
               WHERE a.entity_type=? AND a.entity_id=?
               ORDER BY a.changed_at ASC""",
            (entity_type, entity_id),
        ).fetchall()

        return [
            {
                "from_status": r[0],
                "to_status":   r[1],
                "changed_by":  r[2],
                "changed_at":  r[3],
            }
            for r in rows
        ]

    finally:
        if _own_conn:
            conn.close()


# =============================================================================
# UI HELPER — STATUS BADGE HTML
# =============================================================================

_STATUS_COLORS: Dict[str, Tuple[str, str]] = {
    # (background, text)
    "Planned":       ("#e0e7ff", "#3730a3"),
    "Not Started":   ("#e2e8f0", "#475569"),
    "In Progress":   ("#fef3c7", "#92400e"),
    "Under Review":  ("#fce7f3", "#9d174d"),
    "Approved":      ("#d1fae5", "#065f46"),
    "Completed":     ("#d1fae5", "#065f46"),
    "On Hold":       ("#fee2e2", "#991b1b"),
    "Cancelled":     ("#f1f5f9", "#64748b"),
}


def status_badge_html(status: str) -> str:
    """Return an HTML badge for a status string."""
    bg, color = _STATUS_COLORS.get(status, ("#f1f5f9", "#64748b"))
    return (
        f"<span style='background:{bg}; color:{color}; "
        f"padding:3px 10px; border-radius:12px; font-size:12px; "
        f"font-weight:600;'>{status}</span>"
    )
