from sqlalchemy import text
from backend.database import engine

def check():
    with engine.connect() as conn:
        print("\n📊 --- DATABASE STATUS ---")
        
        # 1. Check Trades
        trades = conn.execute(text("SELECT id, symbol, amount, status, tenant_id FROM broker_trades")).fetchall()
        print(f"📉 TRADES FOUND: {len(trades)}")
        for t in trades[:5]: print(f"   - ID {t.id}: {t.symbol} | {t.amount} | Status: {t.status}")

        # 2. Check Breaks
        breaks = conn.execute(text("SELECT id, rule_id, status FROM recon_breaks")).fetchall()
        print(f"\n💔 BREAKS FOUND: {len(breaks)}")
        for b in breaks[:5]: print(f"   - Break {b.id}: {b.rule_id} | Status: {b.status}")

if __name__ == "__main__":
    check()