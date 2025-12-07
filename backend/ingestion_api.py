# backend/ingestion_api.py
import uuid
import time
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from .auth import get_current_user
from .ingestion import process_file_content

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

# Very simple in-memory job store (OK for single-process MVP)
JOBS: Dict[str, Dict[str, Any]] = {}


def _create_job_record(filename: str, user_id: str) -> str:
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "job_id": job_id,
        "filename": filename,
        "user_id": user_id,
        "status": "PENDING",
        "logs": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    return job_id


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """
    Uploads a file, runs ingestion synchronously for now, and registers a 'job'.
    Frontend gets job_id and can poll /status and /logs.
    """
    filename = file.filename or "unknown"
    job_id = _create_job_record(filename, user_id)

    try:
        content = await file.read()
        JOBS[job_id]["status"] = "RUNNING"
        JOBS[job_id]["updated_at"] = datetime.utcnow().isoformat()

        result = process_file_content(content, filename, user_id)
        JOBS[job_id]["status"] = result.get("status", "Unknown")
        JOBS[job_id]["logs"] = result.get("logs", [])
        JOBS[job_id]["updated_at"] = datetime.utcnow().isoformat()
    except Exception as e:
        JOBS[job_id]["status"] = "FAILED"
        JOBS[job_id]["logs"].append(f"❌ Fatal Ingestion Error: {e}")
        JOBS[job_id]["updated_at"] = datetime.utcnow().isoformat()
        raise HTTPException(status_code=500, detail="Ingestion failed")

    return {
        "job_id": job_id,
        "status": JOBS[job_id]["status"],
        "filename": filename,
        "created_at": JOBS[job_id]["created_at"],
        "updated_at": JOBS[job_id]["updated_at"],
        "logs": JOBS[job_id]["logs"],  # you can ignore on frontend if you want streaming-only
    }


@router.get("/status/{job_id}")
def get_ingestion_status(
    job_id: str,
    user_id: str = Depends(get_current_user),
):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your job")

    return {
        "job_id": job["job_id"],
        "filename": job["filename"],
        "status": job["status"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }


@router.get("/logs/{job_id}")
def get_ingestion_logs(
    job_id: str,
    user_id: str = Depends(get_current_user),
):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your job")

    return {
        "job_id": job["job_id"],
        "logs": job["logs"],
        "status": job["status"],
    }
