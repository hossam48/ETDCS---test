# =============================================================================
# components/styles.py - Global CSS Styles
# Extracted from main_app.py lines 12-53
# =============================================================================

import streamlit as st

CSS_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
* { font-family: 'Cairo', sans-serif; }
.main { background: #f8fafc; }
.header-box { background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 40px; border-radius: 20px; color: white; text-align: center; margin-bottom: 30px; }
.metric-card { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-bottom: 5px solid #667eea; text-align: center; }
.member-card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 15px; transition: 0.3s; }
.cal-table { width: 100%; border-collapse: separate; border-spacing: 5px; background: white; border-radius: 15px; padding: 10px; }
.cal-th { color: #64748b; font-weight: bold; text-align: center; padding: 10px; }
.cal-cell { height: 80px; width: 14%; vertical-align: top; border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px; font-size: 14px; color: #334155; position: relative; transition: 0.2s; }
.cal-cell:hover { background-color: #f1f5f9; border-color: #94a3b8; }
.cal-today { background-color: #eff6ff; border: 2px solid #3b82f6; }
.dot-container { display: flex; gap: 3px; flex-wrap: wrap; margin-top: 5px; }
.dot-task { width: 8px; height: 8px; background-color: #ef4444; border-radius: 50%; }
.dot-deliv { width: 8px; height: 8px; background-color: #3b82f6; border-radius: 50%; }
.critical-alert { background-color: #fef2f2; border-left: 5px solid #ef4444; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
</style>
"""

def inject_styles():
    """Inject global CSS styles into the Streamlit app."""
    st.markdown(CSS_STYLES, unsafe_allow_html=True)
