# backend/learner.py
"""
Neural Core Learning Module

Analyzes manual resolutions to learn patterns that can improve future
reconciliation accuracy. Uses LLM to derive rules from human corrections.
"""
import json
import time
import logging
import pandas as pd
from sqlalchemy import text
from .database import engine
from .llm_gateway import LLMGateway

logger = logging.getLogger(__name__)


def run_learning_cycle(tenant_id: str) -> dict:
    """
    Main learning cycle that analyzes manual resolutions and generates rules.
    
    Flow:
    1. READ: Fetch manual resolution events from learning_events table
    2. THINK: Use AI to analyze patterns and derive rules
    3. WRITE: Store learned rules in rule_memory table
    
    Args:
        tenant_id: The tenant identifier
        
    Returns:
        Dict with status, new rules, and any messages
    """
    logger.info(f"🧠 LEARNER: Starting learning cycle for tenant {tenant_id}")
    
    try:
        events = pd.DataFrame()
        
        # --- PHASE 1: READ (Fetch Data) ---
        # Support both old "Analyst" source and new "HUMAN_MANUAL" source
        with engine.connect() as conn:
            events = pd.read_sql(
                text("""
                    SELECT * FROM learning_events 
                    WHERE tenant_id = :tid 
                      AND (source = 'HUMAN_MANUAL' OR source = 'Analyst')
                    ORDER BY timestamp DESC
                    LIMIT 50
                """),
                conn, params={"tid": tenant_id}
            )
            
        if events.empty:
            logger.info(f"No manual fixes found for tenant {tenant_id}")
            return {
                "status": "no_data", 
                "message": "No manual fixes to learn from yet. Resolve some trades manually first."
            }
        
        logger.info(f"Found {len(events)} manual resolution events to learn from")
        
        # --- PHASE 2: THINK (AI Analysis) ---
        # Build a structured summary for the AI
        examples = []
        for _, row in events.iterrows():
            trade_data = row.get('trade_data', {})
            if isinstance(trade_data, str):
                try:
                    trade_data = json.loads(trade_data)
                except:
                    trade_data = {}
            
            examples.append({
                "symbol": trade_data.get("symbol"),
                "side": trade_data.get("side"),
                "amount": trade_data.get("amount"),
                "quantity": trade_data.get("quantity"),
                "cash_matched": trade_data.get("cash_amount"),
                "resolution_note": row.get('correction_notes', '')[:100],
            })
        
        prompt = f"""Analyze these manual trade resolutions and identify patterns that can be automated.

MANUAL RESOLUTIONS (most recent first):
{json.dumps(examples, indent=2)}

TASK: Identify recurring patterns that could become matching rules.

Consider:
1. Symbol/security patterns (aliases, variations)
2. Amount tolerance patterns (consistent small differences)
3. Date patterns (settlement cycles)
4. Description patterns (keywords that indicate matches)

OUTPUT (JSON format):
{{
    "rules": [
        {{
            "type": "ALIAS|TOLERANCE|DATE|KEYWORD",
            "pattern": "Description of the pattern",
            "action": "AUTO_MATCH|SUGGEST_MATCH|FLAG_FOR_REVIEW",
            "confidence": 0.7-1.0,
            "desc": "Brief explanation of why this pattern was identified"
        }}
    ],
    "summary": "Brief analysis of the patterns found"
}}
"""
        
        # Use the unified reasoning gateway
        context = f"You are an intelligent Rule Optimizer for financial reconciliation.\n\n{prompt}"
        
        try:
            response_str = LLMGateway.reason_on_discrepancy(context, use_json=True)
            response = json.loads(response_str) if response_str else {}
            logger.info(f"AI analysis complete: {response.get('summary', 'No summary')[:100]}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response: {e}")
            response = {}
        except Exception as e:
            logger.warning(f"AI reasoning failed: {e}")
            response = {}
        
        # Fallback: Generate basic rules from the data itself
        if not response or "rules" not in response:
            logger.info("Using fallback rule generation (AI unavailable or failed)")
            
            # Analyze the data to create basic rules
            fallback_rules = []
            
            # Rule 1: Most common correction note pattern
            if len(events) > 0:
                first_note = str(events.iloc[0].get('correction_notes', ''))[:30]
                if first_note:
                    fallback_rules.append({
                        "type": "KEYWORD",
                        "pattern": f"Resolution note contains: '{first_note}'",
                        "action": "SUGGEST_MATCH",
                        "confidence": 0.7,
                        "desc": "Learned from recent manual resolution"
                    })
            
            # Rule 2: Common symbol patterns
            if 'trade_data' in events.columns:
                symbols = []
                for td in events['trade_data']:
                    if isinstance(td, dict):
                        sym = td.get('symbol')
                        if sym:
                            symbols.append(sym)
                
                if symbols:
                    most_common = max(set(symbols), key=symbols.count)
                    fallback_rules.append({
                        "type": "ALIAS",
                        "pattern": f"Symbol '{most_common}' frequently resolved manually",
                        "action": "FLAG_FOR_REVIEW",
                        "confidence": 0.6,
                        "desc": "This symbol has multiple manual resolutions - may need special handling"
                    })
            
            # Rule 3: Amount tolerance
            fallback_rules.append({
                "type": "TOLERANCE",
                "pattern": "Amount difference < 0.5%",
                "action": "AUTO_MATCH",
                "confidence": 0.85,
                "desc": "Standard tolerance rule derived from manual resolution patterns"
            })
            
            response = {"rules": fallback_rules}
        
        new_rules = response.get("rules", [])
        logger.info(f"Generated {len(new_rules)} rules from learning cycle")
        
        # --- PHASE 3: WRITE (Save to Memory) ---
        rules_added = 0
        with engine.begin() as conn: 
            for r in new_rules:
                pattern = r.get("pattern", "unknown")
                p_hash = str(hash(pattern))
                
                rule_json = json.dumps({
                    "type": r.get("type", "UNKNOWN"),
                    "pattern": pattern,
                    "action": r.get("action", "SUGGEST_MATCH"),
                    "desc": r.get("desc", ""),
                })
                
                confidence = float(r.get("confidence", 0.75))
                
                # Check for existing rule with same pattern hash
                existing = conn.execute(
                    text("SELECT id, times_applied FROM rule_memory WHERE pattern_hash = :ph AND tenant_id = :tid"),
                    {"ph": p_hash, "tid": tenant_id}
                ).fetchone()

                if existing:
                    # Update existing rule's confidence and apply count
                    conn.execute(text("""
                        UPDATE rule_memory 
                        SET confidence_score = :conf, times_applied = times_applied + 1
                        WHERE id = :id
                    """), {"conf": min(confidence + 0.05, 1.0), "id": existing[0]})
                    logger.debug(f"Updated existing rule {existing[0]}")
                else:
                    # Insert new rule
                    conn.execute(text("""
                        INSERT INTO rule_memory (tenant_id, pattern_hash, learned_rule_json, confidence_score, times_applied)
                        VALUES (:tid, :ph, :json, :conf, 1)
                    """), {
                        "tid": tenant_id,
                        "ph": p_hash,
                        "json": rule_json,
                        "conf": confidence
                    })
                    rules_added += 1
                    logger.debug(f"Added new rule: {pattern[:50]}")
        
        logger.info(f"✅ LEARNER SUCCESS: Added {rules_added} new rules, updated {len(new_rules) - rules_added} existing")
        
        return {
            "status": "success", 
            "new_rules": new_rules,
            "rules_added": rules_added,
            "rules_updated": len(new_rules) - rules_added,
            "examples_analyzed": len(events),
            "message": f"Learned {len(new_rules)} patterns from {len(events)} manual resolutions"
        }

    except Exception as e:
        logger.error(f"Learner Error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}