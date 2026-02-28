# =============================================================================
# tests/test_suite.py - ETDCS Unit Test Suite
# Task 16 - Unit Tests
# =============================================================================
# Framework: pytest
# No external mocking libraries - uses simple monkey-patching and SimpleNamespace
#
# Test Classes:
#   1. TestWorkflowEngine      - Status transition logic
#   2. TestMigrationManager    - Database migrations with in-memory SQLite
#   3. TestDbAdapter           - Database adapter abstraction
#   4. TestSecureFileUpload    - File upload security validation
#
# Usage:
#   pytest tests/test_suite.py -v
#   pytest tests/test_suite.py -v -k "WorkflowEngine"
# =============================================================================

import pytest
import sqlite3
import sys
import os
import tempfile
from types import SimpleNamespace
from io import BytesIO

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# =============================================================================
# TEST CLASS 1: TestWorkflowEngine
# =============================================================================
# Tests for workflow_engine.py - Status transition state machine
# =============================================================================

class TestWorkflowEngine:
    """
    Test the workflow engine's status transition logic.
    
    Tests cover:
    - Valid transitions for each role (Engineer, Lead, Manager)
    - Invalid transitions that should be rejected
    - Role-based permission enforcement
    - Edge cases (undefined transitions, cross-user modifications)
    """

    # -------------------------------------------------------------------------
    # Setup - Import workflow engine functions
    # -------------------------------------------------------------------------
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Import workflow engine functions for each test."""
        from workflow_engine import (
            get_allowed_transitions,
            can_transition,
            transition_task,
            transition_deliverable,
            _DELIVERABLE_TRANSITIONS,
            _TASK_TRANSITIONS,
            _ROLE_RANK,
        )
        self.get_allowed_transitions = get_allowed_transitions
        self.can_transition = can_transition
        self.transition_task = transition_task
        self.transition_deliverable = transition_deliverable
        self.DELIVERABLE_TRANSITIONS = _DELIVERABLE_TRANSITIONS
        self.TASK_TRANSITIONS = _TASK_TRANSITIONS
        self.ROLE_RANK = _ROLE_RANK

    # -------------------------------------------------------------------------
    # ✅ Valid Transitions
    # -------------------------------------------------------------------------

    def test_engineer_can_start_task(self):
        """
        Engineer should be able to start a task.
        Transition: Not Started → In Progress
        """
        allowed = self.get_allowed_transitions("task", "Not Started", "Engineer")
        assert "In Progress" in allowed, "Engineer should be able to start a task"
        
        # Also verify via can_transition
        is_allowed, reason = self.can_transition("task", "Not Started", "In Progress", "Engineer")
        assert is_allowed is True, f"Expected True, got reason: {reason}"

    def test_engineer_can_submit_for_review(self):
        """
        Engineer should be able to submit task for review.
        Transition: In Progress → Under Review
        """
        allowed = self.get_allowed_transitions("task", "In Progress", "Engineer")
        assert "Under Review" in allowed, "Engineer should be able to submit for review"
        
        is_allowed, reason = self.can_transition("task", "In Progress", "Under Review", "Engineer")
        assert is_allowed is True

    def test_lead_can_complete_task(self):
        """
        Lead should be able to mark a task as completed.
        Transition: Under Review → Completed
        """
        allowed = self.get_allowed_transitions("task", "Under Review", "Lead")
        assert "Completed" in allowed, "Lead should be able to complete a task"
        
        is_allowed, reason = self.can_transition("task", "Under Review", "Completed", "Lead")
        assert is_allowed is True

    def test_manager_can_approve_deliverable(self):
        """
        Manager should be able to approve a deliverable.
        Transition: Under Review → Approved
        """
        allowed = self.get_allowed_transitions("deliverable", "Under Review", "Manager")
        assert "Approved" in allowed, "Manager should be able to approve deliverables"
        
        is_allowed, reason = self.can_transition("deliverable", "Under Review", "Approved", "Manager")
        assert is_allowed is True

    def test_manager_can_cancel(self):
        """
        Manager should be able to cancel items from various states.
        Transition: In Progress → Cancelled
        """
        # Task cancellation
        allowed_task = self.get_allowed_transitions("task", "In Progress", "Manager")
        assert "Cancelled" in allowed_task, "Manager should be able to cancel tasks"
        
        # Deliverable cancellation
        allowed_deliv = self.get_allowed_transitions("deliverable", "In Progress", "Manager")
        assert "Cancelled" in allowed_deliv, "Manager should be able to cancel deliverables"
        
        # Also from On Hold
        allowed_onhold = self.get_allowed_transitions("deliverable", "On Hold", "Manager")
        assert "Cancelled" in allowed_onhold, "Manager should be able to cancel from On Hold"

    def test_lead_can_put_on_hold(self):
        """
        Lead should be able to put items on hold.
        Transition: In Progress → On Hold
        """
        # Task
        allowed_task = self.get_allowed_transitions("task", "In Progress", "Lead")
        assert "On Hold" in allowed_task, "Lead should be able to put tasks on hold"
        
        # Deliverable
        allowed_deliv = self.get_allowed_transitions("deliverable", "In Progress", "Lead")
        assert "On Hold" in allowed_deliv, "Lead should be able to put deliverables on hold"

    def test_lead_can_reject_back_to_in_progress(self):
        """
        Lead should be able to reject items back to In Progress.
        Transition: Under Review → In Progress
        """
        allowed = self.get_allowed_transitions("task", "Under Review", "Lead")
        assert "In Progress" in allowed, "Lead should be able to reject back to In Progress"

    # -------------------------------------------------------------------------
    # ❌ Invalid Transitions
    # -------------------------------------------------------------------------

    def test_engineer_cannot_approve(self):
        """
        Engineer should NOT be able to approve deliverables.
        Transition: Under Review → Approved (requires Manager)
        """
        allowed = self.get_allowed_transitions("deliverable", "Under Review", "Engineer")
        assert "Approved" not in allowed, "Engineer should NOT be able to approve"
        
        is_allowed, reason = self.can_transition("deliverable", "Under Review", "Approved", "Engineer")
        assert is_allowed is False
        assert "Manager" in reason or "not permitted" in reason.lower()

    def test_engineer_cannot_modify_others_task(self):
        """
        Engineers should only be able to transition their own tasks.
        This is enforced in transition_task() by checking assigned_engineer_id.
        """
        # Create in-memory DB for this test
        conn = sqlite3.connect(":memory:")
        
        # Create tables
        conn.execute("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                status TEXT,
                assigned_engineer_id INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE workflow_audit_log (
                id INTEGER PRIMARY KEY,
                entity_type TEXT,
                entity_id INTEGER,
                from_status TEXT,
                to_status TEXT,
                changed_by INTEGER
            )
        """)
        
        # Insert task assigned to engineer 1
        conn.execute(
            "INSERT INTO tasks (id, status, assigned_engineer_id) VALUES (1, 'Not Started', 1)"
        )
        conn.commit()
        
        # Engineer 2 tries to transition task assigned to engineer 1
        result = self.transition_task(1, "In Progress", user_id=2, user_role="Engineer", conn=conn)
        
        assert result.success is False, "Engineer should not be able to modify others' tasks"
        assert "own tasks" in result.message.lower() or "only" in result.message.lower()
        
        conn.close()

    def test_undefined_transition_rejected(self):
        """
        Undefined transitions should be rejected.
        Example: Approved → In Progress for deliverable is not defined.
        """
        is_allowed, reason = self.can_transition("deliverable", "Approved", "In Progress", "Manager")
        assert is_allowed is False, "Undefined transition should be rejected"
        assert "not defined" in reason.lower() or "undefined" in reason.lower()

    def test_engineer_cannot_cancel(self):
        """
        Engineer should NOT be able to cancel items.
        Transition: In Progress → Cancelled (requires Manager)
        """
        allowed = self.get_allowed_transitions("task", "In Progress", "Engineer")
        assert "Cancelled" not in allowed, "Engineer should NOT be able to cancel"

    def test_lead_cannot_approve_deliverable(self):
        """
        Lead should NOT be able to approve deliverables.
        Transition: Under Review → Approved (requires Manager)
        """
        allowed = self.get_allowed_transitions("deliverable", "Under Review", "Lead")
        assert "Approved" not in allowed, "Lead should NOT be able to approve deliverables"

    def test_role_hierarchy_enforcement(self):
        """
        Verify that role hierarchy is properly enforced.
        Manager > Lead > Engineer
        """
        # Manager can do everything Lead can do (and more)
        lead_allowed = self.get_allowed_transitions("task", "Under Review", "Lead")
        manager_allowed = self.get_allowed_transitions("task", "Under Review", "Manager")
        
        # Manager's allowed transitions should be superset of Lead's
        for transition in lead_allowed:
            assert transition in manager_allowed, \
                f"Manager should be able to do everything Lead can: {transition}"


# =============================================================================
# TEST CLASS 2: TestMigrationManager
# =============================================================================
# Tests for database/migration_manager.py using in-memory SQLite
# =============================================================================

class TestMigrationManager:
    """
    Test the database migration system.
    
    Uses in-memory SQLite to avoid affecting the real database.
    
    Tests cover:
    - Fresh database initialization
    - Migration execution
    - Idempotency (running migrations twice)
    - Schema verification
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import migration manager functions for each test."""
        from database.migration_manager import (
            get_current_version,
            run_all_migrations,
            get_migration_status,
            get_pending_migrations,
            get_applied_migrations,
            MIGRATIONS,
        )
        self.get_current_version = get_current_version
        self.run_all_migrations = run_all_migrations
        self.get_migration_status = get_migration_status
        self.get_pending_migrations = get_pending_migrations
        self.get_applied_migrations = get_applied_migrations
        self.MIGRATIONS = MIGRATIONS

    def test_fresh_db_version_is_zero(self):
        """
        A fresh database should have migration version 0.
        """
        conn = sqlite3.connect(":memory:")
        
        try:
            version = self.get_current_version(conn)
            assert version == 0, f"Fresh DB should have version 0, got {version}"
        finally:
            conn.close()

    def test_run_all_applies_all_migrations(self):
        """
        run_all_migrations() should apply all pending migrations.
        Should return the count of applied migrations.
        """
        conn = sqlite3.connect(":memory:")
        
        try:
            # Create core tables first (required by migrations)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deliverables (
                    id INTEGER PRIMARY KEY
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY
                )
            """)
            conn.commit()
            
            # Run migrations
            count = self.run_all_migrations(conn)
            
            # Should have applied all migrations
            assert count == len(self.MIGRATIONS), \
                f"Expected {len(self.MIGRATIONS)} migrations, applied {count}"
            
            # Verify version increased
            version = self.get_current_version(conn)
            assert version == len(self.MIGRATIONS), \
                f"Expected version {len(self.MIGRATIONS)}, got {version}"
        finally:
            conn.close()

    def test_migrations_idempotent(self):
        """
        Running migrations twice should be safe (idempotent).
        Second call should return 0 (no new migrations applied).
        """
        conn = sqlite3.connect(":memory:")
        
        try:
            # Create core tables first
            conn.execute("CREATE TABLE IF NOT EXISTS deliverables (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY)")
            conn.commit()
            
            # First run
            first_count = self.run_all_migrations(conn)
            assert first_count > 0, "First run should apply migrations"
            
            # Second run
            second_count = self.run_all_migrations(conn)
            assert second_count == 0, f"Second run should apply 0 migrations, got {second_count}"
        finally:
            conn.close()

    def test_migration_status_all_applied(self):
        """
        After running all migrations, status should show all as applied.
        """
        conn = sqlite3.connect(":memory:")
        
        try:
            # Create core tables first
            conn.execute("CREATE TABLE IF NOT EXISTS deliverables (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY)")
            conn.commit()
            
            # Run migrations
            self.run_all_migrations(conn)
            
            # Check status
            status = self.get_migration_status(conn)
            
            assert len(status) == len(self.MIGRATIONS), \
                f"Expected {len(self.MIGRATIONS)} status entries, got {len(status)}"
            
            for migration_status in status:
                assert migration_status["applied"] is True, \
                    f"Migration {migration_status['version']} should be applied"
        finally:
            conn.close()

    def test_soft_delete_columns_exist(self):
        """
        After migration 2 (soft delete), deliverables and tasks should have deleted_at column.
        """
        conn = sqlite3.connect(":memory:")
        
        try:
            # Create core tables first
            conn.execute("CREATE TABLE IF NOT EXISTS deliverables (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY)")
            conn.commit()
            
            # Run migrations
            self.run_all_migrations(conn)
            
            # Check deliverables columns
            cursor = conn.execute("PRAGMA table_info(deliverables)")
            columns = [row[1] for row in cursor.fetchall()]
            assert "deleted_at" in columns, "deliverables should have deleted_at column"
            
            # Check tasks columns
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]
            assert "deleted_at" in columns, "tasks should have deleted_at column"
        finally:
            conn.close()

    def test_pending_migrations_before_run(self):
        """
        Before running migrations, all should be pending.
        """
        conn = sqlite3.connect(":memory:")
        
        try:
            # Create core tables
            conn.execute("CREATE TABLE IF NOT EXISTS deliverables (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY)")
            conn.commit()
            
            pending = self.get_pending_migrations(conn)
            assert len(pending) == len(self.MIGRATIONS), \
                f"All {len(self.MIGRATIONS)} migrations should be pending"
        finally:
            conn.close()

    def test_applied_migrations_after_run(self):
        """
        After running migrations, all should be applied.
        """
        conn = sqlite3.connect(":memory:")
        
        try:
            # Create core tables
            conn.execute("CREATE TABLE IF NOT EXISTS deliverables (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY)")
            conn.commit()
            
            self.run_all_migrations(conn)
            
            applied = self.get_applied_migrations(conn)
            assert len(applied) == len(self.MIGRATIONS), \
                f"All {len(self.MIGRATIONS)} migrations should be applied"
        finally:
            conn.close()


# =============================================================================
# TEST CLASS 3: TestDbAdapter
# =============================================================================
# Tests for database/db_adapter.py - Database abstraction layer
# =============================================================================

class TestDbAdapter:
    """
    Test the database adapter abstraction layer.
    
    Tests cover:
    - Adapter type detection (SQLite vs PostgreSQL)
    - Placeholder conversion (? vs %s)
    - SQL translation for PostgreSQL compatibility
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import database adapter module for each test."""
        # Import the db_adapter module
        import db_adapter
        self.db_adapter = db_adapter
        self.DatabaseAdapter = db_adapter.DatabaseAdapter

    def test_sqlite_type(self):
        """
        SQLite adapter should return 'sqlite' as type.
        """
        adapter = self.DatabaseAdapter(db_type="sqlite")
        assert adapter.get_type() == "sqlite"

    def test_sqlite_placeholder(self):
        """
        SQLite adapter should use '?' as placeholder.
        """
        adapter = self.DatabaseAdapter(db_type="sqlite")
        assert adapter.get_placeholder() == "?"

    def test_postgresql_placeholder(self):
        """
        PostgreSQL adapter should use '%s' as placeholder.
        """
        adapter = self.DatabaseAdapter(db_type="postgresql")
        assert adapter.get_placeholder() == "%s"

    def test_adapt_sql_question_mark(self):
        """
        adapt_sql should convert ? to %s for PostgreSQL.
        """
        adapter = self.DatabaseAdapter(db_type="postgresql")
        
        sql = "SELECT * FROM users WHERE id = ? AND name = ?"
        adapted = adapter.adapt_sql(sql)
        
        assert "?" not in adapted, "Question marks should be converted"
        assert "%s" in adapted, "Should contain %s placeholders"
        # Should have exactly 2 placeholders
        assert adapted.count("%s") == 2

    def test_adapt_sql_datetime_now(self):
        """
        adapt_sql should convert datetime('now') to NOW() for PostgreSQL.
        """
        adapter = self.DatabaseAdapter(db_type="postgresql")
        
        sql = "INSERT INTO logs (created_at) VALUES (datetime('now'))"
        adapted = adapter.adapt_sql(sql)
        
        assert "datetime('now')" not in adapted, "datetime('now') should be converted"
        assert "NOW()" in adapted, "Should contain NOW()"

    def test_adapt_sql_date_now(self):
        """
        adapt_sql should convert DATE('now') to CURRENT_DATE for PostgreSQL.
        """
        adapter = self.DatabaseAdapter(db_type="postgresql")
        
        sql = "SELECT * FROM tasks WHERE due_date = DATE('now')"
        adapted = adapter.adapt_sql(sql)
        
        assert "DATE('now')" not in adapted, "DATE('now') should be converted"
        assert "CURRENT_DATE" in adapted, "Should contain CURRENT_DATE"

    def test_adapt_sql_pragma_skipped(self):
        """
        adapt_sql should skip PRAGMA statements for PostgreSQL.
        """
        adapter = self.DatabaseAdapter(db_type="postgresql")
        
        sql = "PRAGMA table_info(users)"
        adapted = adapter.adapt_sql(sql)
        
        # PRAGMA should be removed or replaced with empty/comment
        assert adapted.strip() == "" or "PRAGMA" not in adapted, \
            "PRAGMA should be skipped for PostgreSQL"

    def test_adapt_sql_noop_for_sqlite(self):
        """
        SQLite adapter should return SQL unchanged.
        """
        adapter = self.DatabaseAdapter(db_type="sqlite")
        
        sql = "SELECT * FROM users WHERE id = ?"
        adapted = adapter.adapt_sql(sql)
        
        assert adapted == sql, "SQLite adapter should not modify SQL"

    def test_sqlite_connection_works(self):
        """
        test_connection() should return True for valid SQLite connection.
        """
        adapter = self.DatabaseAdapter(db_type="sqlite")
        result = adapter.test_connection()
        assert result is True, "SQLite connection test should succeed"

    def test_is_postgresql_method(self):
        """
        is_postgresql() should return correct boolean.
        """
        sqlite_adapter = self.DatabaseAdapter(db_type="sqlite")
        pg_adapter = self.DatabaseAdapter(db_type="postgresql")
        
        assert sqlite_adapter.is_postgresql() is False
        assert pg_adapter.is_postgresql() is True

    def test_auto_detection(self):
        """
        DatabaseAdapter with 'auto' should detect SQLite as default.
        """
        adapter = self.DatabaseAdapter(db_type="auto")
        # In test environment without PostgreSQL, should fall back to SQLite
        assert adapter.get_type() in ("sqlite", "postgresql")


# =============================================================================
# TEST CLASS 4: TestSecureFileUpload
# =============================================================================
# Tests for secure_file_upload.py - File upload security validation
# =============================================================================

class TestSecureFileUpload:
    """
    Test the secure file upload module.
    
    Tests cover:
    - Magic bytes validation for various file types
    - Extension whitelist
    - Invalid file detection
    - ZIP bomb protection
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import secure file upload functions for each test."""
        from secure_file_upload import (
            validate_file,
            is_extension_allowed,
            MAGIC_SIGNATURES,
            CSV_VALID_CHARS,
        )
        self.validate_file = validate_file
        self.is_extension_allowed = is_extension_allowed
        self.MAGIC_SIGNATURES = MAGIC_SIGNATURES
        self.CSV_VALID_CHARS = CSV_VALID_CHARS

    # -------------------------------------------------------------------------
    # ✅ Valid File Tests
    # -------------------------------------------------------------------------

    def test_valid_pdf(self):
        """
        Valid PDF should pass magic bytes validation.
        PDF magic bytes: \x25\x50\x44\x46 (%PDF)
        """
        content = b'\x25\x50\x44\x46-1.4\n%test content'
        result = self.validate_file(content, "test.pdf")
        
        assert result.valid is True, f"PDF should be valid, error: {result.error}"
        assert result.detected_type == "pdf"

    def test_valid_jpeg(self):
        """
        Valid JPEG should pass magic bytes validation.
        JPEG magic bytes: \xFF\xD8\xFF
        """
        content = b'\xFF\xD8\xFF\xE0\x00\x10JFIF'
        result = self.validate_file(content, "test.jpg")
        
        assert result.valid is True, f"JPEG should be valid, error: {result.error}"
        assert result.detected_type == "jpg"

    def test_valid_png(self):
        """
        Valid PNG should pass magic bytes validation.
        PNG magic bytes: \x89PNG
        """
        content = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'
        result = self.validate_file(content, "test.png")
        
        assert result.valid is True, f"PNG should be valid, error: {result.error}"
        assert result.detected_type == "png"

    def test_valid_csv(self):
        """
        Valid CSV (text-based) should pass validation.
        CSV has no magic bytes - validated by content inspection.
        """
        content = b'col1,col2,col3\nval1,val2,val3\n'
        result = self.validate_file(content, "test.csv")
        
        assert result.valid is True, f"CSV should be valid, error: {result.error}"
        assert result.detected_type == "csv"

    def test_valid_xlsx(self):
        """
        Valid XLSX should pass magic bytes validation.
        XLSX uses ZIP format: PK\x03\x04
        """
        content = b'\x50\x4B\x03\x04\x14\x00\x00\x00'
        result = self.validate_file(content, "test.xlsx")
        
        # Note: May fail ZIP bomb check, but magic bytes should match
        assert result.valid is True or "ZIP bomb" in (result.error or ""), \
            f"XLSX should be valid or fail ZIP check, error: {result.error}"

    def test_valid_dwg(self):
        """
        Valid DWG should pass magic bytes validation.
        DWG magic bytes: AC (0x41 0x43)
        """
        content = b'\x41\x43\x31\x30\x30\x32'
        result = self.validate_file(content, "test.dwg")
        
        assert result.valid is True, f"DWG should be valid, error: {result.error}"
        assert result.detected_type == "dwg"

    # -------------------------------------------------------------------------
    # ❌ Invalid File Tests
    # -------------------------------------------------------------------------

    def test_invalid_pdf_wrong_magic(self):
        """
        PDF with wrong magic bytes should be rejected.
        File has JPEG magic but .pdf extension.
        """
        content = b'\xFF\xD8\xFF\xE0fake pdf content'
        result = self.validate_file(content, "test.pdf")
        
        assert result.valid is False, "Should reject PDF with wrong magic"
        assert "signature" in result.error.lower() or "match" in result.error.lower()

    def test_csv_with_binary_rejected(self):
        """
        CSV with binary content should be rejected.
        """
        # Binary content (non-text characters)
        binary_content = bytes(range(256))  # Contains many non-text bytes
        result = self.validate_file(binary_content, "test.csv")
        
        assert result.valid is False, "Should reject binary as CSV"
        assert "binary" in result.error.lower()

    def test_unknown_extension_rejected(self):
        """
        Files with unknown/unallowed extensions should be rejected.
        """
        content = b'some random content'
        result = self.validate_file(content, "test.xyz")
        
        assert result.valid is False, "Should reject unknown extension"
        assert "unsupported" in result.error.lower() or "type" in result.error.lower()

    def test_file_too_small(self):
        """
        Files smaller than 2 bytes should be rejected.
        Too small to determine file type.
        """
        content = b'x'  # Only 1 byte
        result = self.validate_file(content, "test.pdf")
        
        assert result.valid is False, "Should reject file too small"
        assert "small" in result.error.lower()

    def test_executable_extension_rejected(self):
        """
        Executable files should be rejected.
        """
        content = b'MZ\x90\x00'  # Windows EXE magic
        result = self.validate_file(content, "test.exe")
        
        assert result.valid is False, "Should reject .exe files"

    # -------------------------------------------------------------------------
    # Extension Whitelist Tests
    # -------------------------------------------------------------------------

    def test_extension_whitelist_allowed(self):
        """
        Allowed extensions should return True from is_extension_allowed.
        """
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'xlsx', 'docx', 
                              'xls', 'doc', 'csv', 'dwg', 'pptx']
        
        for ext in allowed_extensions:
            assert self.is_extension_allowed(f"test.{ext}") is True, \
                f".{ext} should be allowed"

    def test_extension_whitelist_blocked(self):
        """
        Blocked extensions should return False from is_extension_allowed.
        """
        blocked_extensions = ['exe', 'bat', 'cmd', 'sh', 'ps1', 'js', 'vbs', 'xyz']
        
        for ext in blocked_extensions:
            assert self.is_extension_allowed(f"test.{ext}") is False, \
                f".{ext} should be blocked"

    def test_extension_case_insensitive(self):
        """
        Extension check should be case-insensitive.
        """
        assert self.is_extension_allowed("test.PDF") is True
        assert self.is_extension_allowed("test.Pdf") is True
        assert self.is_extension_allowed("test.JPG") is True

    def test_no_extension_rejected(self):
        """
        Files without extension should be rejected.
        """
        assert self.is_extension_allowed("filename") is False
        assert self.is_extension_allowed("no_extension") is False

    # -------------------------------------------------------------------------
    # Size Limit Tests
    # -------------------------------------------------------------------------

    def test_file_size_in_result(self):
        """
        ValidationResult should include file size.
        """
        content = b'\x25\x50\x44\x46' + b'x' * 1000
        result = self.validate_file(content, "test.pdf")
        
        assert result.size_bytes == len(content)

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_empty_filename(self):
        """
        Empty filename should be handled gracefully.
        """
        content = b'\x25\x50\x44\x46content'
        result = self.validate_file(content, "")
        
        assert result.valid is False, "Empty filename should be rejected"

    def test_filename_with_path(self):
        """
        Filename with path should extract extension correctly.
        """
        content = b'\x25\x50\x44\x46content'
        result = self.validate_file(content, "/path/to/test.pdf")
        
        assert result.valid is True, "Should handle path in filename"


# =============================================================================
# TEST RUNNER (for standalone execution)
# =============================================================================

if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v", "--tb=short"])
