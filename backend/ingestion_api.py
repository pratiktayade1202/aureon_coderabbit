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
from contextlib import contextmanager
from datetime import timedelta

from .database import get_db
from .auth import get_current_user
from .ingestion import process_file_content
from .config import settings
from .models import ProcessedFile, ReconLock

router = APIRouter()
logger = logging.getLogger(__name__)


# --- TENANT ISOLATION: MUTEX LOCK HELPER ---
@contextmanager
def acquire_tenant_lock(db: Session, user_id: str, process_name: str, timeout_seconds: int = 300):
    """
    Context manager to enforce single-threaded execution per tenant.
    Raises 409 if locked. Releases lock on exit.
    
    PHASE 3: TENANT ISOLATION (The Traffic Cop)
    Prevents concurrent heavy operations (upload, settlement, AI resolve, commit).
    """
    now = datetime.utcnow()
    
    # 1. Check existing lock
    lock = db.query(ReconLock).filter(ReconLock.tenant_id == user_id).first()
    
    if lock and lock.locked_until > now:
        remaining = int((lock.locked_until - now).total_seconds())
        raise HTTPException(
            status_code=409, 
            detail=f"System is busy processing '{lock.process_name}'. Please wait {remaining} seconds."
        )
    
    # 2. Acquire Lock
    expiry = now + timedelta(seconds=timeout_seconds)
    if not lock:
        lock = ReconLock(tenant_id=user_id, locked_until=expiry, process_name=process_name)
        db.add(lock)
    else:
        lock.locked_until = expiry
        lock.process_name = process_name
    
    db.commit()
    
    try:
        yield  # Allow endpoint to run
    finally:
        # 3. Release Lock (by expiring it immediately)
        # We fetch again to be safe in case of session weirdness, though usually object is attached
        lock = db.query(ReconLock).filter(ReconLock.tenant_id == user_id).first()
        if lock:
            lock.locked_until = datetime.utcnow()  # Expire it
            db.commit()

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
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ingest a file with Deduplication Protection (SHA256).
    
    PHASE 2: INGESTION SAFETY (The Fingerprint)
    - Calculates SHA256 hash before processing
    - Rejects duplicate files (409 Conflict) if already COMPLETED
    - Tracks PROCESSING state before ingestion
    - Updates to COMPLETED on success, FAILED on error
    
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
        
        # --- TENANT ISOLATION: Acquire Lock ---
        with acquire_tenant_lock(db, user_id, f"Ingesting {original_filename}"):
            # --- READ FILE & HASH (The Fingerprint) ---
            content = await file.read()
            file_size = len(content)
            file_hash = calculate_file_hash(content)
            
            # Reset cursor for processing (if needed)
            await file.seek(0)
            
            # --- STEP 2: Check for Duplicates (COMPLETED status only) ---
            existing_file = db.query(ProcessedFile).filter(
                ProcessedFile.tenant_id == user_id,
                ProcessedFile.file_hash == file_hash,
                ProcessedFile.status == "COMPLETED"  # Only block if it actually succeeded before
            ).first()
            
            if existing_file:
                logger.warning(f"Duplicate upload blocked: {original_filename} ({file_hash})")
                raise HTTPException(
                    status_code=409,
                    detail=f"Duplicate file detected. This file was already processed on {existing_file.processed_at.strftime('%Y-%m-%d %H:%M')}."
                )
            
            # --- STEP 3: Track the Attempt (PROCESSING state) ---
            processed_record = ProcessedFile(
                tenant_id=user_id,
                filename=original_filename,
                file_hash=file_hash,
                file_size=file_size,
                status="PROCESSING"
            )
            db.add(processed_record)
            db.commit()  # Commit "PROCESSING" state immediately
            
            # --- STEP 4: Run Ingestion Logic ---
            logs = []
            filename_lower = original_filename.lower()
            total_rows = 0
            
            try:
                # Process file content directly (no temp file needed for ingestion.py)
                result = process_file_content(content, original_filename, user_id)
                logs = result.get("logs", [])
                total_rows = result.get("total_rows", 0)
                
                # If ingestion didn't return total_rows, try to count from logs
                if total_rows == 0:
                    # Fallback: count rows from ingestion logs (less accurate)
                    total_rows = len([l for l in logs if "rows" in l.lower() or "processed" in l.lower()])
                
                # --- STEP 5: Mark Success ---
                processed_record.status = "COMPLETED"
                processed_record.rows_processed = total_rows
                db.add(processed_record)
                db.commit()
                
                # Calculate processing time
                end_time = datetime.utcnow()
                processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                logger.info(f"File processed: {original_filename} for tenant {user_id} in {processing_time_ms}ms ({total_rows} rows)")
                
                return UploadResponse(
                    status="success",
                    message=f"Successfully processed {original_filename}",
                    logs=logs,
                    rows=total_rows,
                    type="Batch" if filename_lower.endswith(".zip") else "Single",
                    file_hash=file_hash,
                    processing_time_ms=processing_time_ms
                )
                    
            except Exception as e:
                # --- STEP 6: Handle Failure ---
                db.rollback()  # Rollback any partial trade inserts from ingestion
                processed_record.status = "FAILED"
                processed_record.errors = str(e)[:500]  # Truncate error if too long
                db.add(processed_record)
                db.commit()
                
                logger.error(f"Ingestion failed for {original_filename}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed for {file.filename}: {str(e)}", exc_info=True)
        
        # Record failure (if we got past hash calculation)
        try:
            if 'file_hash' in locals() and 'processed_record' in locals():
                # Update existing PROCESSING record to FAILED
                processed_record.status = "FAILED"
                processed_record.errors = str(e)[:500]
                db.add(processed_record)
                db.commit()
            elif 'file_hash' in locals():
                # Create new FAILED record if PROCESSING record wasn't created
                failed_record = ProcessedFile(
                    tenant_id=user_id,
                    filename=file.filename or "unknown",
                    file_hash=file_hash,
                    file_size=len(content) if 'content' in locals() else 0,
                    status="FAILED",
                    rows_processed=0,
                    errors=str(e)[:500]
                )
                db.add(failed_record)
                db.commit()
        except Exception:
            pass  # Don't fail on logging failure
        
        raise HTTPException(
            status_code=500,
            detail=f"File processing failed: {str(e)}"
        )


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