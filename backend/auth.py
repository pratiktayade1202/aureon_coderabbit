# backend/auth.py
import os
import jwt # pip install pyjwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

security = HTTPBearer()

# --- CONFIGURATION ---
# 1. Get this from Clerk Dashboard -> API Keys -> JWT Public Key
CLERK_PEM_PUBLIC_KEY = os.getenv("CLERK_PEM_PUBLIC_KEY")

# 2. Allowed emails (RBAC Lite)
ALLOWED_EMAILS = [
    "pratik@aureon.ai", 
    "demo@ycombinator.com", 
    "pratiktayade12022001@gmail.com",
    "aureon.ai.12@gmail.com"
]

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates the Clerk JWT. 
    - Checks Signature (if Key provided).
    - Checks Expiration.
    - Checks Email Allowlist.
    """
    token = credentials.credentials
    
    try:
        # A. DECODE & VERIFY
        if CLERK_PEM_PUBLIC_KEY:
            # STRICT MODE: Verify signature using the Public Key
            payload = jwt.decode(
                token, 
                key=CLERK_PEM_PUBLIC_KEY, 
                algorithms=["RS256"],
                options={"verify_aud": False} # Clerk tokens often don't have audience set by default
            )
        else:
            # UNSAFE DEV MODE (Warn loudly)
            print("⚠️ SECURITY RISK: CLERK_PEM_PUBLIC_KEY missing. Token signature NOT verified.")
            payload = jwt.decode(token, options={"verify_signature": False})

        # B. EXTRACT CLAIMS
        user_id = payload.get("sub")
        user_email = payload.get("email") # Ensure your Clerk session token template includes 'email'

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: No User ID")

        # C. AUTHORIZATION (Allowlist)
        # Allow exact match OR any email from @ycombinator.com
        if user_email:
            is_allowed = (user_email in ALLOWED_EMAILS) or user_email.endswith("@ycombinator.com")
            if not is_allowed:
                 print(f"🚫 BLOCKED: Unauthorized user {user_email}")
                 raise HTTPException(status_code=403, detail="Access Restricted: Waitlist Only")
        
        return user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        print(f"Auth Fail: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")