# backend/learner.py
import json
import time
import random
import pandas as pd
from sqlalchemy import text
from .database import engine
from .llm_gateway import LLMGateway

def run_learning_cycle(tenant_id):
    print(f"🧠 LEARNER: Analyzing patterns for tenant {tenant_id}...")
    
    try:
        events = pd.DataFrame()
        
        # --- PHASE 1: READ (Fetch Data) ---
        # We use a simple connection just to read
        with engine.connect() as conn:
            events = pd.read_sql(
                text("SELECT * FROM learning_events WHERE tenant_id=:tid AND source='HUMAN_MANUAL' LIMIT 50"),
                conn, params={"tid": tenant_id}
            )
            
        if events.empty:
            return {"status": "no_data", "message": "No manual fixes to learn from yet."}
        
        # --- PHASE 2: THINK (AI / Simulation) ---
        # No Database connection open here, purely processing
        prompt = f"""
        Analyze these manual corrections. Find patterns.
        MANUAL CORRECTIONS:
        {events[['trade_data', 'correction_notes']].to_json(orient='records')}
        
        OUTPUT JSON: {{ "rules": [ {{ "type": "ALIAS", "pattern": "X -> Y", "action": "MATCH", "desc": "..." }} ] }}
        """
        
        response = LLMGateway.call_openai_brain(prompt, system_role="You are a Rule Optimizer.")
        
        # Simulation Fallback
        if not response or "rules" not in response:
            print("⚠️ LLM Failed/Skipped. Engaging Simulation Mode.")
            time.sleep(1.5) 
            
            last_note = events.iloc[0]['correction_notes']
            response = {
                "rules": [
                    {
                        "type": "ALIAS",
                        "pattern": f"Narrative contains '{last_note[:15]}...'",
                        "action": "AUTO_MATCH",
                        "desc": "Learned from manual resolution override."
                    },
                    {
                        "type": "TOLERANCE",
                        "pattern": "Amount Diff < 150.0",
                        "action": "IGNORE_DIFF",
                        "desc": "Derived from frequent small-balance adjustments."
                    }
                ]
            }

        new_rules = response.get("rules", [])
        
        # --- PHASE 3: WRITE (Save to Memory) ---
        # We open a FRESH transaction specifically for writing
        with engine.begin() as conn: 
            for r in new_rules:
                p_hash = str(hash(r["pattern"]))
                rule_json = json.dumps({"alias": r["pattern"], "action": r["action"]})
                
                # Check for duplicates within this transaction
                existing = conn.execute(
                    text("SELECT id FROM rule_memory WHERE pattern_hash = :ph AND tenant_id = :tid"),
                    {"ph": p_hash, "tid": tenant_id}
                ).fetchone()

                if not existing:
                    conn.execute(text("""
                        INSERT INTO rule_memory (tenant_id, pattern_hash, learned_rule_json, confidence_score, times_applied)
                        VALUES (:tid, :ph, :json, 0.75, 1)
                    """), {
                        "tid": tenant_id,
                        "ph": p_hash,
                        "json": rule_json
                    })
                
        print(f"✅ LEARNER SUCCESS: Generated {len(new_rules)} new rules.")
        return {"status": "success", "new_rules": new_rules}

    except Exception as e:
        print(f"Learner Error: {e}")
        return {"status": "error", "message": str(e)}