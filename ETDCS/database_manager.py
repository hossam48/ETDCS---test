# =============================================================================
# database_manager.py - Raw Database Operations
# =============================================================================
# All database queries are defined here. These are "raw" functions that
# perform actual DB operations. They should be wrapped by cache_manager
# for performance optimization.
#
# Updated: Task 9 — Added soft delete support
# =============================================================================

import sqlite3
import pandas as pd
from datetime import date, timedelta
from typing import Tuple, Dict, Any, Optional

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Get a new database connection."""
    return sqlite3.connect(DB_PATH)


# =============================================================================
# STATISTICS QUERIES
# =============================================================================

def get_statistics_raw(
    project: str,
    discipline: str = "All",
    station: str = "All",
) -> Dict[str, Any]:
    """
    Get project statistics.
    
    Returns:
        dict with: total_deliverables, total_tasks, overdue_tasks, avg_progress
    """
    conn = get_connection()
    
    try:
        # Build WHERE conditions
        where_clauses = ["project_ref=?", "deleted_at IS NULL"]  # Task 9: soft delete filter
        params = [project]
        
        if discipline != "All":
            where_clauses.append("discipline=?")
            params.append(discipline)
        
        if station != "All":
            where_clauses.append("station=?")
            params.append(station)
        
        sql_cond = " WHERE " + " AND ".join(where_clauses)
        
        # Total deliverables
        total_deliverables = conn.execute(
            f"SELECT COUNT(*) FROM deliverables{sql_cond}", params
        ).fetchone()[0]
        
        # Task WHERE (with aliases)
        task_where = ["t.deleted_at IS NULL", "d.deleted_at IS NULL"]  # Task 9: soft delete filter
        for cond in where_clauses:
            if 'deleted_at' in cond:
                continue  # Skip, already added
            elif 'discipline' in cond:
                task_where.append(f"d.{cond}")
            elif 'project_ref' in cond:
                task_where.append(f"t.{cond}")
            else:
                task_where.append(f"t.{cond}")
        task_sql_cond = " WHERE " + " AND ".join(task_where)
        
        # Total tasks
        total_tasks = conn.execute(
            f"SELECT COUNT(*) FROM tasks t JOIN deliverables d ON t.deliverable_id=d.id{task_sql_cond}",
            params
        ).fetchone()[0]
        
        # Overdue tasks
        today = str(date.today())
        overdue_tasks = conn.execute(
            f"""SELECT COUNT(*) FROM tasks t 
                JOIN deliverables d ON t.deliverable_id=d.id
                {task_sql_cond} AND t.due_date < ? AND t.progress < 100""",
            params + [today]
        ).fetchone()[0]
        
        # Average progress
        avg_result = conn.execute(
            f"SELECT AVG(progress) FROM tasks t JOIN deliverables d ON t.deliverable_id=d.id{task_sql_cond}",
            params
        ).fetchone()[0]
        avg_progress = round(avg_result or 0, 1)
        
        return {
            "total_deliverables": total_deliverables,
            "total_tasks": total_tasks,
            "overdue_tasks": overdue_tasks,
            "avg_progress": avg_progress,
        }
    
    finally:
        conn.close()


# =============================================================================
# TIMELINE DATA
# =============================================================================

def get_timeline_data_raw(
    project: str,
    discipline: str = "All",
    station: str = "All",
) -> pd.DataFrame:
    """
    Get timeline data for Gantt chart.
    
    Returns:
        DataFrame with: name, planned_start_date, planned_finish_date, discipline, station
    """
    conn = get_connection()
    
    try:
        where_clauses = ["project_ref=?", "planned_start_date IS NOT NULL", "deleted_at IS NULL"]  # Task 9
        params = [project]
        
        if discipline != "All":
            where_clauses.append("discipline=?")
            params.append(discipline)
        
        if station != "All":
            where_clauses.append("station=?")
            params.append(station)
        
        sql_cond = " WHERE " + " AND ".join(where_clauses)
        
        query = f"""
            SELECT name, planned_start_date, planned_finish_date, discipline, station
            FROM deliverables
            {sql_cond}
            ORDER BY planned_start_date
            LIMIT 30
        """
        
        df = pd.read_sql(query, conn, params=params)
        return df
    
    finally:
        conn.close()


# =============================================================================
# DELIVERABLES DATA
# =============================================================================

def get_deliverables_raw(
    project: str,
    discipline: str = "All",
    station: str = "All",
    search: str = "",
) -> pd.DataFrame:
    """
    Get all deliverables for project.
    
    Returns:
        DataFrame with deliverable details
    """
    conn = get_connection()
    
    try:
        where_clauses = ["project_ref=?", "deleted_at IS NULL"]  # Task 9
        params = [project]
        
        if discipline != "All":
            where_clauses.append("discipline=?")
            params.append(discipline)
        
        if station != "All":
            where_clauses.append("station=?")
            params.append(station)
        
        if search:
            where_clauses.append("name LIKE ?")
            params.append(f"%{search}%")
        
        sql_cond = " WHERE " + " AND ".join(where_clauses)
        
        query = f"""
            SELECT id, station, discipline, type, name, 
                   planned_start_date, planned_finish_date, status
            FROM deliverables
            {sql_cond}
        """
        
        df = pd.read_sql(query, conn, params=params)
        return df
    
    finally:
        conn.close()


def get_deliverables_paginated_raw(
    project: str,
    discipline: str = "All",
    station: str = "All",
    search: str = "",
    page: int = 1,
    page_size: int = 50,
) -> Tuple[pd.DataFrame, int]:
    """
    Get paginated deliverables.
    
    Returns:
        Tuple of (DataFrame, total_count)
    """
    conn = get_connection()
    
    try:
        where_clauses = ["project_ref=?", "deleted_at IS NULL"]  # Task 9
        params = [project]
        
        if discipline != "All":
            where_clauses.append("discipline=?")
            params.append(discipline)
        
        if station != "All":
            where_clauses.append("station=?")
            params.append(station)
        
        if search:
            where_clauses.append("name LIKE ?")
            params.append(f"%{search}%")
        
        sql_cond = " WHERE " + " AND ".join(where_clauses)
        
        # Get total count
        total_count = conn.execute(
            f"SELECT COUNT(*) FROM deliverables{sql_cond}", params
        ).fetchone()[0]
        
        # Get paginated data
        offset = (page - 1) * page_size
        query = f"""
            SELECT id, station, discipline, type, name, 
                   planned_start_date, planned_finish_date, status
            FROM deliverables
            {sql_cond}
            ORDER BY id
            LIMIT ? OFFSET ?
        """
        
        df = pd.read_sql(query, conn, params=params + [page_size, offset])
        return df, total_count
    
    finally:
        conn.close()


# =============================================================================
# CALENDAR & ALERTS
# =============================================================================

def get_calendar_events_raw(
    project: str,
    discipline: str = "All",
) -> pd.DataFrame:
    """
    Get all calendar events for a project.
    
    Returns:
        DataFrame with: date, type ('task' or 'deliv')
    """
    conn = get_connection()
    
    try:
        # Task 9: Added deleted_at IS NULL filters
        where_deliv = ["project_ref=?", "deleted_at IS NULL"]
        params_deliv = [project]
        
        where_task = ["t.project_ref=?", "t.deleted_at IS NULL", "d.deleted_at IS NULL"]
        params_task = [project]
        
        if discipline != "All":
            where_deliv.append("discipline=?")
            params_deliv.append(discipline)
            where_task.append("d.discipline=?")
            params_task.append(discipline)
        
        sql_deliv = " WHERE " + " AND ".join(where_deliv)
        sql_task = " WHERE " + " AND ".join(where_task)
        
        query = f"""
            SELECT planned_finish_date as date, 'deliv' as type
            FROM deliverables
            {sql_deliv}
            UNION ALL
            SELECT t.due_date as date, 'task' as type
            FROM tasks t
            JOIN deliverables d ON t.deliverable_id = d.id
            {sql_task}
        """
        
        df = pd.read_sql(query, conn, params=params_deliv + params_task)
        return df
    
    finally:
        conn.close()


def get_alerts_raw(
    project: str,
    discipline: str = "All",
) -> pd.DataFrame:
    """
    Get upcoming deadlines (next 7 days).
    
    Returns:
        DataFrame with: type, name, date, info
    """
    conn = get_connection()
    
    try:
        today = str(date.today())
        next_week = str(date.today() + timedelta(days=7))
        
        # Task 9: Added deleted_at IS NULL filters
        where_deliv = ["project_ref=?", "planned_finish_date BETWEEN ? AND ?", "deleted_at IS NULL"]
        params_deliv = [project, today, next_week]
        
        where_task = ["t.project_ref=?", "t.due_date BETWEEN ? AND ?", "t.deleted_at IS NULL", "d.deleted_at IS NULL"]
        params_task = [project, today, next_week]
        
        if discipline != "All":
            where_deliv.append("discipline=?")
            params_deliv.append(discipline)
            where_task.append("d.discipline=?")
            params_task.append(discipline)
        
        sql_deliv = " WHERE " + " AND ".join(where_deliv)
        sql_task = " WHERE " + " AND ".join(where_task)
        
        query = f"""
            SELECT 'Task' as type, t.name, t.due_date as date, t.priority as info
            FROM tasks t
            JOIN deliverables d ON t.deliverable_id = d.id
            {sql_task}
            UNION ALL
            SELECT 'Deliverable' as type, name, planned_finish_date as date, discipline as info
            FROM deliverables
            {sql_deliv}
            ORDER BY date
        """
        
        df = pd.read_sql(query, conn, params=params_task + params_deliv)
        return df
    
    finally:
        conn.close()


# =============================================================================
# TASKS DATA
# =============================================================================

def get_tasks_raw(
    project: str,
    user_id: int,
    role: str,
    discipline: str = "All",
    station: str = "All",
) -> pd.DataFrame:
    """
    Get tasks for display.
    
    Args:
        project: Project name
        user_id: Current user ID
        role: User role (Manager, Lead, Engineer)
        discipline: Discipline filter
        station: Station filter
    
    Returns:
        DataFrame with task details
    """
    conn = get_connection()
    
    try:
        # Task 9: Added deleted_at IS NULL filters
        where_clauses = ["t.project_ref=?", "t.deleted_at IS NULL", "d.deleted_at IS NULL"]
        params = [project]
        
        if discipline != "All":
            where_clauses.append("d.discipline=?")
            params.append(discipline)
        
        if station != "All":
            where_clauses.append("t.station=?")
            params.append(station)
        
        # Non-managers only see their own tasks
        if role != "Manager":
            where_clauses.append("t.assigned_engineer_id=?")
            params.append(user_id)
        
        sql_cond = " WHERE " + " AND ".join(where_clauses)
        
        query = f"""
            SELECT t.id, t.name, t.progress, t.priority, t.status, t.due_date,
                   u.full_name, d.discipline, t.station
            FROM tasks t
            JOIN users u ON t.assigned_engineer_id = u.id
            JOIN deliverables d ON t.deliverable_id = d.id
            {sql_cond}
            ORDER BY t.due_date
        """
        
        df = pd.read_sql(query, conn, params=params)
        return df
    
    finally:
        conn.close()


def get_tasks_slider_raw(
    project: str,
    user_id: int,
    role: str,
    discipline: str = "All",
) -> pd.DataFrame:
    """
    Get tasks for progress slider display.
    
    Returns:
        DataFrame with: id, name, full_name, progress
    """
    conn = get_connection()
    
    try:
        # Task 9: Added deleted_at IS NULL filters
        where_clauses = ["t.project_ref=?", "t.deleted_at IS NULL", "d.deleted_at IS NULL"]
        params = [project]
        
        if discipline != "All":
            where_clauses.append("d.discipline=?")
            params.append(discipline)
        
        # Non-managers only see their own tasks
        if role != "Manager":
            where_clauses.append("t.assigned_engineer_id=?")
            params.append(user_id)
        
        sql_cond = " WHERE " + " AND ".join(where_clauses)
        
        query = f"""
            SELECT t.id, t.name, u.full_name, t.progress
            FROM tasks t
            JOIN users u ON t.assigned_engineer_id = u.id
            JOIN deliverables d ON t.deliverable_id = d.id
            {sql_cond}
            ORDER BY t.due_date
        """
        
        df = pd.read_sql(query, conn, params=params)
        return df
    
    finally:
        conn.close()


def update_task_progress_raw(task_id: int, progress: int) -> bool:
    """
    Update task progress.
    
    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    
    try:
        conn.execute(
            "UPDATE tasks SET progress = ? WHERE id = ?",
            (progress, task_id)
        )
        conn.commit()
        return True
    
    except Exception:
        return False
    
    finally:
        conn.close()


# =============================================================================
# DATA MANAGEMENT (HARD DELETE - for MDL re-import)
# =============================================================================

def delete_project_data_raw(project: str) -> bool:
    """
    Delete all data for a project (HARD DELETE for MDL re-import).
    Note: This remains a hard delete as per requirements.
    
    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    
    try:
        conn.execute("DELETE FROM deliverables WHERE project_ref=?", (project,))
        conn.execute("DELETE FROM tasks WHERE project_ref=?", (project,))
        conn.commit()
        return True
    
    except Exception:
        return False
    
    finally:
        conn.close()


# =============================================================================
# Task 9: SOFT DELETE FUNCTIONS
# =============================================================================

def soft_delete_deliverable(deliverable_id: int) -> bool:
    """
    Soft delete a deliverable by setting deleted_at = now().
    
    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    
    try:
        conn.execute(
            "UPDATE deliverables SET deleted_at = datetime('now') WHERE id=?",
            (deliverable_id,)
        )
        conn.commit()
        return True
    
    except Exception:
        return False
    
    finally:
        conn.close()


def soft_delete_task(task_id: int) -> bool:
    """
    Soft delete a task by setting deleted_at = now().
    
    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    
    try:
        conn.execute(
            "UPDATE tasks SET deleted_at = datetime('now') WHERE id=?",
            (task_id,)
        )
        conn.commit()
        return True
    
    except Exception:
        return False
    
    finally:
        conn.close()


def restore_deliverable(deliverable_id: int) -> bool:
    """
    Restore a soft-deleted deliverable by setting deleted_at = NULL.
    
    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    
    try:
        conn.execute(
            "UPDATE deliverables SET deleted_at = NULL WHERE id=?",
            (deliverable_id,)
        )
        conn.commit()
        return True
    
    except Exception:
        return False
    
    finally:
        conn.close()


def restore_task(task_id: int) -> bool:
    """
    Restore a soft-deleted task by setting deleted_at = NULL.
    
    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    
    try:
        conn.execute(
            "UPDATE tasks SET deleted_at = NULL WHERE id=?",
            (task_id,)
        )
        conn.commit()
        return True
    
    except Exception:
        return False
    
    finally:
        conn.close()


# =============================================================================
# Task 9: GET DELETED ITEMS (for recycle bin)
# =============================================================================

def get_deleted_deliverables(project: str) -> pd.DataFrame:
    """
    Return soft-deleted deliverables for a project.
    
    Returns:
        DataFrame with: id, name, station, discipline, deleted_at
        Ordered by deleted_at DESC (newest first).
    """
    conn = get_connection()
    
    try:
        query = """
            SELECT id, name, station, discipline, deleted_at
            FROM deliverables
            WHERE project_ref=? AND deleted_at IS NOT NULL
            ORDER BY deleted_at DESC
        """
        
        df = pd.read_sql(query, conn, params=[project])
        return df
    
    finally:
        conn.close()


def get_deleted_tasks(project: str) -> pd.DataFrame:
    """
    Return soft-deleted tasks for a project.
    
    Returns:
        DataFrame with: id, name, full_name (assigned engineer), deleted_at
        Ordered by deleted_at DESC.
    """
    conn = get_connection()
    
    try:
        query = """
            SELECT t.id, t.name, u.full_name, t.deleted_at
            FROM tasks t
            JOIN users u ON t.assigned_engineer_id = u.id
            WHERE t.project_ref=? AND t.deleted_at IS NOT NULL
            ORDER BY t.deleted_at DESC
        """
        
        df = pd.read_sql(query, conn, params=[project])
        return df
    
    finally:
        conn.close()
