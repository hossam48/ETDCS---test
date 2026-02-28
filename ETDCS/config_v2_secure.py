"""
================================================================================
CONFIG.PY - Centralized Configuration for ETDCS Application
================================================================================
Purpose: Stores all configuration constants, CSS styles, and UI settings.
Why separate? Makes it easy to modify branding/colors without touching logic.
Author: Elsewedy PSP - MEP Design Team
Version: 9.0
================================================================================
"""

import os

# =============================================================================
# APPLICATION METADATA
# =============================================================================
APP_NAME = "Elsewedy Projects Portfolio"
APP_VERSION = "V9.0 - Modular Architecture"
APP_ICON = "🏗️"

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
# Database path - stored in 'database' folder for organization
DATABASE_DIR = "database"
DATABASE_FILE = "etdcs_v7.db"
DB_PATH = os.path.join(DATABASE_DIR, DATABASE_FILE)

# Files storage directory
FILES_DIR = "files"
UPLOADS_DIR = "uploads"

# =============================================================================
# FILE UPLOAD SECURITY SETTINGS
# =============================================================================
# Maximum file upload size in MB
MAX_UPLOAD_SIZE_MB = 50

# Allowed file extensions (enforced by secure_file_upload.py)
ALLOWED_FILE_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'xlsx', 'docx', 'xls', 'doc', 'csv', 'dwg']

# =============================================================================
# PROJECT DEFINITIONS
# =============================================================================
# Active EPC Projects - These are the main projects managed by the system
PROJECTS = {
    "Morjan Power Station": {
        "code": "MOR-2024",
        "location": "Egypt",
        "status": "Active",
        "icon": "⚡"
    },
    "Synchronous Condenser Building": {
        "code": "SYNC-2024",
        "location": "Egypt", 
        "status": "Active",
        "icon": "🏭"
    },
    "Nasiriyah 115/13.8kV Substation": {
        "code": "NAS-2024",
        "location": "Iraq",
        "status": "Active",
        "icon": "🔌"
    },
    "ALGHAT": {
        "code": "ALG-2024",
        "location": "Saudi Arabia",
        "status": "Planning",
        "icon": "🏗️"
    }
}

# =============================================================================
# USER ROLES & PERMISSIONS
# =============================================================================
ROLES = ["Manager", "Lead", "Engineer"]
DISCIPLINES = ["HVAC", "Plumbing", "Fire Fighting", "Electrical", "Architecture", "Civil", "All"]

# Role-based permissions (for future expansion)
ROLE_PERMISSIONS = {
    "Manager": {
        "can_view_all": True,
        "can_assign_tasks": True,
        "can_manage_users": True,
        "can_delete_data": True,
        "can_upload_mdl": True
    },
    "Lead": {
        "can_view_all": False,  # Only their discipline
        "can_assign_tasks": True,
        "can_manage_users": False,
        "can_delete_data": False,
        "can_upload_mdl": True
    },
    "Engineer": {
        "can_view_all": False,  # Only assigned tasks
        "can_assign_tasks": False,
        "can_manage_users": False,
        "can_delete_data": False,
        "can_upload_mdl": False
    }
}

# =============================================================================
# TASK PRIORITY LEVELS
# =============================================================================
PRIORITIES = ["High", "Medium", "Low"]

# =============================================================================
# DELIVERABLE STATUS OPTIONS
# =============================================================================
DELIVERABLE_STATUSES = ["Planned", "In Progress", "Under Review", "Approved", "On Hold", "Cancelled"]

# =============================================================================
# TASK STATUS OPTIONS  
# =============================================================================
TASK_STATUSES = ["Not Started", "In Progress", "Under Review", "Completed", "On Hold", "Cancelled"]

# =============================================================================
# DOCUMENT TYPES
# =============================================================================
DOCUMENT_TYPES = ["Drawing", "Specification", "Calculation", "Report", "MSA", "RFI", "RFC", "Other"]

# =============================================================================
# CSS STYLES - Corporate EPC Look
# =============================================================================
# This CSS is injected into Streamlit to create a professional appearance

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

/* Global Font Settings */
* { 
    font-family: 'Cairo', sans-serif; 
}

/* Main Background */
.main { 
    background: #f8fafc; 
}

/* Header Box - Used for main titles */
.header-box {
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    padding: 40px; 
    border-radius: 20px; 
    color: white;
    text-align: center; 
    margin-bottom: 30px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.1);
}

/* Metric Card - For KPI displays */
.metric-card {
    background: white; 
    padding: 20px; 
    border-radius: 15px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.05); 
    border-bottom: 5px solid #667eea;
    text-align: center;
    transition: transform 0.3s ease;
}

.metric-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
}

/* Member Card - Team management */
.member-card {
    background: white; 
    border: 1px solid #e2e8f0; 
    border-radius: 12px; 
    padding: 20px;
    margin-bottom: 15px; 
    transition: 0.3s;
}

.member-card:hover {
    border-color: #667eea;
    box-shadow: 0 5px 15px rgba(102,126,234,0.1);
}

/* Project Selection Card */
.project-select-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 30px; 
    border-radius: 20px; 
    color: white;
    text-align: center; 
    margin-bottom: 20px;
    cursor: pointer;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.project-select-card:hover {
    transform: scale(1.02);
    box-shadow: 0 15px 40px rgba(102,126,234,0.3);
}

/* Calendar Styles */
.cal-table { 
    width: 100%; 
    border-collapse: separate; 
    border-spacing: 5px; 
    background: white; 
    border-radius: 15px; 
    padding: 10px; 
}

.cal-th { 
    color: #64748b; 
    font-weight: bold; 
    text-align: center; 
    padding: 10px; 
}

.cal-cell { 
    height: 80px; 
    width: 14%; 
    vertical-align: top; 
    border: 1px solid #e2e8f0; 
    border-radius: 8px; 
    padding: 5px; 
    font-size: 14px; 
    color: #334155; 
    position: relative; 
    transition: 0.2s;
}

.cal-cell:hover { 
    background-color: #f1f5f9; 
    border-color: #94a3b8; 
}

.cal-today { 
    background-color: #eff6ff; 
    border: 2px solid #3b82f6; 
}

/* Dot Indicators for Calendar */
.dot-container { 
    display: flex; 
    gap: 3px; 
    flex-wrap: wrap; 
    margin-top: 5px; 
}

.dot-task { 
    width: 8px; 
    height: 8px; 
    background-color: #ef4444; 
    border-radius: 50%; 
} 

.dot-deliv { 
    width: 8px; 
    height: 8px; 
    background-color: #3b82f6; 
    border-radius: 50%; 
}

/* Critical Alert Box */
.critical-alert {
    background-color: #fef2f2; 
    border-left: 5px solid #ef4444; 
    padding: 15px; 
    border-radius: 8px; 
    margin-bottom: 20px;
}

/* Success Alert Box */
.success-alert {
    background-color: #f0fdf4; 
    border-left: 5px solid #22c55e; 
    padding: 15px; 
    border-radius: 8px; 
    margin-bottom: 20px;
}

/* Warning Alert Box */
.warning-alert {
    background-color: #fffbeb; 
    border-left: 5px solid #f59e0b; 
    padding: 15px; 
    border-radius: 8px; 
    margin-bottom: 20px;
}

/* Info Alert Box */
.info-alert {
    background-color: #eff6ff; 
    border-left: 5px solid #3b82f6; 
    padding: 15px; 
    border-radius: 8px; 
    margin-bottom: 20px;
}

/* Progress Bar Styling */
.progress-container {
    background: #e2e8f0;
    border-radius: 10px;
    overflow: hidden;
    height: 20px;
}

.progress-bar {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    height: 100%;
    transition: width 0.3s ease;
}

/* Status Badges */
.status-badge {
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
}

.status-planned { background: #e0e7ff; color: #3730a3; }
.status-progress { background: #fef3c7; color: #92400e; }
.status-review { background: #fce7f3; color: #9d174d; }
.status-approved { background: #d1fae5; color: #065f46; }
.status-hold { background: #fee2e2; color: #991b1b; }

/* Sidebar Styling */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e293b 0%, #334155 100%);
}

section[data-testid="stSidebar"] .element-container {
    color: white;
}

/* Button Styling */
.stButton button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 10px;
    transition: transform 0.2s ease;
}

.stButton button:hover {
    transform: scale(1.02);
}

/* Dataframe Styling */
.dataframe {
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 5px 15px rgba(0,0,0,0.05);
}
</style>
"""

# =============================================================================
# COLOR PALETTE - Consistent colors for charts and UI
# =============================================================================
COLORS = {
    "primary": "#667eea",
    "secondary": "#764ba2",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "info": "#3b82f6",
    "dark": "#1e293b",
    "light": "#f8fafc",
    "gray": "#64748b"
}

# Discipline colors for charts
DISCIPLINE_COLORS = {
    "HVAC": "#3b82f6",        # Blue
    "Plumbing": "#22c55e",    # Green
    "Fire Fighting": "#ef4444", # Red
    "Electrical": "#f59e0b",  # Amber
    "Architecture": "#8b5cf6", # Purple
    "Civil": "#6b7280",       # Gray
    "General": "#94a3b8"      # Slate
}

# Priority colors
PRIORITY_COLORS = {
    "High": "#ef4444",    # Red
    "Medium": "#f59e0b",  # Amber
    "Low": "#22c55e"      # Green
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def ensure_directories():
    """
    Create necessary directories if they don't exist.
    This ensures the app doesn't crash on first run.
    """
    directories = [DATABASE_DIR, FILES_DIR, UPLOADS_DIR]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Created directory: {directory}")


def get_project_info(project_name: str) -> dict:
    """
    Get project details by name.
    Returns a dict with code, location, status, and icon.
    """
    return PROJECTS.get(project_name, {
        "code": "N/A",
        "location": "Unknown",
        "status": "Unknown",
        "icon": "📁"
    })


def get_status_color(status: str) -> str:
    """
    Get the color associated with a status.
    Used for consistent coloring across the app.
    """
    status_colors = {
        "Planned": "#e0e7ff",
        "In Progress": "#fef3c7",
        "Under Review": "#fce7f3",
        "Approved": "#d1fae5",
        "On Hold": "#fee2e2",
        "Completed": "#d1fae5",
        "Cancelled": "#f1f5f9",
        "Not Started": "#e2e8f0"
    }
    return status_colors.get(status, "#f1f5f9")


# =============================================================================
# INITIALIZE ON IMPORT
# =============================================================================
ensure_directories()
