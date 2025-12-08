from sqlalchemy import text
from backend.database import engine

# 1. DEFINE THE UNIVERSAL ID
# We will use this ID for EVERYTHING to prevent mismatches.
UNIVERSAL_TENANT_ID = "dev_tenant_01"

def align_data():
    with engine.connect() as conn:
        print(f"🔧 Aligning all data to Tenant ID: {UNIVERSAL_TENANT_ID}...")
        conn.execute(text("COMMIT"))

        # 1. Update Trades (Fix Tenant + Fix NULL Status)
        conn.execute(text(f"""
            UPDATE broker_trades 
            SET tenant_id = '{UNIVERSAL_TENANT_ID}',
                status = COALESCE(status, 'UNSETTLED')
        """))
        
        # 2. Update Bank Txns
        conn.execute(text(f"UPDATE bank_txns SET tenant_id = '{UNIVERSAL_TENANT_ID}'"))
        
        # 3. Update Breaks
        conn.execute(text(f"UPDATE recon_breaks SET tenant_id = '{UNIVERSAL_TENANT_ID}'"))
        
        # 4. Update Logs/Holdings
        conn.execute(text(f"UPDATE nav_logs SET tenant_id = '{UNIVERSAL_TENANT_ID}'"))
        conn.execute(text(f"UPDATE holdings SET tenant_id = '{UNIVERSAL_TENANT_ID}'"))
        
        conn.commit()
        print("✅ Data Alignment Complete.")

if __name__ == "__main__":
    align_data()