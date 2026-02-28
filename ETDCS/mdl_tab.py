# =============================================================================
# tabs/mdl_tab.py - MDL (Master Document List) Tab
# Extracted from main_app.py - MDL section
# =============================================================================

import streamlit as st
import sqlite3
from typing import List

from cache_manager import (
    get_deliverables_paginated_cached,
    get_cache_version,
)


def render_mdl_tab(
    conn: sqlite3.Connection,
    session: object,
    sel_st: str,
    sel_di: str,
    search: str,
    sql_cond: str,
    base_params: List,
) -> None:
    """
    Render the MDL tab with paginated deliverables table.

    Args:
        conn:        SQLite connection (kept for compatibility)
        session:     st.session_state
        sel_st:      Selected station filter
        sel_di:      Selected discipline filter
        search:      Search string
        sql_cond:    WHERE clause for deliverables queries
        base_params: Parameters matching sql_cond
    """
    project_name = session.selected_project
    cache_ver = get_cache_version()

    st.markdown("### 📋 Master Document List")

    # ── Pagination Controls ──────────────────────────────────────────────────
    ctl1, ctl2 = st.columns([3, 1])
    with ctl2:
        page_size = st.selectbox("Rows per page", [25, 50, 100], index=1)

    # Reset page when filters change
    filter_key = f"{project_name}_{sel_st}_{sel_di}_{search}"
    if st.session_state.get("_mdl_filter_key") != filter_key:
        st.session_state["_mdl_filter_key"] = filter_key
        st.session_state["_mdl_page"] = 1

    page = st.session_state.get("_mdl_page", 1)

    # ── Fetch Data ───────────────────────────────────────────────────────────
    df, total_count = get_deliverables_paginated_cached(
        project_name, sel_di, cache_ver, sel_st, search, page, page_size
    )

    total_pages = max(1, (total_count + page_size - 1) // page_size)

    # ── Table ─────────────────────────────────────────────────────────────────
    with ctl1:
        st.caption(
            f"Showing {len(df)} of {total_count} deliverables "
            f"(Page {page} / {total_pages})"
        )

    if df.empty:
        st.info("No deliverables found for the selected filters.")
    else:
        display_cols = [
            c for c in ["station", "discipline", "name", "type", "status",
                         "planned_start_date", "planned_finish_date"]
            if c in df.columns
        ]
        st.dataframe(df[display_cols], use_container_width=True, height=500)

    # ── Pagination Buttons ───────────────────────────────────────────────────
    p1, p2, p3 = st.columns([1, 2, 1])
    with p1:
        if st.button("◀ Prev", disabled=page <= 1):
            st.session_state["_mdl_page"] = page - 1
            st.rerun()
    with p2:
        st.markdown(
            f"<p style='text-align:center; padding-top:8px;'>Page {page} of {total_pages}</p>",
            unsafe_allow_html=True,
        )
    with p3:
        if st.button("Next ▶", disabled=page >= total_pages):
            st.session_state["_mdl_page"] = page + 1
            st.rerun()
