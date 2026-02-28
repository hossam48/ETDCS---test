"""
================================================================================
AUTH.PY - Secure Authentication Module (bcrypt + SHA-256 Legacy Support)
================================================================================
Version: 2.0 - Security Hardened
Author: Elsewedy PSP - MEP Design Team

MIGRATION NOTES:
- bcrypt is now the primary hashing algorithm
- SHA-256 hashes are still supported for backward compatibility
- Users with SHA-256 hashes are auto-upgraded to bcrypt on successful login
- No action required from users - transparent migration

SECURITY IMPROVEMENTS:
- bcrypt with cost factor 12 (~250ms per hash)
- Automatic hash upgrade on login
- Constant-time comparison (prevents timing attacks)
- Proper error handling without information leakage
================================================================================
"""

import secrets
import hashlib
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# BCRYPT IMPORT (with fallback instructions)
# =============================================================================

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    # This will be shown at import time
    raise ImportError(
        "bcrypt is required for secure password hashing.\n"
        "Install it with: pip install bcrypt\n"
        "On some systems you may also need: pip install importlib-metadata"
    )


# =============================================================================
# CONFIGURATION
# =============================================================================

# bcrypt work factor (cost)
# 12 = ~250ms per hash on modern hardware
# Increase this by 1 every 2 years to keep pace with hardware
BCRYPT_ROUNDS = 12

# Hash format prefixes for detection
BCRYPT_PREFIXES = ('$2a$', '$2b$', '$2y$')
SHA256_PREFIX = None  # SHA-256 hashes don't have a standard prefix


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PasswordHash:
    """
    Represents a parsed password hash with metadata.
    
    Used internally to determine how to verify a password.
    """
    algorithm: str  # 'bcrypt' or 'sha256_legacy'
    hash_value: str
    salt: Optional[str] = None
    needs_upgrade: bool = False


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    This is the NEW primary hashing function. All new passwords and
    password changes will use bcrypt.
    
    SECURITY PROPERTIES:
    - Cost factor 12 means ~250ms to compute
    - Salt is generated automatically by bcrypt
    - Resistant to GPU/ASIC attacks
    - Future-proof (cost factor can be increased)
    
    Args:
        password: Plain text password (will be encoded to UTF-8)
        
    Returns:
        bcrypt hash string (e.g., "$2b$12$N9qo8uLOickgx2ZMRZoMy...")
        
    Raises:
        ValueError: If password is empty or None
        
    Example:
        >>> hashed = hash_password("my_secure_password")
        >>> hashed.startswith('$2b$')
        True
    """
    if not password:
        raise ValueError("Password cannot be empty")
    
    # Encode password to bytes (bcrypt requires bytes)
    password_bytes = password.encode('utf-8')
    
    # Generate salt with specified cost factor
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    
    # Hash the password
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string for database storage
    return hashed_bytes.decode('utf-8')


def verify_password(password: str, stored_hash: str) -> Tuple[bool, bool]:
    """
    Verify a password against a stored hash.
    
    SUPPORTS BOTH:
    - bcrypt hashes (new format)
    - SHA-256+salt hashes (legacy format)
    
    BACKWARD COMPATIBILITY:
    - Automatically detects hash format
    - Verifies using the correct algorithm
    - Returns 'needs_upgrade' flag for SHA-256 hashes
    
    Args:
        password: Plain text password to verify
        stored_hash: Hash from database
        
    Returns:
        Tuple of (is_valid, needs_upgrade)
        - is_valid: True if password matches
        - needs_upgrade: True if hash should be upgraded to bcrypt
        
    Example:
        >>> # For bcrypt hash
        >>> valid, upgrade = verify_password("password", "$2b$12$...")
        >>> valid, upgrade
        (True, False)
        
        >>> # For SHA-256 hash (legacy)
        >>> valid, upgrade = verify_password("password", "salt$hash")
        >>> valid, upgrade
        (True, True)  # Should call hash_password() and update DB
    """
    if not password or not stored_hash:
        return False, False
    
    try:
        # Detect hash format
        hash_info = _parse_hash(stored_hash)
        
        if hash_info.algorithm == 'bcrypt':
            # Verify using bcrypt
            return _verify_bcrypt(password, stored_hash), False
            
        elif hash_info.algorithm == 'sha256_legacy':
            # Verify using legacy SHA-256
            is_valid = _verify_sha256_legacy(password, stored_hash)
            return is_valid, is_valid  # needs_upgrade only if valid
        
        else:
            # Unknown format - fail safe
            logger.warning(f"Unknown hash format detected")
            return False, False
            
    except Exception as e:
        # Log error but don't expose details to caller
        logger.error(f"Password verification error: {e}")
        return False, False


def _parse_hash(stored_hash: str) -> PasswordHash:
    """
    Parse a stored hash to determine its algorithm.
    
    DETECTION LOGIC:
    - Starts with $2a$, $2b$, or $2y$ → bcrypt
    - Contains exactly one $ separator → SHA-256 legacy
    - Otherwise → Unknown (will fail verification)
    
    Args:
        stored_hash: The stored hash string
        
    Returns:
        PasswordHash with algorithm info
    """
    if not stored_hash:
        return PasswordHash(algorithm='unknown', hash_value='')
    
    # Check for bcrypt prefix
    for prefix in BCRYPT_PREFIXES:
        if stored_hash.startswith(prefix):
            return PasswordHash(
                algorithm='bcrypt',
                hash_value=stored_hash,
                needs_upgrade=False
            )
    
    # Check for SHA-256 legacy format: "salt$hash"
    # SHA-256 hashes are 64 hex chars, salt is 32 hex chars
    if '$' in stored_hash:
        parts = stored_hash.split('$')
        if len(parts) == 2:
            # Looks like SHA-256 legacy format
            return PasswordHash(
                algorithm='sha256_legacy',
                hash_value=parts[1],
                salt=parts[0],
                needs_upgrade=True
            )
    
    # Could be plain text (very old, insecure) or unknown format
    logger.warning(f"Unrecognized hash format: {stored_hash[:20]}...")
    return PasswordHash(algorithm='unknown', hash_value=stored_hash)


def _verify_bcrypt(password: str, stored_hash: str) -> bool:
    """
    Verify password against bcrypt hash.
    
    Uses bcrypt.checkpw() which:
    - Extracts salt from the hash automatically
    - Performs constant-time comparison
    - Returns True/False
    """
    try:
        password_bytes = password.encode('utf-8')
        hash_bytes = stored_hash.encode('utf-8')
        
        return bcrypt.checkpw(password_bytes, hash_bytes)
        
    except Exception as e:
        logger.error(f"bcrypt verification error: {e}")
        return False


def _verify_sha256_legacy(password: str, stored_hash: str) -> bool:
    """
    Verify password against legacy SHA-256 hash.
    
    LEGACY FORMAT: "salt$hash"
    
    SECURITY NOTE:
    - SHA-256 is NOT designed for passwords
    - This is ONLY for backward compatibility
    - Hash should be upgraded to bcrypt after successful verification
    """
    try:
        if '$' not in stored_hash:
            return False
        
        salt, stored_hash_value = stored_hash.split('$')
        
        # Compute hash with same salt
        password_bytes = (password + salt).encode('utf-8')
        computed_hash = hashlib.sha256(password_bytes).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return secrets.compare_digest(computed_hash, stored_hash_value)
        
    except Exception as e:
        logger.error(f"SHA-256 verification error: {e}")
        return False


# =============================================================================
# AUTHENTICATION FUNCTION
# =============================================================================

def authenticate_user(
    email: str,
    password: str,
    db_connection
) -> Optional[dict]:
    """
    Authenticate a user by email and password.
    
    MIGRATION LOGIC:
    1. Look up user by email
    2. Verify password (supports both bcrypt and SHA-256)
    3. If SHA-256 hash verified → Upgrade to bcrypt → Update database
    4. Return user info or None
    
    Args:
        email: User's email address
        password: Plain text password
        db_connection: SQLite connection object
        
    Returns:
        dict with user info if authenticated, None otherwise
        
    Example:
        >>> user = authenticate_user("admin@elsewedy.com", "password", conn)
        >>> if user:
        ...     print(f"Welcome, {user['name']}")
    """
    if not email or not password:
        return None
    
    cursor = db_connection.cursor()
    
    # Get user by email
    cursor.execute(
        "SELECT id, full_name, email, password, role, discipline FROM users WHERE email = ?",
        (email,)
    )
    
    row = cursor.fetchone()
    
    if row is None:
        # User not found - use constant-time delay to prevent timing attacks
        # Still hash something to take time
        hash_password("dummy_password_for_timing")
        logger.info(f"Login attempt for non-existent email: {email}")
        return None
    
    user_id, full_name, user_email, stored_password, role, discipline = row
    
    # Verify password
    is_valid, needs_upgrade = verify_password(password, stored_password)
    
    if not is_valid:
        logger.warning(f"Failed login attempt for: {email}")
        return None
    
    # If hash needs upgrade (SHA-256 → bcrypt), update it now
    if needs_upgrade:
        try:
            new_hash = hash_password(password)
            cursor.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (new_hash, user_id)
            )
            db_connection.commit()
            logger.info(f"Password hash upgraded for user: {email}")
        except Exception as e:
            # Log error but don't fail the login
            logger.error(f"Failed to upgrade password hash: {e}")
    
    # Update last login timestamp (optional)
    try:
        cursor.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,)
        )
        db_connection.commit()
    except:
        pass  # Column might not exist yet
    
    logger.info(f"Successful login: {email}")
    
    return {
        'id': user_id,
        'name': full_name,
        'email': user_email,
        'role': role,
        'discipline': discipline
    }


# =============================================================================
# PASSWORD CHANGE FUNCTION
# =============================================================================

def change_password(
    user_id: int,
    current_password: str,
    new_password: str,
    db_connection
) -> Tuple[bool, str]:
    """
    Change a user's password.
    
    SECURITY:
    - Verifies current password before allowing change
    - Always uses bcrypt for new password
    - Validates new password strength (basic)
    
    Args:
        user_id: User's ID
        current_password: User's current password
        new_password: New password to set
        db_connection: Database connection
        
    Returns:
        Tuple of (success, message)
    """
    cursor = db_connection.cursor()
    
    # Get current password hash
    cursor.execute(
        "SELECT password FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    
    if row is None:
        return False, "User not found"
    
    stored_hash = row[0]
    
    # Verify current password
    is_valid, _ = verify_password(current_password, stored_hash)
    
    if not is_valid:
        return False, "Current password is incorrect"
    
    # Validate new password
    if len(new_password) < 8:
        return False, "New password must be at least 8 characters"
    
    if new_password == current_password:
        return False, "New password must be different from current password"
    
    # Hash new password with bcrypt
    new_hash = hash_password(new_password)
    
    # Update database
    cursor.execute(
        "UPDATE users SET password = ? WHERE id = ?",
        (new_hash, user_id)
    )
    db_connection.commit()
    
    logger.info(f"Password changed for user ID: {user_id}")
    
    return True, "Password changed successfully"


# =============================================================================
# ADMIN FUNCTIONS
# =============================================================================

def create_user_with_password(
    full_name: str,
    email: str,
    password: str,
    role: str,
    discipline: str,
    db_connection
) -> Tuple[bool, str]:
    """
    Create a new user with a bcrypt-hashed password.
    
    Args:
        full_name: User's full name
        email: User's email
        password: Plain text password
        role: User role (Engineer, Lead, Manager)
        discipline: User's discipline
        db_connection: Database connection
        
    Returns:
        Tuple of (success, message)
    """
    cursor = db_connection.cursor()
    
    # Check if email already exists
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        return False, "Email already registered"
    
    # Validate password
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    # Hash password
    hashed_password = hash_password(password)
    
    # Insert user
    try:
        cursor.execute('''
            INSERT INTO users (full_name, email, password, role, discipline, join_date)
            VALUES (?, ?, ?, ?, ?, DATE('now'))
        ''', (full_name, email, hashed_password, role, discipline))
        db_connection.commit()
        
        logger.info(f"New user created: {email}")
        return True, "User created successfully"
        
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        return False, f"Failed to create user: {str(e)}"


def force_password_reset(
    user_id: int,
    new_password: str,
    db_connection
) -> Tuple[bool, str]:
    """
    Force reset a user's password (admin function).
    
    SECURITY WARNING:
    - This bypasses current password verification
    - Should only be used by administrators
    - Consider logging this action for audit
    
    Args:
        user_id: User's ID
        new_password: New password to set
        db_connection: Database connection
        
    Returns:
        Tuple of (success, message)
    """
    cursor = db_connection.cursor()
    
    # Validate new password
    if len(new_password) < 8:
        return False, "Password must be at least 8 characters"
    
    # Hash new password
    hashed_password = hash_password(new_password)
    
    # Update database
    try:
        cursor.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, user_id)
        )
        db_connection.commit()
        
        logger.warning(f"Password force-reset for user ID: {user_id}")
        return True, "Password reset successfully"
        
    except Exception as e:
        logger.error(f"Failed to reset password: {e}")
        return False, f"Failed to reset password: {str(e)}"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def is_bcrypt_hash(hash_string: str) -> bool:
    """
    Check if a hash string is a bcrypt hash.
    
    Useful for checking migration status.
    """
    if not hash_string:
        return False
    return any(hash_string.startswith(prefix) for prefix in BCRYPT_PREFIXES)


def needs_bcrypt_upgrade(hash_string: str) -> bool:
    """
    Check if a hash needs to be upgraded to bcrypt.
    
    Returns True if hash is SHA-256 legacy format.
    """
    if not hash_string:
        return False
    return not is_bcrypt_hash(hash_string)


def check_bcrypt_cost(stored_hash: str) -> Optional[int]:
    """
    Extract the cost factor from a bcrypt hash.
    
    Returns None if not a bcrypt hash.
    """
    if not is_bcrypt_hash(stored_hash):
        return None
    
    try:
        # bcrypt hash format: $2b$12$...
        # Cost is after the second $
        parts = stored_hash.split('$')
        if len(parts) >= 3:
            return int(parts[2])
    except:
        pass
    
    return None


# =============================================================================
# MIGRATION HELPER
# =============================================================================

def migrate_all_passwords(db_connection) -> dict:
    """
    Migrate all SHA-256 hashes to bcrypt.
    
    WARNING: This requires knowing users' passwords.
    Since we can't reverse hashes, this should be done
    during login (authenticate_user handles this automatically).
    
    This function is for reporting migration status only.
    
    Returns:
        Dict with migration statistics
    """
    cursor = db_connection.cursor()
    
    cursor.execute("SELECT id, email, password FROM users")
    users = cursor.fetchall()
    
    stats = {
        'total_users': len(users),
        'bcrypt_users': 0,
        'sha256_users': 0,
        'unknown_users': 0
    }
    
    for user_id, email, password_hash in users:
        if is_bcrypt_hash(password_hash):
            stats['bcrypt_users'] += 1
        elif '$' in password_hash:
            stats['sha256_users'] += 1
        else:
            stats['unknown_users'] += 1
    
    return stats
