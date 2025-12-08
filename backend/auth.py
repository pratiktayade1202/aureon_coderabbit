# backend/auth.py
import os
import jwt  # pip install pyjwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

security = HTTPBearer()

# Get this from Clerk Dashboard -> API Keys -> JWT Public Key
CLERK_PEM_PUBLIC_KEY = os.getenv("CLERK_PEM_PUBLIC_KEY")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    DEV MODE OVERRIDE:
    Ignore the actual token content. 
    Always return the same ID so the Dashboard sees the Data.
    """
    # We still require a token to be present to satisfy the Frontend's header requirement
    if not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Token")
    
    # RETURN THE UNIVERSAL ID
    return "dev_tenant_01"