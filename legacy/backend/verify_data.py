# backend/verify_data.py
import pandas as pd
from sqlalchemy import text
# FIX: Use the full path 'backend.database' instead of just 'database'
from backend.database import engine 

def run_audit():
    print("🕵️ STARTING DATA AUDIT...\n")
    
    try:
        with engine.connect() as conn:
            # 1. COUNT CHECK
            count = conn.execute(text("SELECT count(*) FROM broker_trades")).scalar()
            print(f"📊 Total Rows Found: {count}")
            
            if count == 0:
                print("❌ CRITICAL: Database is empty! (Check your .env connection)")
                return

            # 2. HALLUCINATION CHECK (Nulls)
            print("\n🔍 TEST 1: Checking for Blank/Null Data...")
            nulls = conn.execute(text("""
                SELECT count(*) FROM broker_trades 
                WHERE symbol IS NULL OR amount IS NULL OR amount = 0
            """)).scalar()
            
            if nulls == 0:
                print("✅ PASS: No missing critical data.")
            else:
                print(f"❌ FAIL: Found {nulls} rows with missing data.")

            # 3. TIME TRAVEL CHECK (Date Logic)
            print("\n🔍 TEST 2: Checking Date Ranges...")
            dates = conn.execute(text("SELECT MIN(date), MAX(date) FROM broker_trades")).fetchone()
            print(f"   📅 Date Range: {dates[0]} to {dates[1]}")
            
            # 4. DUPLICATE CHECK
            print("\n🔍 TEST 3: Checking for Duplicates...")
            dupes = conn.execute(text("""
                SELECT count(*) FROM (
                    SELECT date, symbol, amount, side, count(*) 
                    FROM broker_trades
                    GROUP BY date, symbol, amount, side
                    HAVING count(*) > 1
                ) as subquery
            """)).scalar()
            
            if dupes == 0:
                print("✅ PASS: No duplicates found.")
            else:
                print(f"⚠️ WARNING: Found {dupes} duplicate groups.")

            # 5. SPOT CHECK (Visual)
            print("\n👀 VISUAL SAMPLING (First 3 Rows):")
            sample = pd.read_sql("SELECT date, symbol, amount, side FROM broker_trades LIMIT 3", conn)
            print(sample.to_string(index=False))
            
    except Exception as e:
        print(f"❌ CONNECTION ERROR: {e}")

if __name__ == "__main__":
    run_audit()