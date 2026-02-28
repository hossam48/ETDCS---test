# =============================================================================
# main_app.py - Application Entry Point & Routing
# Version: 9.0 - Modular Architecture
# Lines: 71 (target: <80)
# =============================================================================

import streamlit as st

# --- Page Configuration (MUST be first Streamlit call) ---
st.set_page_config(page_title="Elsewedy Projects Portfolio", page_icon="🏗️", layout="wide")

# --- Import and Initialize ---
from components.styles import inject_styles
from database.db_init import get_db_connection

inject_styles()

# --- Session State Initialization ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None
if 'selected_project' not in st.session_state:
    st.session_state.selected_project = None
if 'show_team_mgmt' not in st.session_state:
    st.session_state.show_team_mgmt = False

# --- Import Renderers (after session state init) ---
from login.login_page import render_login_page
from pages.project_selection import render_project_selection
from pages.team_management import render_team_management
from components.sidebar import render_sidebar
from components.filters import render_project_filters
from tabs.dashboard_tab import render_dashboard_tab
from tabs.calendar_tab import render_calendar_tab
from tabs.mdl_tab import render_mdl_tab
from tabs.tasks_tab import render_tasks_tab

# =============================================================================
# MAIN ROUTING
# =============================================================================

if not st.session_state.logged_in:
    # --- Login Page ---
    conn = get_db_connection()
    render_login_page(conn)
    conn.close()

else:
    # --- Sidebar (always visible when logged in) ---
    render_sidebar()
    
    # --- Route to appropriate page ---
    if st.session_state.show_team_mgmt:
        render_team_management(get_db_connection)
    
    elif st.session_state.selected_project is None:
        render_project_selection()
    
    else:
        # --- Project Dashboard (4 tabs with shared filters) ---
        conn = get_db_connection()
        sel_st, sel_di, search, sql_cond, task_sql_cond, base_params, task_params = render_project_filters(
            conn, st.session_state.selected_project
        )
        
        t1, t2, t3, t4 = st.tabs(["Dashboard", "📅 Calendar & Alerts", "MDL", "Tasks"])
        with t1: render_dashboard_tab(conn, st.session_state, sel_st, sel_di, search, sql_cond, base_params)
        with t2: render_calendar_tab(conn, st.session_state, sel_st, sel_di, search, sql_cond, task_sql_cond, base_params, task_params)
        with t3: render_mdl_tab(conn, st.session_state, sel_st, sel_di, search, sql_cond, base_params)
        with t4: render_tasks_tab(conn, st.session_state, sel_st, sel_di, search, sql_cond, task_sql_cond, base_params, task_params)
        conn.close()
