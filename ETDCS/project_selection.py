# =============================================================================
# pages/project_selection.py - Project Selection Page
# Extracted from main_app.py lines 198-210
# =============================================================================

import streamlit as st
from config import PROJECTS


def render_project_selection() -> None:
    """
    Display project selection cards.
    Sets st.session_state.selected_project on button click.
    """
    st.markdown(
        "<div style='text-align:center;'><h1>🌍 Projects Portfolio</h1></div>",
        unsafe_allow_html=True
    )
    
    # Create 2 columns for project cards
    col_p1, col_p2 = st.columns(2)
    
    projects_list = list(PROJECTS.items())
    
    with col_p1:
        for proj_name, proj_info in projects_list[:2]:
            st.markdown(
                f"<div class='project-select-card'><h1>{proj_info.get('icon', '📁')}</h1><h2>{proj_name}</h2></div>",
                unsafe_allow_html=True
            )
            if st.button(f"🚀 Access {proj_name[:10]}", use_container_width=True, key=f"proj_{proj_name}"):
                st.session_state.selected_project = proj_name
                st.rerun()
    
    with col_p2:
        for proj_name, proj_info in projects_list[2:4]:
            st.markdown(
                f"<div class='project-select-card'><h1>{proj_info.get('icon', '📁')}</h1><h2>{proj_name}</h2></div>",
                unsafe_allow_html=True
            )
            if st.button(f"🚀 Access {proj_name[:10]}", use_container_width=True, key=f"proj_{proj_name}"):
                st.session_state.selected_project = proj_name
                st.rerun()
