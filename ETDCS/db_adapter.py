# =============================================================================
# db_adapter.py - Database Adapter Abstraction Layer
# Task 13 - Reference Implementation
# =============================================================================
# Provides a unified interface for SQLite and PostgreSQL databases.
# Handles connection management, placeholder differences, and SQL translation.
#
# Usage:
#   from db_adapter import DatabaseAdapter, get_connection, get_db_type
#
#   # Explicit type
#   adapter = DatabaseAdapter("postgresql")
#   conn = adapter.connect()
#
#   # Auto-detect / singleton
#   conn = get_connection()
#   placeholder = get_placeholder()  # "?" or "%s"
# =============================================================================

from __future__ import annotations

import os
import re
import sqlite3
from typing import Optional, Any, Dict
from types import SimpleNamespace

# =============================================================================
# CONFIGURATION
# =============================================================================

# Database type: "sqlite", "postgresql", or "auto"
DB_TYPE = os.environ.get("DB_TYPE", "auto")

# SQLite database path
SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", os.path.join("database", "etdcs_v7.db"))

# PostgreSQL connection settings
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "etdcs")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "etdcs_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")


# =============================================================================
# DATABASE ADAPTER CLASS
# =============================================================================

class DatabaseAdapter:
    """
    Abstracted database adapter supporting SQLite and PostgreSQL.
    
    Provides:
        - Unified connection interface
        - Placeholder conversion (? → %s)
        - SQL translation for PostgreSQL compatibility
        - Type detection methods
    """

    def __init__(self, db_type: str = "auto"):
        """
        Initialize the database adapter.
        
        Args:
            db_type: "sqlite", "postgresql", or "auto"
        """
        if db_type == "auto":
            db_type = self._detect_db_type()
        
        self._db_type = db_type.lower()
        self._connection: Optional[Any] = None
        
        # Validate type
        if self._db_type not in ("sqlite", "postgresql"):
            raise ValueError(f"Unsupported database type: {db_type}")

    def _detect_db_type(self) -> str:
        """
        Auto-detect database type from environment.
        
        Priority:
            1. If POSTGRES_HOST is set → PostgreSQL
            2. Otherwise → SQLite
        """
        if POSTGRES_HOST and POSTGRES_HOST != "localhost":
            return "postgresql"
        return "sqlite"

    # -------------------------------------------------------------------------
    # Connection Methods
    # -------------------------------------------------------------------------

    def connect(self):
        """
        Open a database connection.
        
        Returns:
            Database connection object
            
        Raises:
            ConnectionError: If connection fails
        """
        if self._db_type == "sqlite":
            # Ensure database directory exists
            import os
            db_dir = os.path.dirname(SQLITE_DB_PATH)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            
            self._connection = sqlite3.connect(SQLITE_DB_PATH)
            
        elif self._db_type == "postgresql":
            try:
                import psycopg2
                self._connection = psycopg2.connect(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    database=POSTGRES_DB,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD
                )
            except ImportError:
                raise ImportError(
                    "psycopg2 is required for PostgreSQL. "
                    "Install with: pip install psycopg2-binary"
                )
        
        return self._connection

    def close(self) -> None:
        """Close the database connection if open."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def test_connection(self) -> bool:
        """
        Test if a connection can be established.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            self.close()
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Type Detection Methods
    # -------------------------------------------------------------------------

    def get_type(self) -> str:
        """
        Get the database type string.
        
        Returns:
            "sqlite" or "postgresql"
        """
        return self._db_type

    def is_postgresql(self) -> bool:
        """
        Check if using PostgreSQL.
        
        Returns:
            True if PostgreSQL, False otherwise
        """
        return self._db_type == "postgresql"

    # -------------------------------------------------------------------------
    # Placeholder Methods
    # -------------------------------------------------------------------------

    def get_placeholder(self) -> str:
        """
        Get the parameter placeholder for this database.
        
        Returns:
            "?" for SQLite, "%s" for PostgreSQL
        """
        return "?" if self._db_type == "sqlite" else "%s"

    # -------------------------------------------------------------------------
    # SQL Translation Methods
    # -------------------------------------------------------------------------

    def adapt_sql(self, sql: str) -> str:
        """
        Adapt SQL for the target database.
        
        For SQLite: Returns SQL unchanged.
        For PostgreSQL: Converts SQLite syntax to PostgreSQL.
        
        Translations:
            ?                    →  %s
            datetime('now')      →  NOW()
            DATE('now')          →  CURRENT_DATE
            INTEGER PRIMARY KEY  →  SERIAL PRIMARY KEY
            PRAGMA ...           →  "" (skip)
        
        Args:
            sql: SQL query string
            
        Returns:
            Adapted SQL string
        """
        if self._db_type == "sqlite":
            return sql
        
        # PostgreSQL adaptations
        adapted = sql
        
        # Skip PRAGMA statements entirely
        if adapted.strip().upper().startswith("PRAGMA"):
            return ""
        
        # Convert placeholders ? → %s
        # Count ? and replace with %s (preserving order for parameter binding)
        adapted = re.sub(r'\?', '%s', adapted)
        
        # Convert datetime('now') → NOW()
        adapted = re.sub(
            r"datetime\s*\(\s*['\"]now['\"]\s*\)",
            "NOW()",
            adapted,
            flags=re.IGNORECASE
        )
        
        # Convert DATE('now') → CURRENT_DATE
        adapted = re.sub(
            r"DATE\s*\(\s*['\"]now['\"]\s*\)",
            "CURRENT_DATE",
            adapted,
            flags=re.IGNORECASE
        )
        
        # Convert INTEGER PRIMARY KEY → SERIAL PRIMARY KEY
        # Only for CREATE TABLE statements, not foreign keys
        if "CREATE TABLE" in adapted.upper():
            adapted = re.sub(
                r"\bINTEGER\s+PRIMARY\s+KEY\b",
                "SERIAL PRIMARY KEY",
                adapted,
                flags=re.IGNORECASE
            )
        
        return adapted


# =============================================================================
# MODULE-LEVEL SINGLETON / CONVENIENCE FUNCTIONS
# =============================================================================

# Default adapter instance
default_adapter: Optional[DatabaseAdapter] = None


def _get_default_adapter() -> DatabaseAdapter:
    """Get or create the default adapter singleton."""
    global default_adapter
    if default_adapter is None:
        default_adapter = DatabaseAdapter(db_type=DB_TYPE)
    return default_adapter


def get_connection():
    """
    Get a database connection using the default adapter.
    
    This is a drop-in replacement for sqlite3.connect().
    
    Returns:
        Database connection object
    """
    return _get_default_adapter().connect()


def get_db_type() -> str:
    """
    Get the current database type.
    
    Returns:
        "sqlite" or "postgresql"
    """
    return _get_default_adapter().get_type()


def get_placeholder() -> str:
    """
    Get the parameter placeholder for current database.
    
    Returns:
        "?" or "%s"
    """
    return _get_default_adapter().get_placeholder()


def adapt_sql(sql: str) -> str:
    """
    Adapt SQL for the current database type.
    
    Args:
        sql: SQL query string
        
    Returns:
        Adapted SQL string
    """
    return _get_default_adapter().adapt_sql(sql)


# =============================================================================
# CONTEXT MANAGER SUPPORT
# =============================================================================

class DatabaseConnection:
    """
    Context manager for database connections.
    
    Usage:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
    """
    
    def __init__(self, adapter: Optional[DatabaseAdapter] = None):
        """
        Initialize context manager.
        
        Args:
            adapter: Optional specific adapter, uses default if None
        """
        self._adapter = adapter or _get_default_adapter()
        self._conn = None
    
    def __enter__(self):
        self._conn = self._adapter.connect()
        return self._conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            if exc_type is not None:
                self._conn.rollback()
            self._conn.close()
        return False


# =============================================================================
# INITIALIZATION
# =============================================================================

# Print configuration on import (for debugging)
if os.environ.get("DEBUG_DB"):
    adapter = _get_default_adapter()
    print(f"Database Adapter: {adapter.get_type()}")
    print(f"Placeholder: {adapter.get_placeholder()}")
