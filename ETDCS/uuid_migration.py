# =============================================================================
# database/uuid_migration.py - UUID Column Migration
# Task 17 - UUID Migration
# =============================================================================
# Adds UUID columns to core tables without breaking existing integer IDs.
#
# Strategy: Additive Approach
#   - Does NOT remove existing id columns
#   - Adds uuid column as TEXT UNIQUE
#   - Populates with UUID v4 values
#   - Zero breaking changes
#
# Benefits of UUIDs:
#   - Not guessable (security: no id=1, id=2 enumeration attacks)
#   - Suitable for distributed systems
#   - Can be generated client-side
#   - Merges between databases don't conflict
#
# Usage:
#   from database.uuid_migration import run_uuid_migration
#   
#   result = run_uuid_migration()
#   print(result)  # {"status": "success", "updated": {...}, "coverage": {...}}
#
# Or with existing connection:
#   conn = sqlite3.connect("etdcs.db")
#   result = run_uuid_migration(conn)
# =============================================================================

from __future__ import annotations

import uuid
import sqlite3
from typing import Dict, Optional, Any, List

# =============================================================================
# CONFIGURATION
# =============================================================================

# Tables to migrate (core tables only)
TABLES_TO_MIGRATE = ["deliverables", "tasks", "users"]

# Column name for UUID
UUID_COLUMN = "uuid"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> List[str]:
    """
    Get list of column names for a table.
    
    Uses PRAGMA table_info to inspect the schema.
    
    Args:
        conn: Database connection
        table_name: Name of the table to inspect
    
    Returns:
        List of column names
    """
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """
    Check if a table exists in the database.
    
    Args:
        conn: Database connection
        table_name: Name of the table to check
    
    Returns:
        True if table exists, False otherwise
    """
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def _generate_uuid() -> str:
    """
    Generate a new UUID v4 string.
    
    Uses Python's uuid module (stdlib).
    UUID v4 is randomly generated and has 122 bits of randomness.
    
    Returns:
        UUID string in format: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    """
    return str(uuid.uuid4())


# =============================================================================
# CORE MIGRATION FUNCTIONS
# =============================================================================

def add_uuid_columns(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Add UUID columns to tables and populate them.
    
    This is the main migration function that:
    1. Checks if uuid column exists (skip if already present)
    2. Adds uuid column as TEXT (without UNIQUE - added separately as index)
    3. Generates UUIDs for all existing rows
    4. Creates UNIQUE index on uuid column
    
    Note: SQLite doesn't allow UNIQUE in ALTER TABLE ADD COLUMN,
    so we add the column first, populate it, then create a unique index.
    
    Args:
        conn: SQLite database connection
    
    Returns:
        Dict with count of rows updated per table:
        {"deliverables": int, "tasks": int, "users": int}
    """
    updated_counts = {}
    
    for table in TABLES_TO_MIGRATE:
        # Check if table exists
        if not _table_exists(conn, table):
            updated_counts[table] = 0
            continue
        
        # Check if uuid column already exists
        columns = _get_table_columns(conn, table)
        
        if UUID_COLUMN not in columns:
            # Add uuid column (without UNIQUE constraint - SQLite limitation)
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {UUID_COLUMN} TEXT"
                )
                conn.commit()
            except sqlite3.OperationalError as e:
                # Column might have been added by another process
                if "duplicate column" not in str(e).lower():
                    raise
        
        # Generate UUIDs for rows that don't have one
        count = generate_uuids_for_table(conn, table)
        updated_counts[table] = count
        
        # Create unique index if not exists (after populating to avoid conflicts)
        index_name = f"idx_{table}_{UUID_COLUMN}"
        try:
            conn.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table}({UUID_COLUMN})"
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Handle case where duplicates somehow exist
            print(f"Warning: Could not create unique index on {table}.{UUID_COLUMN}")
    
    return updated_counts


def generate_uuids_for_table(conn: sqlite3.Connection, table_name: str) -> int:
    """
    Generate UUIDs for all rows where uuid IS NULL.
    
    This function can be called independently to fill in any
    missing UUIDs (e.g., after bulk data import).
    
    Args:
        conn: SQLite database connection
        table_name: Name of the table to update
    
    Returns:
        Number of rows updated
    """
    # Check if uuid column exists
    columns = _get_table_columns(conn, table_name)
    if UUID_COLUMN not in columns:
        return 0
    
    # Get all rows with missing UUID
    cursor = conn.execute(
        f"SELECT id FROM {table_name} WHERE {UUID_COLUMN} IS NULL"
    )
    rows_needing_uuid = cursor.fetchall()
    
    if not rows_needing_uuid:
        return 0
    
    # Update each row with a new UUID
    updated = 0
    for (row_id,) in rows_needing_uuid:
        new_uuid = _generate_uuid()
        try:
            conn.execute(
                f"UPDATE {table_name} SET {UUID_COLUMN} = ? WHERE id = ?",
                (new_uuid, row_id)
            )
            updated += 1
        except sqlite3.IntegrityError:
            # UUID collision (extremely unlikely), try again
            new_uuid = _generate_uuid()
            conn.execute(
                f"UPDATE {table_name} SET {UUID_COLUMN} = ? WHERE id = ?",
                (new_uuid, row_id)
            )
            updated += 1
    
    conn.commit()
    return updated


def verify_uuid_coverage(conn: sqlite3.Connection) -> Dict[str, Dict[str, int]]:
    """
    Verify that all rows have UUIDs.
    
    This function checks the completeness of UUID migration
    and returns detailed statistics per table.
    
    Args:
        conn: SQLite database connection
    
    Returns:
        Dict with coverage statistics:
        {
            "deliverables": {"total": int, "with_uuid": int, "missing": int},
            "tasks": {"total": int, "with_uuid": int, "missing": int},
            "users": {"total": int, "with_uuid": int, "missing": int},
        }
    """
    coverage = {}
    
    for table in TABLES_TO_MIGRATE:
        # Check if table exists
        if not _table_exists(conn, table):
            coverage[table] = {
                "total": 0,
                "with_uuid": 0,
                "missing": 0
            }
            continue
        
        # Check if uuid column exists
        columns = _get_table_columns(conn, table)
        if UUID_COLUMN not in columns:
            # Column doesn't exist yet
            total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            coverage[table] = {
                "total": total,
                "with_uuid": 0,
                "missing": total
            }
            continue
        
        # Get statistics
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        with_uuid = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {UUID_COLUMN} IS NOT NULL"
        ).fetchone()[0]
        
        coverage[table] = {
            "total": total,
            "with_uuid": with_uuid,
            "missing": total - with_uuid
        }
    
    return coverage


def get_by_uuid(
    conn: sqlite3.Connection,
    table_name: str,
    uuid_str: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a row by UUID instead of integer ID.
    
    This provides a UUID-based lookup that can be used in APIs
    and external references without exposing internal IDs.
    
    Args:
        conn: SQLite database connection
        table_name: Name of the table to query
        uuid_str: UUID string to look up
    
    Returns:
        Dict with column names and values, or None if not found
        
    Raises:
        ValueError: If table_name is not in allowed list
    """
    # Validate table name (prevent SQL injection)
    if table_name not in TABLES_TO_MIGRATE:
        raise ValueError(f"Invalid table name: {table_name}")
    
    # Check if uuid column exists
    columns = _get_table_columns(conn, table_name)
    if UUID_COLUMN not in columns:
        return None
    
    # Query by UUID
    cursor = conn.execute(
        f"SELECT * FROM {table_name} WHERE {UUID_COLUMN} = ?",
        (uuid_str,)
    )
    row = cursor.fetchone()
    
    if row is None:
        return None
    
    # Get column names for dict
    column_names = [desc[0] for desc in cursor.description]
    
    return dict(zip(column_names, row))


def get_id_by_uuid(
    conn: sqlite3.Connection,
    table_name: str,
    uuid_str: str
) -> Optional[int]:
    """
    Get the integer ID for a given UUID.
    
    Useful for internal operations that still use integer IDs.
    
    Args:
        conn: SQLite database connection
        table_name: Name of the table to query
        uuid_str: UUID string to look up
    
    Returns:
        Integer ID, or None if not found
    """
    # Validate table name
    if table_name not in TABLES_TO_MIGRATE:
        raise ValueError(f"Invalid table name: {table_name}")
    
    # Check if uuid column exists
    columns = _get_table_columns(conn, table_name)
    if UUID_COLUMN not in columns:
        return None
    
    cursor = conn.execute(
        f"SELECT id FROM {table_name} WHERE {UUID_COLUMN} = ?",
        (uuid_str,)
    )
    row = cursor.fetchone()
    
    return row[0] if row else None


def get_uuid_by_id(
    conn: sqlite3.Connection,
    table_name: str,
    row_id: int
) -> Optional[str]:
    """
    Get the UUID for a given integer ID.
    
    Useful for converting internal IDs to external references.
    
    Args:
        conn: SQLite database connection
        table_name: Name of the table to query
        row_id: Integer ID to look up
    
    Returns:
        UUID string, or None if not found
    """
    # Validate table name
    if table_name not in TABLES_TO_MIGRATE:
        raise ValueError(f"Invalid table name: {table_name}")
    
    # Check if uuid column exists
    columns = _get_table_columns(conn, table_name)
    if UUID_COLUMN not in columns:
        return None
    
    cursor = conn.execute(
        f"SELECT {UUID_COLUMN} FROM {table_name} WHERE id = ?",
        (row_id,)
    )
    row = cursor.fetchone()
    
    return row[0] if row else None


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run_uuid_migration(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """
    Run the complete UUID migration.
    
    This is the main entry point that orchestrates the entire migration:
    1. Opens connection if not provided
    2. Adds UUID columns to all tables
    3. Generates UUIDs for existing rows
    4. Verifies coverage
    5. Returns summary
    
    This function is idempotent - running it multiple times has no side effects.
    
    Args:
        conn: Optional SQLite connection. If None, uses default DB path.
    
    Returns:
        Dict with migration results:
        {
            "status": "success" | "partial" | "already_complete",
            "updated": {"deliverables": int, "tasks": int, "users": int},
            "coverage": {...}
        }
    """
    # Import DB_PATH from config
    from config import DB_PATH
    
    # Manage connection
    _own_conn = conn is None
    if _own_conn:
        conn = sqlite3.connect(DB_PATH)
    
    try:
        # Add UUID columns
        updated = add_uuid_columns(conn)
        
        # Verify coverage
        coverage = verify_uuid_coverage(conn)
        
        # Determine status
        total_missing = sum(
            table_coverage["missing"]
            for table_coverage in coverage.values()
        )
        
        total_updated = sum(updated.values())
        
        if total_missing == 0 and total_updated == 0:
            status = "already_complete"
        elif total_missing == 0:
            status = "success"
        else:
            status = "partial"
        
        return {
            "status": status,
            "updated": updated,
            "coverage": coverage
        }
    
    finally:
        if _own_conn:
            conn.close()


# =============================================================================
# MIGRATION 4 - For migration_manager.py Integration
# =============================================================================

# This can be added to migration_manager.py MIGRATIONS list:
# {
#     "version": 4,
#     "description": "Add UUID columns (Task 17)",
#     "sql": [],
#     "special": "uuid_columns"
# }

MIGRATION_SQL = """
-- Migration 4: Add UUID columns (Task 17)
-- Uses special handler in migration_manager.py
-- See: database/uuid_migration.py
"""


def migration_4_uuid_columns(conn: sqlite3.Connection) -> bool:
    """
    Migration 4 handler for integration with migration_manager.
    
    This function is designed to be called from migration_manager.py
    as a special migration handler (like migration 2 for soft delete).
    
    Args:
        conn: Database connection
    
    Returns:
        True if successful, False otherwise
    """
    try:
        result = add_uuid_columns(conn)
        return True
    except Exception as e:
        print(f"Migration 4 (UUID columns) failed: {e}")
        return False


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def batch_generate_uuids(
    conn: sqlite3.Connection,
    table_name: str,
    batch_size: int = 1000
) -> int:
    """
    Generate UUIDs in batches for large tables.
    
    For tables with millions of rows, this prevents memory issues
    by processing in smaller batches.
    
    Args:
        conn: SQLite database connection
        table_name: Name of the table to update
        batch_size: Number of rows to process per batch
    
    Returns:
        Total number of rows updated
    """
    # Validate table name
    if table_name not in TABLES_TO_MIGRATE:
        raise ValueError(f"Invalid table name: {table_name}")
    
    total_updated = 0
    
    while True:
        # Get batch of rows without UUID
        cursor = conn.execute(
            f"SELECT id FROM {table_name} WHERE {UUID_COLUMN} IS NULL LIMIT ?",
            (batch_size,)
        )
        rows = cursor.fetchall()
        
        if not rows:
            break
        
        # Update this batch
        for (row_id,) in rows:
            new_uuid = _generate_uuid()
            conn.execute(
                f"UPDATE {table_name} SET {UUID_COLUMN} = ? WHERE id = ?",
                (new_uuid, row_id)
            )
        
        conn.commit()
        total_updated += len(rows)
    
    return total_updated


def validate_uuid_format(uuid_str: str) -> bool:
    """
    Validate that a string is a valid UUID.
    
    Args:
        uuid_str: String to validate
    
    Returns:
        True if valid UUID format, False otherwise
    """
    try:
        uuid.UUID(uuid_str)
        return True
    except (ValueError, AttributeError):
        return False


def find_duplicate_uuids(conn: sqlite3.Connection) -> Dict[str, List[str]]:
    """
    Find any duplicate UUIDs (should never happen with UNIQUE constraint).
    
    This is a diagnostic function for detecting data corruption.
    
    Args:
        conn: SQLite database connection
    
    Returns:
        Dict mapping table names to lists of duplicate UUIDs
    """
    duplicates = {}
    
    for table in TABLES_TO_MIGRATE:
        if not _table_exists(conn, table):
            continue
        
        columns = _get_table_columns(conn, table)
        if UUID_COLUMN not in columns:
            continue
        
        cursor = conn.execute(f"""
            SELECT {UUID_COLUMN}, COUNT(*) as cnt
            FROM {table}
            WHERE {UUID_COLUMN} IS NOT NULL
            GROUP BY {UUID_COLUMN}
            HAVING COUNT(*) > 1
        """)
        
        dupe_list = [row[0] for row in cursor.fetchall()]
        if dupe_list:
            duplicates[table] = dupe_list
    
    return duplicates


# =============================================================================
# CLI ENTRY POINT (for standalone execution)
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("UUID Migration - Task 17")
    print("=" * 60)
    
    # Run migration
    result = run_uuid_migration()
    
    print(f"\nStatus: {result['status']}")
    print("\nRows Updated:")
    for table, count in result['updated'].items():
        print(f"  {table}: {count}")
    
    print("\nUUID Coverage:")
    for table, stats in result['coverage'].items():
        print(f"  {table}:")
        print(f"    Total: {stats['total']}")
        print(f"    With UUID: {stats['with_uuid']}")
        print(f"    Missing: {stats['missing']}")
    
    print("\n" + "=" * 60)
    
    # Exit with appropriate code
    if result['status'] == 'partial':
        sys.exit(1)  # Partial migration
    else:
        sys.exit(0)  # Success or already complete
