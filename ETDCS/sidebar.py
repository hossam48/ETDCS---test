# =============================================================================
# components/sidebar.py - Sidebar Component
# Extracted from main_app.py lines 141-161
# =============================================================================

import streamlit as st


def render_sidebar() -> None:
    """
    Render the application sidebar with user info and navigation.
    
    Sidebar contains:
    - User greeting and role
    - Navigation buttons (Projects Portfolio, Team & HR Hub)
    - Logout button
    """
    with st.sidebar:
        # User greeting
        st.markdown(f"### 👋 Hi, {st.session_state.user_info['name']}")
        st.caption(f"Role: {st.session_state.user_info['role']}")
        st.divider()
        
        # Navigation: Projects Portfolio
        if st.button("🏠 PROJECTS PORTFOLIO", use_container_width=True):
            st.session_state.show_team_mgmt = False
            st.session_state.selected_project = None
            st.rerun()
        
        # Navigation: Team & HR Hub (Manager only)
        if st.session_state.user_info['role'] == 'Manager':
            if st.button("👥 TEAM & HR HUB", use_container_width=True):
                st.session_state.show_team_mgmt = True
                st.session_state.selected_project = None
                st.rerun()
        
        st.divider()
        
        # Logout
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
