# backend/ingestion_api.py
"""
File ingestion API with production-ready validation and security.
"""
import os
import shutil
import zipfile
import hashlib
import logging
import tempfile
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from .database import get_db
from .auth import get_current_user
from .ingestion import process_file_content
from .config import settings
from .models import ProcessedFile

router = APIRouter()
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
MAX_FILE_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf", ".zip"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",  # Sometimes used for ZIP
}


# --- RESPONSE MODELS ---
class UploadResponse(BaseModel):
    status: str
    message: str
    logs: List[str]
    rows: int
    type: str
    file_hash: Optional[str] = None
    processing_time_ms: Optional[int] = None


class UploadHistoryItem(BaseModel):
    id: int
    filename: str
    status: str
    processed_at: str
    rows_processed: int


# --- VALIDATION HELPERS ---
def validate_file_extension(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_EXTENSIONS


def validate_file_size(file: UploadFile) -> None:
    """
    Validate file size before processing.
    Raises HTTPException if file is too large.
    """
    # Try to get size from content-length header
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB"
        )


def calculate_file_hash(content: bytes) -> str:
    """Calculate SHA256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def check_duplicate_file(db: Session, user_id: str, file_hash: str) -> Optional[ProcessedFile]:
    """Check if file has already been processed."""
    return db.query(ProcessedFile).filter(
        ProcessedFile.tenant_id == user_id,
        ProcessedFile.file_hash == file_hash
    ).first()


def sanitize_filename(filename: str) -> str:
    """Remove potentially dangerous characters from filename."""
    # Keep only alphanumeric, dots, underscores, and hyphens
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return "".join(c if c in safe_chars else "_" for c in filename)


# --- ENDPOINTS ---
@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    skip_duplicates: bool = Query(default=True, description="Skip files that have already been processed"),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and process a financial data file.
    
    Supported formats:
    - CSV (.csv)
    - Excel (.xlsx, .xls)
    - PDF (.pdf)
    - ZIP archives containing the above formats
    
    The file will be automatically categorized as:
    - Trades (broker trades, contract notes)
    - Cash (bank statements, ledgers)
    - Holdings (portfolio positions)
    - NAV (fund NAV reports)
    """
    start_time = datetime.utcnow()
    temp_path = None
    
    try:
        # --- VALIDATION ---
        # 1. Check filename
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        original_filename = file.filename
        safe_filename = sanitize_filename(original_filename)
        
        # 2. Check extension
        if not validate_file_extension(original_filename):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # 3. Check MIME type (optional, as it can be spoofed)
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
            logger.warning(f"Unexpected MIME type: {file.content_type} for {original_filename}")
        
        # 4. Check file size
        validate_file_size(file)
        
        # --- READ FILE ---
        content = await file.read()
        file_size = len(content)
        file_hash = calculate_file_hash(content)
        
        # 5. Check for duplicates
        if skip_duplicates:
            existing = check_duplicate_file(db, user_id, file_hash)
            if existing:
                return UploadResponse(
                    status="skipped",
                    message=f"File already processed on {existing.processed_at.isoformat()}",
                    logs=[f"Duplicate of: {existing.filename}"],
                    rows=existing.rows_processed,
                    type="Duplicate",
                    file_hash=file_hash
                )
        
        # --- PROCESS FILE ---
        logs = []
        filename_lower = original_filename.lower()
        
        # Create temp file in proper temp directory
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(safe_filename)[1]) as tmp:
            tmp.write(content)
            temp_path = tmp.name
        
        try:
            if filename_lower.endswith(".zip"):
                # Process ZIP archive
                try:
                    with zipfile.ZipFile(temp_path, "r") as z:
                        # Security: Check for zip bombs
                        total_uncompressed = sum(info.file_size for info in z.infolist())
                        if total_uncompressed > MAX_FILE_SIZE_BYTES * 10:
                            raise HTTPException(
                                status_code=400,
                                detail="ZIP archive is too large when uncompressed"
                            )
                        
                        for subfile in z.namelist():
                            # Skip hidden files and directories
                            if subfile.startswith(("__", ".")) or subfile.endswith("/"):
                                continue
                            
                            # Validate extension
                            if not any(subfile.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS - {".zip"}):
                                logs.append(f"{subfile} -> Skipped (unsupported format)")
                                continue
                            
                            with z.open(subfile) as f:
                                sub_content = f.read()
                                result = process_file_content(sub_content, subfile, user_id)
                                logs.append(f"{subfile} -> {result.get('status', 'Unknown')}")
                                
                except zipfile.BadZipFile:
                    raise HTTPException(status_code=400, detail="Invalid or corrupted ZIP file")
            else:
                # Process single file
                result = process_file_content(content, original_filename, user_id)
                logs.extend(result.get("logs", [f"{original_filename} -> {result.get('status', 'Unknown')}"]))
        
        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
                temp_path = None
        
        # --- RECORD PROCESSING ---
        processed_record = ProcessedFile(
            tenant_id=user_id,
            filename=original_filename,
            file_hash=file_hash,
            file_size=file_size,
            status="COMPLETED",
            rows_processed=len(logs)
        )
        db.add(processed_record)
        db.commit()
        
        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        logger.info(f"File processed: {original_filename} for tenant {user_id} in {processing_time_ms}ms")
        
        return UploadResponse(
            status="success",
            message="File processed successfully",
            logs=logs,
            rows=len(logs),
            type="Batch" if filename_lower.endswith(".zip") else "Single",
            file_hash=file_hash,
            processing_time_ms=processing_time_ms
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed for {file.filename}: {str(e)}", exc_info=True)
        
        # Record failure
        try:
            if 'file_hash' in locals():
                failed_record = ProcessedFile(
                    tenant_id=user_id,
                    filename=file.filename or "unknown",
                    file_hash=file_hash,
                    file_size=len(content) if 'content' in locals() else 0,
                    status="FAILED",
                    rows_processed=0,
                    errors=str(e)
                )
                db.add(failed_record)
                db.commit()
        except Exception:
            pass  # Don't fail on logging failure
        
        raise HTTPException(
            status_code=500,
            detail=f"File processing failed: {str(e)}"
        )
    finally:
        # Ensure cleanup
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@router.get("/upload/history")
async def get_upload_history(
    limit: int = Query(default=50, le=100),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get upload history for the current tenant.
    """
    try:
        files = db.query(ProcessedFile).filter(
            ProcessedFile.tenant_id == user_id
        ).order_by(ProcessedFile.processed_at.desc()).limit(limit).all()
        
        return {
            "status": "success",
            "count": len(files),
            "files": [
                {
                    "id": f.id,
                    "filename": f.filename,
                    "status": f.status,
                    "processed_at": f.processed_at.isoformat() if f.processed_at else None,
                    "rows_processed": f.rows_processed,
                    "file_size": f.file_size,
                    "errors": f.errors
                }
                for f in files
            ]
        }
    except Exception as e:
        logger.error(f"Failed to fetch upload history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch upload history")


@router.delete("/upload/{file_id}")
async def delete_uploaded_file(
    file_id: int,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Delete a processed file record (for re-upload).
    Note: This only removes the tracking record, not the imported data.
    """
    file_record = db.query(ProcessedFile).filter(
        ProcessedFile.id == file_id,
        ProcessedFile.tenant_id == user_id
    ).first()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File record not found")
    
    db.delete(file_record)
    db.commit()
    
    return {"status": "success", "message": "File record deleted"}