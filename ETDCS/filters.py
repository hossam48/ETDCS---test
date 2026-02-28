# =============================================================================
# components/filters.py - Project Filters Component
# Extracted from main_app.py lines 220-242
# =============================================================================

import streamlit as st
import pandas as pd
import sqlite3
from typing import Tuple, List


def render_project_filters(
    conn: sqlite3.Connection,
    project_name: str
) -> Tuple[str, str, str, str, str, List, List]:
    """
    Render project filter controls (Station, Discipline, Search).
    
    Returns filter values and pre-built SQL conditions for use in queries.
    
    Args:
        conn: SQLite database connection
        project_name: Current project reference
        
    Returns:
        Tuple of 7 values:
        - sel_st: Selected station filter value
        - sel_di: Selected discipline filter value
        - search: Search string
        - sql_cond: SQL WHERE clause for deliverables queries
        - task_sql_cond: SQL WHERE clause for tasks queries (with table aliases)
        - base_params: List of parameters for deliverables queries
        - task_params: List of parameters for tasks queries (copy of base_params)
    """
    # Get available stations for this project
    try:
        stations = pd.read_sql(
            "SELECT DISTINCT station FROM deliverables WHERE project_ref=?",
            conn,
            params=[project_name]
        )['station'].tolist()
        stations = [s for s in stations if s]
    except Exception:
        stations = []
    
    # Render filter widgets in columns
    c1, c2, c3 = st.columns([1, 1, 2])
    
    with c1:
        sel_st = st.selectbox("📍 Station:", ["All"] + stations)
    
    with c2:
        sel_di = st.selectbox("🎯 Discipline:", ["All", "HVAC", "Plumbing", "Fire"])
    
    with c3:
        search = st.text_input("🔍 Search")
    
    # Build SQL WHERE conditions for deliverables
    base_where = ["project_ref=?"]
    base_params = [project_name]
    
    if sel_st != "All":
        base_where.append("station=?")
        base_params.append(sel_st)
    
    if sel_di != "All":
        base_where.append("discipline=?")
        base_params.append(sel_di)
    
    if search:
        base_where.append("name LIKE ?")
        base_params.append(f"%{search}%")
    
    sql_cond = " WHERE " + " AND ".join(base_where)
    
    # Build SQL WHERE conditions for tasks (with table aliases for JOINs)
    task_where = []
    task_params = list(base_params)  # Copy params for task queries
    
    for cond in base_where:
        if 'discipline' in cond:
            task_where.append(f"d.{cond}")
        elif 'LIKE' in cond:
            task_where.append("t.name LIKE ?")
            # search param already in task_params (copied from base_params)
        else:
            task_where.append(f"t.{cond}")
    
    task_sql_cond = " WHERE " + " AND ".join(task_where)
    
    return sel_st, sel_di, search, sql_cond, task_sql_cond, base_params, task_params
