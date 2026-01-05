# backend/executor.py
from sqlalchemy import text
from .database import engine

class DBExecutor:
    @staticmethod
    def apply_settlement_plan(plan):
        items_to_process = plan.get("decisions", [])
        print(f"🔧 EXECUTOR: Processing {len(items_to_process)} AI decisions...")
        
        if not items_to_process: return False

        try:
            with engine.begin() as conn:
                for t in items_to_process:
                    t_id = t.get("id")
                    status = t.get("status")
                    reason = t.get("reason", "AI Decision")
                    cash_id = t.get("cash_id")

                    if t_id and status:
                        # 1. Update Trade
                        conn.execute(
                            text("UPDATE broker_trades SET status = :s, bank_ref = :r WHERE id = :id"),
                            {"s": status, "r": reason, "id": t_id}
                        )

                        # 2. Lock Cash (If matched)
                        if cash_id:
                            conn.execute(
                                text("UPDATE bank_txns SET status = 'USED' WHERE id = :cid"),
                                {"cid": cash_id}
                            )

                        # 3. UPDATE HOLDINGS (Accounting Logic) - UPDATED FOR TENANT ID
                        if "SETTLED" in status:
                            # Fetch trade details AND tenant_id
                            row = conn.execute(
                                text("SELECT side, symbol, quantity, price, tenant_id FROM broker_trades WHERE id = :id"),
                                {"id": t_id}
                            ).fetchone()
                            
                            if row:
                                side, symbol, qty, price, tenant_id = row
                                
                                # Calculate direction: BUY (+) / SELL (-)
                                op = 1 if str(side).upper() == "BUY" else -1
                                change_qty = qty * op
                                change_val = (qty * price) * op

                                # ATOMIC UPSERT (Replaces old if/else check)
                                conn.execute(text("""
                                    INSERT INTO holdings (date, isin, symbol, quantity, total_value, avg_cost, market_price, source_file, tenant_id)
                                    VALUES ('2025-11-24', 'UNKNOWN', :s, :q, :v, 0, 0, 'AI_AUTO', :tid)
                                    ON CONFLICT (symbol, tenant_id)
                                    DO UPDATE SET 
                                        quantity = holdings.quantity + EXCLUDED.quantity,
                                        total_value = holdings.total_value + EXCLUDED.total_value;
                                """), {
                                    "s": symbol, 
                                    "q": change_qty, 
                                    "v": change_val, 
                                    "tid": tenant_id
                                })

                        # 4. LOG THE DECISION (The Audit Trail)
                        # Ideally, recon_logs should also have tenant_id. Assuming schema allows null or auto-fetch if needed.
                        # If you updated recon_logs schema, you should pass tenant_id here too.
                        # For now, sticking to original logging structure unless specified.
                        conn.execute(text("""
                            INSERT INTO recon_logs (trade_id, cash_id, status_before, status_after, reason, agent_model)
                            VALUES (:tid, :cid, 'UNSETTLED', :stat, :rsn, 'GPT-4o-mini')
                        """), {
                            "tid": t_id,
                            "cid": cash_id,
                            "stat": status,
                            "rsn": reason
                        })

            print(f"✅ EXECUTOR SUCCESS: Database updated & actions logged.")
            return True
            
        except Exception as e:
            print(f"❌ EXECUTOR ERROR: {e}")
            return False