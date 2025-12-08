from sqlalchemy import text
from backend.database import engine

with engine.connect() as conn:
    conn.execute(text("TRUNCATE TABLE recon_logs, recon_breaks, broker_trades, bank_txns, nav_logs, holdings RESTART IDENTITY CASCADE;"))
    conn.commit()
print("✅ Database Wiped Clean.")