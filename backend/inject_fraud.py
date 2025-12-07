# backend/inject_fraud.py
import os
from sqlalchemy import text
from backend.database import engine, DATABASE_URL

def inject_bad_trade():
    print(f"🔌 CONNECTING TO: {DATABASE_URL}") 
    print("😈 INJECTING FRAUDULENT TRADE...")
    
    # Explicitly check if table exists first
    try:
        with engine.connect() as conn:
            # Check row count before
            before = conn.execute(text("SELECT count(*) FROM broker_trades")).scalar()
            print(f"📊 Rows Before: {before}")

            # Inject
            fraud_sql = text("""
                INSERT INTO broker_trades (date, symbol, quantity, price, amount, side, isin, source_file)
                VALUES ('2025-11-23', 'FRAUD-TEST-LTD', 500, 1000, 0, 'BUY', 'BAD_ISIN', 'manual_injection');
            """)
            conn.execute(fraud_sql)
            conn.commit() # Force save

            # Check row count after
            after = conn.execute(text("SELECT count(*) FROM broker_trades")).scalar()
            print(f"📊 Rows After: {after}")

            if after > before:
                print("✅ SUCCESS: Trade inserted successfully.")
            else:
                print("❌ FAIL: Row count did not increase.")

    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    inject_bad_trade()