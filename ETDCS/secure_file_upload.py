"""
================================================================================
SECURE_FILE_UPLOAD.PY - Secure File Upload with Magic Bytes Validation
================================================================================
Purpose: Replace insecure save_uploaded_file() with content-validated uploads.
Security: Manual Magic Bytes validation (no python-magic dependency).
Author: Elsewedy PSP - MEP Design Team
Version: 1.1 - Fixed tempfile import location
================================================================================
"""

import os
import zipfile
import shutil
import tempfile
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, BinaryIO
from dataclasses import dataclass

# Module logger
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION - Import from config.py or use defaults
# =============================================================================

# Default max size (should be imported from config.py)
MAX_UPLOAD_SIZE_MB = getattr(
    __import__('config', fromlist=['MAX_UPLOAD_SIZE_MB']),
    'MAX_UPLOAD_SIZE_MB',
    50  # Default: 50MB
)

# Directory paths
FILES_DIR = "files"
QUARANTINE_DIR = "uploads/quarantine"
ALLOWED_DIR = "files"

# ZIP bomb protection threshold
MAX_COMPRESSION_RATIO = 100  # Reject if uncompressed > 100x compressed

# =============================================================================
# MAGIC BYTES SIGNATURES (Manual - No External Dependencies)
# =============================================================================

MAGIC_SIGNATURES = {
    # PDF: %PDF
    'pdf': {'bytes': b'\x25\x50\x44\x46', 'offset': 0, 'len': 4},
    # JPEG: FF D8 FF
    'jpg': {'bytes': b'\xFF\xD8\xFF', 'offset': 0, 'len': 3},
    'jpeg': {'bytes': b'\xFF\xD8\xFF', 'offset': 0, 'len': 3},
    # PNG: \x89PNG
    'png': {'bytes': b'\x89\x50\x4E\x47', 'offset': 0, 'len': 4},
    # ZIP-based (XLSX, DOCX, PPTX): PK\x03\x04
    'xlsx': {'bytes': b'\x50\x4B\x03\x04', 'offset': 0, 'len': 4, 'zip_based': True},
    'docx': {'bytes': b'\x50\x4B\x03\x04', 'offset': 0, 'len': 4, 'zip_based': True},
    'pptx': {'bytes': b'\x50\x4B\x03\x04', 'offset': 0, 'len': 4, 'zip_based': True},
    # OLE-based (XLS, DOC, PPT): D0 CF 11 E0
    'xls': {'bytes': b'\xD0\xCF\x11\xE0', 'offset': 0, 'len': 4},
    'doc': {'bytes': b'\xD0\xCF\x11\xE0', 'offset': 0, 'len': 4},
    'ppt': {'bytes': b'\xD0\xCF\x11\xE0', 'offset': 0, 'len': 4},
    # DWG: AC10 or AC1.5+ variants
    'dwg': {'bytes': b'\x41\x43', 'offset': 0, 'len': 2},  # "AC"
}

# CSV has no magic bytes - validated by content inspection
CSV_VALID_CHARS = set(range(32, 127)) | {9, 10, 13}  # Printable + tab/newline


# =============================================================================
# RESULT DATA CLASS
# =============================================================================

@dataclass
class ValidationResult:
    """Result of file validation."""
    valid: bool
    error: Optional[str] = None
    detected_type: Optional[str] = None
    file_path: Optional[str] = None
    quarantine_path: Optional[str] = None
    size_bytes: int = 0


# =============================================================================
# CORE VALIDATION FUNCTION (< 60 lines as required)
# =============================================================================

def validate_file(file_bytes: bytes, filename: str, max_size_mb: int = None) -> ValidationResult:
    """
    Validate file content using Magic Bytes.
    Core validation logic - kept under 60 lines.
    """
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    max_bytes = (max_size_mb or MAX_UPLOAD_SIZE_MB) * 1024 * 1024

    # Size check
    if len(file_bytes) > max_bytes:
        return ValidationResult(False, f"File exceeds {max_size_mb or MAX_UPLOAD_SIZE_MB}MB limit")
    if len(file_bytes) < 2:
        return ValidationResult(False, "File too small to validate")

    # CSV: text-based validation
    if ext == 'csv':
        sample = file_bytes[:1024]
        non_text = sum(1 for b in sample if b not in CSV_VALID_CHARS)
        if non_text > len(sample) * 0.1:  # >10% non-text = invalid
            return ValidationResult(False, "CSV contains binary content")
        return ValidationResult(True, None, 'csv', size_bytes=len(file_bytes))

    # Check extension supported
    if ext not in MAGIC_SIGNATURES:
        return ValidationResult(False, f"Unsupported file type: .{ext}")

    sig = MAGIC_SIGNATURES[ext]
    header = file_bytes[:512]  # Read first 512 bytes for magic check

    # Magic bytes match
    if header[sig['offset']:sig['offset'] + sig['len']] != sig['bytes']:
        return ValidationResult(False, f"File content doesn't match .{ext} signature")

    # ZIP bomb check for ZIP-based formats
    if sig.get('zip_based') and not _check_zip_safe(file_bytes):
        return ValidationResult(False, "Potential ZIP bomb detected")

    return ValidationResult(True, None, ext, size_bytes=len(file_bytes))


# =============================================================================
# ZIP BOMB DETECTION
# =============================================================================

def _check_zip_safe(file_bytes: bytes) -> bool:
    """
    Check if ZIP-based file is safe (no ZIP bomb).
    Returns False if compression ratio exceeds MAX_COMPRESSION_RATIO.
    """
    try:
        # Write to temp location for inspection
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            compressed_size = len(file_bytes)
            uncompressed_size = 0

            with zipfile.ZipFile(tmp_path, 'r') as zf:
                for info in zf.infolist():
                    uncompressed_size += info.file_size
                    # Also check for suspiciously large single files
                    if info.file_size > 1024 * 1024 * 1024:  # >1GB single file
                        return False

            # Check ratio
            if compressed_size > 0:
                ratio = uncompressed_size / compressed_size
                if ratio > MAX_COMPRESSION_RATIO:
                    return False

            return True

        finally:
            os.unlink(tmp_path)

    except Exception:
        return False  # Fail closed - reject if we can't verify


# =============================================================================
# QUARANTINE FLOW
# =============================================================================

def _ensure_dirs():
    """Ensure required directories exist."""
    for d in [QUARANTINE_DIR, ALLOWED_DIR]:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)


def _quarantine_file(file_bytes: bytes, filename: str) -> str:
    """Move suspicious file to quarantine."""
    _ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{filename.replace('/', '_').replace('\\', '_')}"
    quarantine_path = os.path.join(QUARANTINE_DIR, safe_name)

    with open(quarantine_path, 'wb') as f:
        f.write(file_bytes)

    return quarantine_path


# =============================================================================
# MAIN ENTRY POINT - DROP-IN REPLACEMENT
# =============================================================================

def save_uploaded_file_secure(
    uploaded_file,
    destination_dir: str = None,
    validate_content: bool = True
) -> Tuple[Optional[str], Optional[str]]:
    """
    Secure replacement for save_uploaded_file().

    Flow: uploaded_file -> validate_magic_bytes() -> check_zip_bomb()
          -> quarantine -> move to files/ if clean

    Args:
        uploaded_file: Streamlit UploadedFile object
        destination_dir: Target directory (default: FILES_DIR)
        validate_content: Enable content validation (default: True)

    Returns:
        Tuple of (file_path, error_message)
        - On success: (path, None)
        - On failure: (None, error_msg)
    """
    if uploaded_file is None:
        return None, "No file provided"

    destination_dir = destination_dir or ALLOWED_DIR
    _ensure_dirs()

    # Read file content
    file_bytes = uploaded_file.getvalue()

    # Validate if enabled
    if validate_content:
        result = validate_file(file_bytes, uploaded_file.name)

        if not result.valid:
            # Quarantine rejected files
            quarantine_path = _quarantine_file(file_bytes, uploaded_file.name)
            return None, f"{result.error} (quarantined: {quarantine_path})"

    # Save to final destination
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{uploaded_file.name.replace('/', '_').replace('\\', '_')}"
    file_path = os.path.join(destination_dir, safe_name)

    with open(file_path, 'wb') as f:
        f.write(file_bytes)

    return file_path, None


# =============================================================================
# BACKWARD COMPATIBILITY WRAPPER
# =============================================================================

def save_uploaded_file(uploaded_file, destination_dir: str = "files") -> Optional[str]:
    """
    Drop-in replacement for existing save_uploaded_file().
    Maintains same signature for zero-code-change integration.

    Args:
        uploaded_file: Streamlit UploadedFile object
        destination_dir: Directory to save the file

    Returns:
        Full path to saved file, or None if validation/save fails
    """
    file_path, error = save_uploaded_file_secure(uploaded_file, destination_dir)
    if error:
        logger.warning("File upload rejected: %s", error)
        return None
    return file_path


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get information about a saved file."""
    if not os.path.exists(file_path):
        return {"exists": False}

    stat = os.stat(file_path)
    return {
        "exists": True,
        "path": file_path,
        "size_bytes": stat.st_size,
        "size_human": _format_size(stat.st_size),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
    }


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def clean_quarantine(older_than_days: int = 30) -> int:
    """Remove quarantined files older than specified days."""
    if not os.path.exists(QUARANTINE_DIR):
        return 0

    removed = 0
    cutoff = datetime.now().timestamp() - (older_than_days * 86400)

    for filename in os.listdir(QUARANTINE_DIR):
        path = os.path.join(QUARANTINE_DIR, filename)
        if os.path.isfile(path) and os.stat(path).st_mtime < cutoff:
            os.unlink(path)
            removed += 1

    return removed


# =============================================================================
# EXTENSION WHITELIST HELPER
# =============================================================================

ALLOWED_EXTENSIONS = set(MAGIC_SIGNATURES.keys()) | {'csv'}

def is_extension_allowed(filename: str) -> bool:
    """Check if file extension is in allowed list."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in ALLOWED_EXTENSIONS


# =============================================================================
# TEST SUITE (Run standalone to verify)
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SECURE FILE UPLOAD - TEST SUITE")
    print("=" * 60)

    # Test magic bytes detection
    test_cases = [
        ("test.pdf", b'\x25\x50\x44\x46-1.4 content', True),
        ("test.jpg", b'\xFF\xD8\xFFimage data', True),
        ("test.png", b'\x89\x50\x4E\x47PNG data', True),
        ("fake.pdf", b'\xFF\xD8\xFFfake pdf', False),  # Wrong magic
        ("test.csv", b'header1,header2\nval1,val2', True),
        ("test.xls", b'\xD0\xCF\x11\xE0OLE data', True),
        ("test.dwg", b'\x41\x43\x31\x00DWG data', True),
        ("large.pdf", b'\x25\x50\x44\x46' + b'x' * 1024, True),
        ("unknown.xyz", b'random data', False),
    ]

    print("\nValidation Tests:")
    print("-" * 40)
    for filename, content, expected in test_cases:
        result = validate_file(content, filename)
        status = "PASS" if result.valid == expected else "FAIL"
        print(f"  [{status}] {filename}: valid={result.valid}, expected={expected}")
        if result.error and not expected:
            print(f"        Error: {result.error}")

    print("\nExtension Whitelist:")
    print("-" * 40)
    for ext in ['pdf', 'jpg', 'png', 'xlsx', 'docx', 'xls', 'doc', 'csv', 'dwg', 'exe', 'bat']:
        allowed = is_extension_allowed(f"test.{ext}")
        print(f"  .{ext}: {'ALLOWED' if allowed else 'BLOCKED'}")

    print("\n" + "=" * 60)
    print("Tests complete.")
