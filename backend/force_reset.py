# backend/force_reset.py
import sys
import os
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import engine, Base
from backend.models import *

def nuclear_reset():
    print("☢️ STARTING NUCLEAR RESET...")
    
    with engine.connect() as conn:
        print("   - Dropping schema public CASCADE...")
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
        conn.commit()

    # COMMENT OUT OR REMOVE THIS LINE:
    # print("   - Recreating tables...")
    # Base.metadata.create_all(bind=engine)
    
    print("✅ DATABASE IS CLEAN (AND EMPTY). READY FOR ALEMBIC.")

if __name__ == "__main__":
    nuclear_reset()