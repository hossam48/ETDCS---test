# =============================================================================
# tabs/calendar_tab.py - Calendar & Alerts Tab
# Extracted from main_app.py - Calendar section
# =============================================================================

import streamlit as st
import sqlite3
import calendar
from datetime import date, datetime
from typing import List

from cache_manager import (
    get_calendar_events_cached,
    get_alerts_cached,
    get_cache_version,
)


def render_calendar_tab(
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
    Render the Calendar & Alerts tab.

    Args:
        conn:           SQLite connection (kept for compatibility)
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
    cache_ver = get_cache_version()

    st.markdown("### 📅 Project Calendar")

    # ── Month Navigation ─────────────────────────────────────────────────────
    today = date.today()

    if "cal_year" not in st.session_state:
        st.session_state.cal_year = today.year
    if "cal_month" not in st.session_state:
        st.session_state.cal_month = today.month

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
        if st.button("◀ Prev"):
            if st.session_state.cal_month == 1:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
            st.rerun()
    with nav2:
        st.markdown(
            f"<h3 style='text-align:center'>"
            f"{calendar.month_name[st.session_state.cal_month]} {st.session_state.cal_year}"
            f"</h3>",
            unsafe_allow_html=True,
        )
    with nav3:
        if st.button("Next ▶"):
            if st.session_state.cal_month == 12:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
            st.rerun()

    # ── Load Events ──────────────────────────────────────────────────────────
    df_events = get_calendar_events_cached(project_name, sel_di, cache_ver)

    # Build set of dates with events: {date_str: ['task'|'deliv', ...]}
    event_map: dict = {}
    if not df_events.empty:
        for _, row in df_events.iterrows():
            d = str(row.get("date", ""))[:10]
            if d:
                event_map.setdefault(d, []).append(row.get("type", ""))

    # ── Render Calendar Grid ─────────────────────────────────────────────────
    year = st.session_state.cal_year
    month = st.session_state.cal_month
    _, num_days = calendar.monthrange(year, month)
    first_weekday = calendar.monthrange(year, month)[0]  # 0=Mon

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_html = "".join(
        f"<th class='cal-th'>{d}</th>" for d in day_names
    )

    cells = ["<td></td>"] * first_weekday
    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        is_today = date_str == str(today)
        cell_class = "cal-today" if is_today else "cal-cell"

        dots = ""
        if date_str in event_map:
            for ev_type in event_map[date_str]:
                dot_class = "dot-task" if ev_type == "task" else "dot-deliv"
                dots += f"<div class='{dot_class}'></div>"
        dots_html = f"<div class='dot-container'>{dots}</div>" if dots else ""

        cells.append(
            f"<td class='{cell_class}'><strong>{day}</strong>{dots_html}</td>"
        )

    # Pad end of last row
    while len(cells) % 7 != 0:
        cells.append("<td></td>")

    rows_html = ""
    for i in range(0, len(cells), 7):
        rows_html += "<tr>" + "".join(cells[i : i + 7]) + "</tr>"

    cal_html = f"""
    <table class='cal-table'>
        <tr>{header_html}</tr>
        {rows_html}
    </table>
    <p style='font-size:12px; color:#64748b; margin-top:8px;'>
        🔴 Task deadline &nbsp; 🔵 Deliverable deadline
    </p>
    """
    st.markdown(cal_html, unsafe_allow_html=True)

    # ── Alerts Section ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🚨 Upcoming Deadlines (Next 7 Days)")

    df_alerts = get_alerts_cached(project_name, sel_di, cache_ver)

    if df_alerts.empty:
        st.info("No upcoming deadlines in the next 7 days.")
    else:
        for _, row in df_alerts.iterrows():
            item_type = row.get("type", "")
            name = row.get("name", "")
            due = row.get("date", "")
            info = row.get("info", "")
            icon = "🔴" if item_type == "Task" else "🔵"
            st.markdown(
                f"<div class='critical-alert'>{icon} <strong>{item_type}:</strong> {name} "
                f"— Due: <strong>{due}</strong> ({info})</div>",
                unsafe_allow_html=True,
            )
