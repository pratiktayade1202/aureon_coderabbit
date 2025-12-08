# backend/fix_db_schema.py
from sqlalchemy import text
# FIX: Use absolute import so Python finds the file
from backend.database import engine 

def fix_schema():
    print("🔧 Checking Database Schema...")
    
    with engine.connect() as conn:
        conn.execute(text("COMMIT")) # Ensure we are not in a transaction block
        
        # 1. Fix broker_trades table
        try:
            print("   > Checking 'broker_trades' for missing columns...")
            conn.execute(text("ALTER TABLE broker_trades ADD COLUMN IF NOT EXISTS resolution_note TEXT;"))
            print("   ✅ Added 'resolution_note' to broker_trades")
        except Exception as e:
            print(f"   ⚠️ Could not alter broker_trades: {e}")

        # 2. Fix recon_breaks table (just in case)
        try:
            print("   > Checking 'recon_breaks' for missing columns...")
            conn.execute(text("ALTER TABLE recon_breaks ADD COLUMN IF NOT EXISTS resolution_note TEXT;"))
            print("   ✅ Added 'resolution_note' to recon_breaks")
        except Exception as e:
            print(f"   ⚠️ Could not alter recon_breaks: {e}")

        # 3. Fix nav_logs (common missing field)
        try:
            conn.execute(text("ALTER TABLE nav_logs ADD COLUMN IF NOT EXISTS source_file VARCHAR;"))
        except:
            pass
            
    print("✨ Database Schema Patch Complete.")

if __name__ == "__main__":
    fix_schema()