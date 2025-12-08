# backend/ingestion_api.py

from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
import shutil
import os
import zipfile
from .database import get_db
from .auth import get_current_user
from .ingestion import process_file_content

router = APIRouter()

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    user_id: str = Depends(get_current_user)
):
    try:
        temp_name = f"temp_{file.filename}"
        with open(temp_name, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        filename = file.filename.lower()
        logs = [] 

        if filename.endswith(".zip"):
            try:
                with zipfile.ZipFile(temp_name, "r") as z:
                    for subfile in z.namelist():
                        if subfile.startswith("__") or subfile.startswith(".") or subfile.endswith("/"):
                            continue
                        with z.open(subfile) as f:
                            content = f.read()
                            result = process_file_content(content, subfile, user_id) 
                            logs.append(f"{subfile} -> {result}")
            except zipfile.BadZipFile:
                return {"status": "error", "message": "Invalid ZIP"}
        else:
            with open(temp_name, "rb") as f:
                content = f.read()
                result = process_file_content(content, filename, user_id)
                logs.append(f"{filename} -> {result}")
        
        os.remove(temp_name)
        
        # CRITICAL: Frontend looks for "logs" array
        return {
            "status": "success",
            "message": "Batch Complete",
            "logs": logs, 
            "rows": len(logs),
            "type": "Batch",
        }

    except Exception as e:
        if os.path.exists(temp_name):
            os.remove(temp_name)
        return {"status": "error", "message": f"Error: {str(e)}"}