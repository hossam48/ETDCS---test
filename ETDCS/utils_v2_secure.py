"""
================================================================================
UTILS.PY - Utility Functions for ETDCS Application
================================================================================
Purpose: Contains helper functions for data processing, date handling, 
         file operations, and common calculations.
Why separate? Promotes code reuse and keeps main_app.py clean.
Author: Elsewedy PSP - MEP Design Team
Version: 10.1 - Fixed silent print in production (proper logging/warnings)
================================================================================
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
import re
import logging
import warnings
from typing import Optional, Union, List, Dict, Any

# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# SECURITY WARNING CLASS
# =============================================================================

class SecurityWarning(UserWarning):
    """Warning category for security-related issues."""
    pass


# =============================================================================
# DATE PARSING & HANDLING
# =============================================================================

def smart_date_parser(date_val: Any) -> Optional[date]:
    """
    Intelligently parse various date formats into a Python date object.
    
    This function handles multiple date formats commonly found in EPC project data:
    - ISO format: '2024-01-15'
    - European format: '15-01-2024'
    - Short format: '15-Jan-24'
    - Excel serial numbers
    - Dates with special characters (*, A suffixes from Primavera P6)
    
    Args:
        date_val: Input date (string, datetime, pandas Timestamp, or Excel serial)
        
    Returns:
        date object if parsing succeeds, None otherwise
        
    Example:
        >>> smart_date_parser("15-Jan-24")
        datetime.date(2024, 1, 15)
        >>> smart_date_parser("2024-01-15")
        datetime.date(2024, 1, 15)
    """
    # Handle None or empty values
    if date_val is None or pd.isna(date_val):
        return None
    
    # Handle empty strings
    if isinstance(date_val, str) and str(date_val).strip() == '':
        return None
    
    # If already a date or datetime object
    if isinstance(date_val, date) and not isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, datetime):
        return date_val.date()
    
    # Convert to string and clean
    s = str(date_val).strip().upper()
    
    # Remove Primavera P6 special characters
    # P6 sometimes adds '*' for critical path or 'A' for actual dates
    s = s.replace('*', '').replace('A', '')
    
    # Try common date formats
    date_formats = [
        '%Y-%m-%d',      # ISO: 2024-01-15
        '%d-%m-%Y',      # European: 15-01-2024
        '%d-%b-%y',      # Short: 15-Jan-24
        '%d-%B-%Y',      # Full: 15-January-2024
        '%m/%d/%Y',      # US: 01/15/2024
        '%d/%m/%Y',      # Another European: 15/01/2024
        '%Y/%m/%d',      # Asian: 2024/01/15
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    
    # Try pandas parser as fallback
    try:
        parsed = pd.to_datetime(s)
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        pass
    
    # Handle Excel serial date number
    try:
        if isinstance(date_val, (int, float)):
            # Excel serial date (days since 1899-12-30)
            excel_epoch = date(1899, 12, 30)
            return excel_epoch + timedelta(days=int(date_val))
    except Exception:
        pass
    
    return None


def format_date(dt: Optional[date], format_str: str = "%d-%b-%Y") -> str:
    """
    Format a date object into a string.
    
    Args:
        dt: Date object to format
        format_str: Output format (default: '15-Jan-2024')
        
    Returns:
        Formatted string or 'N/A' if date is None
    """
    if dt is None:
        return "N/A"
    return dt.strftime(format_str)


def get_date_range_days(start: date, end: date) -> int:
    """
    Calculate number of days between two dates.
    
    Args:
        start: Start date
        end: End date
        
    Returns:
        Number of days (positive if end > start)
    """
    return (end - start).days


def get_business_days(start: date, end: date) -> int:
    """
    Calculate number of business days (Mon-Fri) between dates.
    
    This is useful for EPC project scheduling where weekends
    are typically non-working days.
    
    Args:
        start: Start date
        end: End date
        
    Returns:
        Number of business days
    """
    if start > end:
        return 0
    
    # Count days excluding weekends
    business_days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            business_days += 1
        current += timedelta(days=1)
    
    return business_days


def get_week_dates(target_date: date) -> Dict[str, date]:
    """
    Get the start and end dates of the week containing target_date.
    
    Returns:
        Dict with 'start' (Monday) and 'end' (Sunday) dates
    """
    start = target_date - timedelta(days=target_date.weekday())
    end = start + timedelta(days=6)
    return {"start": start, "end": end}


def get_month_dates(target_date: date) -> Dict[str, date]:
    """
    Get the first and last dates of the month containing target_date.
    
    Returns:
        Dict with 'start' (1st) and 'end' (last day) of month
    """
    start = target_date.replace(day=1)
    # Get last day of month
    if target_date.month == 12:
        end = target_date.replace(day=31)
    else:
        next_month = target_date.replace(month=target_date.month + 1, day=1)
        end = next_month - timedelta(days=1)
    return {"start": start, "end": end}


# =============================================================================
# FILE OPERATIONS - SECURE UPLOAD (Delegated to secure_file_upload.py)
# =============================================================================
# Import secure file upload implementation
# This replaces the insecure save_uploaded_file() with content-validated version
try:
    from secure_file_upload import save_uploaded_file, save_uploaded_file_secure, validate_file, is_extension_allowed
    SECURE_UPLOAD_ENABLED = True
except ImportError:
    # Fallback to insecure method if secure module not available
    SECURE_UPLOAD_ENABLED = False
    
    # CRITICAL: Alert developers and operators about insecure fallback
    warnings.warn(
        "secure_file_upload.py not found — using INSECURE file upload fallback!",
        SecurityWarning,
        stacklevel=2
    )
    logger.critical(
        "INSECURE file upload fallback active — deploy secure_file_upload.py immediately"
    )
    
    def save_uploaded_file(uploaded_file, destination_dir: str = "files") -> Optional[str]:
        """
        Fallback insecure file save (use only when secure_file_upload.py unavailable).
        
        WARNING: This fallback does NOT validate file content. It only saves files
        based on extension. Deploy secure_file_upload.py for production use.
        
        Args:
            uploaded_file: Streamlit UploadedFile object
            destination_dir: Directory to save the file
            
        Returns:
            Full path to saved file, or None if save fails
        """
        try:
            if not os.path.exists(destination_dir):
                os.makedirs(destination_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{timestamp}_{uploaded_file.name}"
            file_path = os.path.join(destination_dir, file_name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            logger.warning("File saved using INSECURE fallback: %s", file_path)
            return file_path
        except Exception as e:
            logger.error("File save failed: %s", e)
            return None


def get_file_extension(filename: str) -> str:
    """
    Extract file extension from filename.
    
    Returns lowercase extension without the dot.
    """
    if '.' not in filename:
        return ""
    return filename.rsplit('.', 1)[1].lower()


def is_valid_file_type(filename: str, allowed_types: List[str]) -> bool:
    """
    Check if file has an allowed extension.
    
    Args:
        filename: Name of the file
        allowed_types: List of allowed extensions (without dots)
        
    Returns:
        True if file extension is in allowed list
    """
    ext = get_file_extension(filename)
    return ext.lower() in [t.lower().strip('.') for t in allowed_types]


def format_file_size(size_bytes: int) -> str:
    """
    Convert bytes to human-readable file size.
    
    Returns sizes like '1.5 MB', '250 KB', etc.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# =============================================================================
# DATA PROCESSING UTILITIES
# =============================================================================

def clean_string(text: Any) -> str:
    """
    Clean and normalize a string value.
    
    Removes extra whitespace, handles NaN values, and returns
    a clean string suitable for display or storage.
    """
    if text is None or pd.isna(text):
        return ""
    return str(text).strip()


def extract_discipline_from_name(name: str) -> str:
    """
    Infer the discipline from a deliverable or task name.
    
    This uses keyword matching common in EPC project naming conventions.
    
    Args:
        name: Deliverable or task name
        
    Returns:
        Detected discipline or 'General' if not detected
    """
    if not name:
        return "General"
    
    name_upper = name.upper()
    
    # Check for discipline keywords
    if 'HVAC' in name_upper or 'VENTILATION' in name_upper or 'AIR CONDITIONING' in name_upper:
        return "HVAC"
    elif 'FIRE' in name_upper or 'FIREFIGHTING' in name_upper or 'FIRE FIGHTING' in name_upper or 'FIRE-PROTECTION' in name_upper:
        return "Fire Fighting"
    elif 'PLUMB' in name_upper or 'DRAINAGE' in name_upper or 'WATER SUPPLY' in name_upper:
        return "Plumbing"
    elif 'ELECTR' in name_upper or 'POWER' in name_upper or 'LIGHTING' in name_upper or 'CABLE' in name_upper:
        return "Electrical"
    elif 'ARCHITECT' in name_upper or 'CIVIL' in name_upper or 'STRUCT' in name_upper or 'BUILDING' in name_upper:
        return "Architecture"
    
    return "General"


def calculate_progress_status(progress: int) -> Dict[str, Any]:
    """
    Calculate status information based on progress percentage.
    
    Args:
        progress: Progress percentage (0-100)
        
    Returns:
        Dict with status, color, and icon
    """
    if progress >= 100:
        return {
            "status": "Completed",
            "color": "#22c55e",  # Green
            "icon": "✅"
        }
    elif progress >= 75:
        return {
            "status": "Near Completion",
            "color": "#84cc16",  # Lime
            "icon": "🔶"
        }
    elif progress >= 50:
        return {
            "status": "In Progress",
            "color": "#f59e0b",  # Amber
            "icon": "🔄"
        }
    elif progress > 0:
        return {
            "status": "Started",
            "color": "#3b82f6",  # Blue
            "icon": "▶️"
        }
    else:
        return {
            "status": "Not Started",
            "color": "#94a3b8",  # Slate
            "icon": "⏸️"
        }


def calculate_days_remaining(due_date: date) -> Dict[str, Any]:
    """
    Calculate days remaining until due date with status.
    
    Useful for deadline tracking and alert generation.
    
    Args:
        due_date: Target due date
        
    Returns:
        Dict with days_remaining, status, color, and urgency
    """
    if due_date is None:
        return {
            "days_remaining": None,
            "status": "No Date",
            "color": "#94a3b8",
            "urgency": "unknown"
        }
    
    today = date.today()
    days_remaining = (due_date - today).days
    
    if days_remaining < 0:
        return {
            "days_remaining": days_remaining,
            "status": "Overdue",
            "color": "#ef4444",  # Red
            "urgency": "critical"
        }
    elif days_remaining == 0:
        return {
            "days_remaining": 0,
            "status": "Due Today",
            "color": "#f97316",  # Orange
            "urgency": "critical"
        }
    elif days_remaining <= 3:
        return {
            "days_remaining": days_remaining,
            "status": "Due Soon",
            "color": "#f59e0b",  # Amber
            "urgency": "high"
        }
    elif days_remaining <= 7:
        return {
            "days_remaining": days_remaining,
            "status": "This Week",
            "color": "#84cc16",  # Lime
            "urgency": "medium"
        }
    else:
        return {
            "days_remaining": days_remaining,
            "status": "On Track",
            "color": "#22c55e",  # Green
            "urgency": "low"
        }


# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def validate_email(email: str) -> bool:
    """
    Validate email format using regex.
    
    Returns True if email has valid format.
    """
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Check password strength and return requirements.
    
    Returns dict with 'valid' boolean and list of 'missing' requirements.
    """
    missing = []
    
    if len(password) < 8:
        missing.append("Minimum 8 characters")
    if not re.search(r'[A-Z]', password):
        missing.append("At least one uppercase letter")
    if not re.search(r'[a-z]', password):
        missing.append("At least one lowercase letter")
    if not re.search(r'[0-9]', password):
        missing.append("At least one number")
    
    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "strength": "Strong" if len(missing) == 0 else ("Medium" if len(missing) <= 2 else "Weak")
    }


# =============================================================================
# DATAFRAME UTILITIES
# =============================================================================

def safe_dataframe_operation(df: pd.DataFrame, operation: str, **kwargs) -> pd.DataFrame:
    """
    Safely perform a DataFrame operation with error handling.
    
    Returns empty DataFrame if operation fails.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    try:
        if operation == "filter":
            return df.query(kwargs.get('query', ''))
        elif operation == "sort":
            return df.sort_values(by=kwargs.get('by', []), ascending=kwargs.get('ascending', True))
        elif operation == "group":
            return df.groupby(kwargs.get('by', [])).agg(kwargs.get('agg', {}))
        else:
            return df
    except Exception as e:
        logger.error("DataFrame operation failed: %s", e)
        return pd.DataFrame()


def fill_missing_dates(df: pd.DataFrame, date_col: str, start: date, end: date) -> pd.DataFrame:
    """
    Fill missing dates in a DataFrame with zero/null values.
    
    Useful for creating continuous time series data for charts.
    """
    if df.empty or date_col not in df.columns:
        return df
    
    # Create complete date range
    date_range = pd.date_range(start=start, end=end, freq='D')
    complete_df = pd.DataFrame({date_col: date_range})
    
    # Merge with original data
    df[date_col] = pd.to_datetime(df[date_col])
    result = complete_df.merge(df, on=date_col, how='left')
    
    return result


# =============================================================================
# DISPLAY UTILITIES
# =============================================================================

def create_html_metric_card(title: str, value: str, subtitle: str = "", color: str = "#667eea") -> str:
    """
    Create an HTML metric card for Streamlit display.
    
    Uses the CSS classes defined in config.py
    """
    return f"""
    <div class="metric-card" style="border-bottom-color: {color};">
        <h3 style="color: #64748b; margin: 0; font-size: 14px;">{title}</h3>
        <h1 style="color: {color}; margin: 10px 0;">{value}</h1>
        <p style="color: #94a3b8; margin: 0; font-size: 12px;">{subtitle}</p>
    </div>
    """


def create_status_badge(status: str) -> str:
    """
    Create an HTML status badge with appropriate color.
    """
    status_classes = {
        "Planned": "status-planned",
        "In Progress": "status-progress",
        "Under Review": "status-review",
        "Approved": "status-approved",
        "On Hold": "status-hold",
        "Completed": "status-approved",
        "Not Started": "status-planned"
    }
    
    badge_class = status_classes.get(status, "status-planned")
    return f'<span class="status-badge {badge_class}">{status}</span>'


# =============================================================================
# LOGGING UTILITIES
# =============================================================================

def log_action(action: str, details: str = "", user: str = "System") -> None:
    """
    Log an action with timestamp.
    
    In production, this could write to a file or database.
    For now, it uses the module logger.
    """
    logger.info("[%s] %s: %s", user, action, details)
