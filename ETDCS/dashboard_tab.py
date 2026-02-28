# =============================================================================
# tabs/dashboard_tab.py - Dashboard Tab
# Extracted from main_app.py - Dashboard section
# =============================================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from typing import List

from cache_manager import (
    get_statistics_cached,
    get_timeline_data_cached,
    get_deliverables_cached,
    get_cache_version,
    invalidate_project_cache,
    delete_project_data_with_invalidation,
)
from secure_file_upload import save_uploaded_file_secure


def render_dashboard_tab(
    conn: sqlite3.Connection,
    session: object,
    sel_st: str,
    sel_di: str,
    search: str,
    sql_cond: str,
    base_params: List,
) -> None:
    """
    Render the Dashboard tab: KPI metrics, timeline chart, and MDL upload.

    Args:
        conn:        SQLite connection (kept for compatibility; DB functions open own connections)
        session:     st.session_state
        sel_st:      Selected station filter
        sel_di:      Selected discipline filter
        search:      Search string
        sql_cond:    WHERE clause for deliverables queries
        base_params: Parameters matching sql_cond
    """
    project_name = session.selected_project
    cache_ver = get_cache_version()

    # ── KPI Metrics ──────────────────────────────────────────────────────────
    stats = get_statistics_cached(project_name, sel_di, cache_ver, sel_st)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        f"<div class='metric-card'><h3>📦 Deliverables</h3><h1>{stats['total_deliverables']}</h1></div>",
        unsafe_allow_html=True,
    )
    c2.markdown(
        f"<div class='metric-card'><h3>✅ Tasks</h3><h1>{stats['total_tasks']}</h1></div>",
        unsafe_allow_html=True,
    )
    c3.markdown(
        f"<div class='metric-card'><h3>🔴 Overdue</h3><h1>{stats['overdue_tasks']}</h1></div>",
        unsafe_allow_html=True,
    )
    c4.markdown(
        f"<div class='metric-card'><h3>📊 Avg Progress</h3><h1>{stats['avg_progress']}%</h1></div>",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Timeline Chart ────────────────────────────────────────────────────────
    df_timeline = get_timeline_data_cached(project_name, sel_di, cache_ver, sel_st)

    if not df_timeline.empty:
        st.markdown("### 📅 Deliverables Timeline")
        fig = px.timeline(
            df_timeline,
            x_start="planned_start_date",
            x_end="planned_finish_date",
            y="name",
            color="discipline",
            title="Project Timeline",
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

    # ── Discipline Distribution ───────────────────────────────────────────────
    df_all = get_deliverables_cached(project_name, sel_di, cache_ver, sel_st, search)

    if not df_all.empty and "discipline" in df_all.columns:
        st.markdown("### 🎯 Discipline Distribution")
        disc_counts = df_all["discipline"].value_counts().reset_index()
        disc_counts.columns = ["Discipline", "Count"]
        fig2 = px.pie(disc_counts, names="Discipline", values="Count")
        st.plotly_chart(fig2, use_container_width=True)

    # ── MDL Upload (Manager / Lead only) ─────────────────────────────────────
    if session.user_info["role"] in ("Manager", "Lead"):
        st.markdown("---")
        st.markdown("### 📤 Upload MDL (CSV)")

        uploaded = st.file_uploader("Upload MDL CSV", type=["csv"])
        if uploaded:
            col_up, col_del = st.columns([2, 1])

            with col_up:
                if st.button("⬆️ Import MDL", use_container_width=True):
                    _import_mdl(uploaded, project_name, conn)

            with col_del:
                if st.button("🗑️ Clear Project Data", use_container_width=True):
                    if delete_project_data_with_invalidation(project_name):
                        st.success("Project data cleared.")
                        st.rerun()
                    else:
                        st.error("Failed to clear data.")


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _import_mdl(uploaded_file, project_name: str, conn: sqlite3.Connection) -> None:
    """Read CSV and insert rows into deliverables table."""
    try:
        file_path, error = save_uploaded_file_secure(uploaded_file)
        if error:
            st.error(f"Upload rejected: {error}")
            return

        df = pd.read_csv(file_path)

        # Normalize column names
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        required = {"station", "discipline", "name"}
        if not required.issubset(set(df.columns)):
            st.error(f"CSV missing required columns. Need: {required}")
            return

        inserted = 0
        for _, row in df.iterrows():
            conn.execute(
                """INSERT INTO deliverables
                   (project_ref, station, discipline, type, name,
                    planned_start_date, planned_finish_date, status, mdl_synced)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    project_name,
                    row.get("station", ""),
                    row.get("discipline", ""),
                    row.get("type", "Drawing"),
                    row.get("name", ""),
                    row.get("planned_start_date", None),
                    row.get("planned_finish_date", None),
                    row.get("status", "Planned"),
                ),
            )
            inserted += 1

        conn.commit()
        invalidate_project_cache()
        st.success(f"✅ Imported {inserted} deliverables.")
        st.rerun()

    except Exception as e:
        st.error(f"Import failed: {e}")
