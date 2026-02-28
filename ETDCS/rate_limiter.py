# =============================================================================
# rate_limiter.py - Login Rate Limiting
# =============================================================================
# Protects against brute force login attempts.
# Locks account for 15 minutes after 5 failed attempts.
# =============================================================================

import time
from typing import Tuple

# In-memory store for rate limiting (resets on server restart)
# Format: {email: {"attempts": int, "locked_until": float}}
_failed_attempts: dict = {}

# Configuration
MAX_ATTEMPTS = 5
LOCKOUT_DURATION = 15 * 60  # 15 minutes in seconds


def check_rate_limit(email: str) -> Tuple[bool, str]:
    """
    Check if login is allowed for the given email.
    
    Args:
        email: User email address
        
    Returns:
        Tuple of (allowed: bool, error_message: str)
        - If allowed: (True, "")
        - If locked: (False, "Account locked. Try again in X minutes.")
    """
    email_lower = email.lower()
    
    if email_lower not in _failed_attempts:
        return True, ""
    
    record = _failed_attempts[email_lower]
    
    # Check if locked out
    if "locked_until" in record:
        remaining = record["locked_until"] - time.time()
        if remaining > 0:
            minutes = int(remaining / 60) + 1
            return False, f"Account locked. Try again in {minutes} minute{'s' if minutes != 1 else ''}."
        else:
            # Lockout expired, reset
            del _failed_attempts[email_lower]
            return True, ""
    
    return True, ""


def record_failed_attempt(email: str) -> int:
    """
    Record a failed login attempt.
    
    Args:
        email: User email address
        
    Returns:
        Current number of failed attempts
    """
    email_lower = email.lower()
    
    if email_lower not in _failed_attempts:
        _failed_attempts[email_lower] = {"attempts": 0}
    
    _failed_attempts[email_lower]["attempts"] += 1
    attempts = _failed_attempts[email_lower]["attempts"]
    
    # Lock account if max attempts reached
    if attempts >= MAX_ATTEMPTS:
        _failed_attempts[email_lower]["locked_until"] = time.time() + LOCKOUT_DURATION
    
    return attempts


def record_success(email: str) -> None:
    """
    Clear failed attempts after successful login.
    
    Args:
        email: User email address
    """
    email_lower = email.lower()
    if email_lower in _failed_attempts:
        del _failed_attempts[email_lower]


def get_remaining_attempts(email: str) -> int:
    """
    Get remaining attempts before lockout.
    
    Args:
        email: User email address
        
    Returns:
        Number of remaining attempts
    """
    email_lower = email.lower()
    
    if email_lower not in _failed_attempts:
        return MAX_ATTEMPTS
    
    return MAX_ATTEMPTS - _failed_attempts[email_lower].get("attempts", 0)
