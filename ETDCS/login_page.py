# =============================================================================
# login/login_page.py - Login Page Rendering
# Extracted from main_app.py lines 123-139
# =============================================================================

import streamlit as st
import sqlite3

from auth import authenticate_user
from rate_limiter import check_rate_limit, record_failed_attempt, record_success


def render_login_page(conn: sqlite3.Connection) -> None:
    """
    Render the login page with rate limiting protection.
    
    Uses authenticate_user() from auth.py which supports bcrypt
    and auto-migrates SHA-256 hashes.
    
    Args:
        conn: SQLite database connection
    """
    # Center the login form
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<div class='header-box'><h1>🏗️ ELSEWEDY PROJECTS</h1><p>V9.0 - Modular</p></div>",
            unsafe_allow_html=True
        )
        
        with st.form("login"):
            email = st.text_input("Email", "admin@elsewedy.com")
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Secure Login", use_container_width=True):
                # Rate limit check BEFORE authentication
                allowed, error_msg = check_rate_limit(email)
                if not allowed:
                    st.error(error_msg)
                    st.stop()
                
                # Use bcrypt-aware authenticate_user() from auth.py
                user = authenticate_user(email, password, conn)
                
                if user:
                    # Success - clear rate limit and set session
                    record_success(email)
                    st.session_state.logged_in = True
                    st.session_state.user_info = {
                        'id': user['id'],
                        'name': user['name'],
                        'role': user['role'],
                        'discipline': user['discipline']
                    }
                    st.rerun()
                else:
                    # Failed - record attempt and show remaining
                    attempts = record_failed_attempt(email)
                    remaining = 5 - attempts
                    if remaining > 0:
                        st.error(f"Invalid credentials. {remaining} attempt{'s' if remaining != 1 else ''} remaining.")
                    else:
                        st.error("Account locked. Try again in 15 minutes.")
