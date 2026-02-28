# =============================================================================
# tabs/tasks_tab.py - Tasks Tab
# Extracted from main_app.py - Tasks section
# =============================================================================

import streamlit as st
import sqlite3
from datetime import date
from typing import List

from cache_manager import (
    get_tasks_cached,
    get_tasks_slider_cached,
    update_task_progress_with_invalidation,
    get_cache_version,
    invalidate_project_cache,
)
from config import PRIORITIES, TASK_STATUSES


def render_tasks_tab(
    conn: sqlite3.Connection,
    session: object,
    sel_st: str,
    sel_di: str,
    search: str,
    sql_cond: str,
    task_sql_cond: str,
    base_params: List,
    task_params: List,
) -> None:
    """
    Render the Tasks tab: task list, progress sliders, and task creation.

    Args:
        conn:           SQLite connection
        session:        st.session_state
        sel_st:         Selected station filter
        sel_di:         Selected discipline filter
        search:         Search string
        sql_cond:       WHERE clause for deliverables queries
        task_sql_cond:  WHERE clause for tasks queries
        base_params:    Parameters for deliverables queries
        task_params:    Parameters for tasks queries
    """
    project_name = session.selected_project
    user_info = session.user_info
    cache_ver = get_cache_version()

    st.markdown("### ✅ Tasks")

    # ── Task List ─────────────────────────────────────────────────────────────
    df_tasks = get_tasks_cached(
        project_name,
        user_info["id"],
        user_info["role"],
        sel_di,
        cache_ver,
        sel_st,
    )

    if df_tasks.empty:
        st.info("No tasks found for the selected filters.")
    else:
        # Column display config
        display_cols = [
            c for c in [
                "name", "full_name", "discipline", "station",
                "priority", "status", "due_date", "progress",
            ]
            if c in df_tasks.columns
        ]
        st.dataframe(df_tasks[display_cols], use_container_width=True, height=350)

    # ── Progress Sliders ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔄 Update Progress")

    df_slider = get_tasks_slider_cached(
        project_name,
        user_info["id"],
        user_info["role"],
        sel_di,
        cache_ver,
    )

    if not df_slider.empty:
        for _, row in df_slider.iterrows():
            task_id = int(row["id"])
            task_name = row.get("name", f"Task {task_id}")
            assignee = row.get("full_name", "")
            current_progress = int(row.get("progress", 0))

            label = f"{task_name} ({assignee})" if assignee else task_name
            new_val = st.slider(
                label,
                min_value=0,
                max_value=100,
                value=current_progress,
                step=5,
                key=f"slider_{task_id}",
            )

            if new_val != current_progress:
                if update_task_progress_with_invalidation(task_id, new_val):
                    st.success(f"Updated '{task_name}' → {new_val}%")
                    st.rerun()
                else:
                    st.error(f"Failed to update '{task_name}'")

    # ── Create Task (Manager / Lead only) ─────────────────────────────────────
    if user_info["role"] in ("Manager", "Lead"):
        st.markdown("---")
        st.markdown("### ➕ Create New Task")

        with st.form("create_task"):
            t_name = st.text_input("Task Name")
            t_desc = st.text_area("Description", height=80)

            col1, col2 = st.columns(2)
            with col1:
                t_priority = st.selectbox("Priority", PRIORITIES)
                t_due = st.date_input("Due Date", value=date.today())
            with col2:
                # Fetch engineers for assignment
                try:
                    engineers = conn.execute(
                        "SELECT id, full_name FROM users WHERE role != 'Manager'"
                    ).fetchall()
                    eng_options = {row[1]: row[0] for row in engineers}
                except Exception:
                    eng_options = {}

                assigned_name = st.selectbox(
                    "Assign To",
                    list(eng_options.keys()) if eng_options else ["(no engineers)"],
                )

                # Fetch deliverables for linking
                try:
                    delivs = conn.execute(
                        f"SELECT id, name FROM deliverables{sql_cond}",
                        base_params,
                    ).fetchall()
                    deliv_options = {row[1]: row[0] for row in delivs}
                except Exception:
                    deliv_options = {}

                linked_deliv = st.selectbox(
                    "Link to Deliverable",
                    list(deliv_options.keys()) if deliv_options else ["(none)"],
                )

            if st.form_submit_button("Create Task", use_container_width=True):
                if not t_name:
                    st.error("Task name is required.")
                elif not eng_options:
                    st.error("No engineers to assign the task to.")
                else:
                    try:
                        assigned_id = eng_options.get(assigned_name)
                        deliv_id = deliv_options.get(linked_deliv)

                        conn.execute(
                            """INSERT INTO tasks
                               (project_ref, station, deliverable_id, name,
                                assigned_engineer_id, priority, due_date,
                                description, progress, status)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'Not Started')""",
                            (
                                project_name,
                                sel_st if sel_st != "All" else "",
                                deliv_id,
                                t_name,
                                assigned_id,
                                t_priority,
                                str(t_due),
                                t_desc,
                            ),
                        )
                        conn.commit()
                        # Invalidate cache after insert
                        invalidate_project_cache()

                        st.success(f"Task '{t_name}' created.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Failed to create task: {e}")
