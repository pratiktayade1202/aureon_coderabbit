# backend/utils/secure_files.py
"""
Secure file handling utilities.

Provides:
- Secure temporary file context manager with auto-cleanup
- ZIP path traversal protection
- ZIP bomb detection
"""
import os
import io
import tempfile
import zipfile
import logging
from typing import Optional, List, Generator
from contextlib import contextmanager

from ..constants import MAX_ZIP_COMPRESSION_RATIO, MAX_UNCOMPRESSED_SIZE_BYTES

logger = logging.getLogger(__name__)


@contextmanager
def secure_temp_file(prefix: str = "aureon_", suffix: str = ".tmp"):
    """
    Context manager for secure temporary file handling.
    
    Ensures file is always cleaned up, even on errors.
    Uses system temp directory with unpredictable names.
    
    Usage:
        with secure_temp_file() as temp_path:
            with open(temp_path, "wb") as f:
                f.write(content)
            # Process file
        # File automatically deleted
    
    Args:
        prefix: File name prefix
        suffix: File name suffix
        
    Yields:
        Path to temporary file
    """
    fd = None
    path = None
    try:
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        yield path
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if path and os.path.exists(path):
            try:
                os.unlink(path)
                logger.debug(f"Cleaned up temp file: {path}")
            except OSError as e:
                logger.warning(f"Failed to cleanup temp file {path}: {e}")


def validate_zip_path(member_path: str, target_dir: str) -> Optional[str]:
    """
    Validate ZIP member path to prevent directory traversal attacks.
    
    Attacks like "../../../etc/passwd" are blocked.
    
    Args:
        member_path: Path from ZIP file member
        target_dir: Target extraction directory
        
    Returns:
        Safe absolute path if valid, None if dangerous
    """
    # Normalize the path
    normalized = os.path.normpath(member_path)
    
    # Check for absolute paths or parent directory references
    if normalized.startswith('/') or normalized.startswith('\\'):
        logger.warning(f"ZIP path traversal blocked (absolute): {member_path}")
        return None
    
    if normalized.startswith('..') or '/..' in normalized or '\\..' in normalized:
        logger.warning(f"ZIP path traversal blocked (parent ref): {member_path}")
        return None
    
    # Build and verify final path
    final_path = os.path.normpath(os.path.join(target_dir, normalized))
    abs_target = os.path.abspath(target_dir)
    
    if not final_path.startswith(abs_target):
        logger.warning(f"ZIP path traversal blocked (escape): {member_path}")
        return None
    
    return final_path


def check_zip_safety(content: bytes) -> bool:
    """
    Check if a ZIP file is safe to extract.
    
    Detects:
    - ZIP bombs (high compression ratio)
    - Excessive uncompressed size
    - Directory traversal attempts
    
    Args:
        content: ZIP file content as bytes
        
    Returns:
        True if safe, raises HTTPException if dangerous
        
    Raises:
        ValueError: If ZIP is potentially dangerous
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            compressed_size = len(content)
            uncompressed_size = sum(info.file_size for info in z.filelist)
            
            # Check for ZIP bomb (suspicious compression ratio)
            if compressed_size > 0:
                ratio = uncompressed_size / compressed_size
                if ratio > MAX_ZIP_COMPRESSION_RATIO:
                    logger.warning(
                        f"ZIP bomb detected: ratio {ratio:.1f}x "
                        f"(max {MAX_ZIP_COMPRESSION_RATIO}x)"
                    )
                    raise ValueError(
                        f"Suspicious compression ratio ({ratio:.0f}x). "
                        "File rejected for security."
                    )
            
            # Check total uncompressed size
            if uncompressed_size > MAX_UNCOMPRESSED_SIZE_BYTES:
                size_mb = uncompressed_size / (1024 * 1024)
                max_mb = MAX_UNCOMPRESSED_SIZE_BYTES / (1024 * 1024)
                logger.warning(
                    f"ZIP too large: {size_mb:.1f}MB uncompressed "
                    f"(max {max_mb:.0f}MB)"
                )
                raise ValueError(
                    f"Uncompressed size ({size_mb:.0f}MB) exceeds limit "
                    f"({max_mb:.0f}MB)."
                )
            
            # Check for path traversal in any member
            for info in z.filelist:
                if info.filename.startswith('/') or '..' in info.filename:
                    logger.warning(f"ZIP contains dangerous path: {info.filename}")
                    raise ValueError(
                        f"ZIP contains dangerous path: {info.filename}"
                    )
            
            return True
            
    except zipfile.BadZipFile as e:
        logger.warning(f"Invalid ZIP file: {e}")
        raise ValueError("Invalid or corrupted ZIP file")


def get_safe_zip_members(
    content: bytes, 
    allowed_extensions: tuple = (".csv", ".xlsx", ".xls")
) -> List[str]:
    """
    Get list of safe-to-extract members from a ZIP file.
    
    Filters out:
    - Hidden files (starting with .)
    - macOS metadata (__MACOSX)
    - Files with dangerous paths
    - Files with disallowed extensions
    
    Args:
        content: ZIP file content
        allowed_extensions: Tuple of allowed file extensions
        
    Returns:
        List of safe member names
    """
    # First check overall ZIP safety
    check_zip_safety(content)
    
    safe_members = []
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for name in z.namelist():
            # Skip directories
            if name.endswith('/'):
                continue
            
            # Skip hidden files and macOS metadata
            if name.startswith('.') or name.startswith('__MACOSX'):
                continue
            
            # Skip files in hidden directories
            if '/.' in name or '\\.' in name:
                continue
            
            # Check extension
            if not name.lower().endswith(allowed_extensions):
                continue
            
            # Verify path is safe
            if '..' not in name and not name.startswith('/'):
                safe_members.append(name)
    
    return safe_members
