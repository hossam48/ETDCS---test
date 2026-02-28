# =============================================================================
# cache_manager.py - Streamlit Caching Layer
# =============================================================================
# Wraps database_manager functions with st.cache_data for performance.
# TTL: deliverables=10min, tasks=5min, stats=2min
#
# Updated: Task 9 — Added soft delete functions with cache invalidation
# =============================================================================

import streamlit as st
import pandas as pd
from typing import Tuple, Dict, Any

import database_manager as db

# =============================================================================
# CACHE VERSION (for manual invalidation)
# =============================================================================

def get_cache_version() -> int:
    """Get current cache version from session state."""
    return st.session_state.get("cache_version", 1)


def invalidate_project_cache() -> None:
    """Increment cache version to invalidate all cached data."""
    current = st.session_state.get("cache_version", 1)
    st.session_state["cache_version"] = current + 1


# =============================================================================
# STATISTICS (TTL: 2 minutes)
# =============================================================================

@st.cache_data(ttl=120, show_spinner=False)
def get_statistics_cached(
    project: str,
    discipline: str,
    cache_ver: int,  # Used for invalidation
    station: str = "All",
) -> Dict[str, Any]:
    """
    Cached wrapper for get_statistics_raw.
    TTL: 2 minutes
    """
    return db.get_statistics_raw(project, discipline, station)


# =============================================================================
# TIMELINE DATA (TTL: 10 minutes)
# =============================================================================

@st.cache_data(ttl=600, show_spinner=False)
def get_timeline_data_cached(
    project: str,
    discipline: str,
    cache_ver: int,
    station: str = "All",
) -> pd.DataFrame:
    """
    Cached wrapper for get_timeline_data_raw.
    TTL: 10 minutes
    """
    return db.get_timeline_data_raw(project, discipline, station)


# =============================================================================
# DELIVERABLES DATA (TTL: 10 minutes)
# =============================================================================

@st.cache_data(ttl=600, show_spinner=False)
def get_deliverables_cached(
    project: str,
    discipline: str,
    cache_ver: int,
    station: str = "All",
    search: str = "",
) -> pd.DataFrame:
    """
    Cached wrapper for get_deliverables_raw.
    TTL: 10 minutes
    """
    return db.get_deliverables_raw(project, discipline, station, search)


@st.cache_data(ttl=600, show_spinner=False)
def get_deliverables_paginated_cached(
    project: str,
    discipline: str,
    cache_ver: int,
    station: str = "All",
    search: str = "",
    page: int = 1,
    page_size: int = 50,
) -> Tuple[pd.DataFrame, int]:
    """
    Cached wrapper for get_deliverables_paginated_raw.
    TTL: 10 minutes
    """
    return db.get_deliverables_paginated_raw(
        project, discipline, station, search, page, page_size
    )


# =============================================================================
# CALENDAR & ALERTS (TTL: 5 minutes)
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_calendar_events_cached(
    project: str,
    discipline: str,
    cache_ver: int,
) -> pd.DataFrame:
    """
    Cached wrapper for get_calendar_events_raw.
    TTL: 5 minutes
    """
    return db.get_calendar_events_raw(project, discipline)


@st.cache_data(ttl=300, show_spinner=False)
def get_alerts_cached(
    project: str,
    discipline: str,
    cache_ver: int,
) -> pd.DataFrame:
    """
    Cached wrapper for get_alerts_raw.
    TTL: 5 minutes
    """
    return db.get_alerts_raw(project, discipline)


# =============================================================================
# TASKS DATA (TTL: 5 minutes)
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_tasks_cached(
    project: str,
    user_id: int,
    role: str,
    discipline: str,
    cache_ver: int,
    station: str = "All",
) -> pd.DataFrame:
    """
    Cached wrapper for get_tasks_raw.
    TTL: 5 minutes
    """
    return db.get_tasks_raw(project, user_id, role, discipline, station)


@st.cache_data(ttl=300, show_spinner=False)
def get_tasks_slider_cached(
    project: str,
    user_id: int,
    role: str,
    discipline: str,
    cache_ver: int,
) -> pd.DataFrame:
    """
    Cached wrapper for get_tasks_slider_raw.
    TTL: 5 minutes
    """
    return db.get_tasks_slider_raw(project, user_id, role, discipline)


# =============================================================================
# WRITE OPERATIONS (with cache invalidation)
# =============================================================================

def update_task_progress_with_invalidation(task_id: int, progress: int) -> bool:
    """
    Update task progress and invalidate relevant caches.
    
    Returns:
        True if successful, False otherwise
    """
    result = db.update_task_progress_raw(task_id, progress)
    if result:
        invalidate_project_cache()
    return result


def delete_project_data_with_invalidation(project: str) -> bool:
    """
    Delete all project data and invalidate caches.
    
    Returns:
        True if successful, False otherwise
    """
    result = db.delete_project_data_raw(project)
    if result:
        invalidate_project_cache()
    return result


# =============================================================================
# Task 9: SOFT DELETE OPERATIONS (with cache invalidation)
# =============================================================================

def soft_delete_deliverable_with_invalidation(deliverable_id: int) -> bool:
    """
    Soft delete deliverable and invalidate cache.
    
    Returns:
        True if successful, False otherwise
    """
    result = db.soft_delete_deliverable(deliverable_id)
    if result:
        invalidate_project_cache()
    return result


def soft_delete_task_with_invalidation(task_id: int) -> bool:
    """
    Soft delete task and invalidate cache.
    
    Returns:
        True if successful, False otherwise
    """
    result = db.soft_delete_task(task_id)
    if result:
        invalidate_project_cache()
    return result


def restore_deliverable_with_invalidation(deliverable_id: int) -> bool:
    """
    Restore deliverable and invalidate cache.
    
    Returns:
        True if successful, False otherwise
    """
    result = db.restore_deliverable(deliverable_id)
    if result:
        invalidate_project_cache()
    return result


def restore_task_with_invalidation(task_id: int) -> bool:
    """
    Restore task and invalidate cache.
    
    Returns:
        True if successful, False otherwise
    """
    result = db.restore_task(task_id)
    if result:
        invalidate_project_cache()
    return result


# =============================================================================
# Task 9: DELETED ITEMS (for recycle bin)
# =============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def get_deleted_deliverables_cached(
    project: str,
    cache_ver: int,
) -> pd.DataFrame:
    """
    Cached wrapper for get_deleted_deliverables.
    TTL: 1 minute (shorter, as deleted items change less frequently)
    """
    return db.get_deleted_deliverables(project)


@st.cache_data(ttl=60, show_spinner=False)
def get_deleted_tasks_cached(
    project: str,
    cache_ver: int,
) -> pd.DataFrame:
    """
    Cached wrapper for get_deleted_tasks.
    TTL: 1 minute
    """
    return db.get_deleted_tasks(project)
