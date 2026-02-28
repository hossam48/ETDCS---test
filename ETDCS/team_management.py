# =============================================================================
# pages/team_management.py - Team Management Page
# Extracted from main_app.py lines 164-196
# =============================================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from typing import Callable
from auth import hash_password


def render_team_management(get_db_connection: Callable) -> None:
    """
    Render team management page with member management and performance tabs.
    Manager-only access.
    
    Args:
        get_db_connection: Callable that returns a database connection
    """
    st.markdown("<h1 style='text-align:center;'>👥 Team Management</h1>", unsafe_allow_html=True)
    
    # Back button
    if st.button("⬅️ Back to Projects"):
        st.session_state.show_team_mgmt = False
        st.rerun()
    
    # Tabs for member management
    hr_tab1, hr_tab2 = st.tabs(["📝 Members", "📈 Performance"])
    
    with hr_tab1:
        col_add, col_edit = st.columns([1, 2])
        
        with col_add:
            st.markdown("### ➕ Add Member")
            with st.form("add_user"):
                nm = st.text_input("Name")
                em = st.text_input("Email")
                pw = st.text_input("Password", type="password")
                rl = st.selectbox("Role", ["Engineer", "Manager"])
                ds = st.selectbox("Discipline", ["HVAC", "Plumbing", "Fire", "Elect", "Civil"])
                
                if st.form_submit_button("Create"):
                    try:
                        conn = get_db_connection()
                        conn.execute(
                            "INSERT INTO users (full_name, email, password, role, discipline, join_date) VALUES (?,?,?,?,?,DATE('now'))",
                            (nm, em, hash_password(pw), rl, ds)
                        )
                        conn.commit()
                        conn.close()
                        st.success("Added!")
                    except Exception:
                        st.error("Exists")
        
        with col_edit:
            conn = get_db_connection()
            st.dataframe(
                pd.read_sql("SELECT full_name, email, role, discipline FROM users", conn),
                use_container_width=True
            )
            conn.close()
    
    with hr_tab2:
        conn = get_db_connection()
        df = pd.read_sql(
            "SELECT u.full_name, count(t.id) as tasks, avg(t.progress) as prog "
            "FROM users u LEFT JOIN tasks t ON u.id=t.assigned_engineer_id "
            "GROUP BY u.full_name",
            conn
        ).fillna(0)
        conn.close()
        
        if not df.empty:
            st.plotly_chart(
                px.bar(df, x='full_name', y='prog', color='prog'),
                use_container_width=True
            )
