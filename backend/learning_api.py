"""
backend/learning_api.py

Lightweight endpoints to support the Neural Core (Learner) and audit views
without changing core reconciliation semantics.
"""

from typing import Dict, Any, List
import logging
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import get_db
from .auth import get_current_user
from .models import ReconLog, LearningEvent, RuleMemory

router = APIRouter(tags=["learning"])
logger = logging.getLogger(__name__)


@router.get("/learned-rules")
def get_learned_rules(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Get all learned rules from Neural Core.
    
    Returns rules stored in rule_memory table that were learned
    from manual resolutions and AI training cycles.
    """
    try:
        rules = db.query(RuleMemory).filter(
            RuleMemory.tenant_id == user_id
        ).order_by(RuleMemory.created_at.desc()).limit(100).all()
        
        result = []
        for r in rules:
            # Parse the JSON rule definition
            rule_def = {}
            if r.learned_rule_json:
                if isinstance(r.learned_rule_json, str):
                    try:
                        rule_def = json.loads(r.learned_rule_json)
                    except json.JSONDecodeError:
                        rule_def = {"raw": r.learned_rule_json}
                else:
                    rule_def = r.learned_rule_json
            
            result.append({
                "id": r.id,
                "pattern_hash": r.pattern_hash,
                "rule": rule_def,
                "confidence": float(r.confidence_score) if r.confidence_score else 0.5,
                "times_applied": r.times_applied or 0,
                "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
            })
        
        logger.info(f"Returning {len(result)} learned rules for tenant {user_id}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to fetch learned rules: {str(e)}", exc_info=True)
        return []


@router.get("/training-examples")
def get_training_examples(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get training examples (manual resolutions) for Neural Core display.
    
    This shows what examples are available for training, allowing
    analysts to see their impact on the learning system.
    """
    try:
        # Get all manual resolution events
        events = db.query(LearningEvent).filter(
            LearningEvent.tenant_id == user_id
        ).order_by(LearningEvent.timestamp.desc()).limit(100).all()
        
        examples = []
        for e in events:
            trade_data = e.trade_data if isinstance(e.trade_data, dict) else {}
            
            examples.append({
                "id": e.id,
                "trade_id": e.trade_id,
                "status": e.status,
                "source": e.source,
                "trade_snapshot": {
                    "symbol": trade_data.get("symbol"),
                    "side": trade_data.get("side"),
                    "amount": trade_data.get("amount"),
                    "quantity": trade_data.get("quantity"),
                    "price": trade_data.get("price"),
                    "date": trade_data.get("date"),
                },
                "matched_cash_id": trade_data.get("cash_id"),
                "matched_cash_amount": trade_data.get("cash_amount"),
                "correction_notes": e.correction_notes,
                "timestamp": e.timestamp.isoformat() + "Z" if e.timestamp else None,
            })
        
        # Stats for the UI
        manual_count = sum(1 for e in events if e.source == "HUMAN_MANUAL")
        ai_count = sum(1 for e in events if e.source and "AI" in e.source.upper())
        
        logger.info(f"Returning {len(examples)} training examples for tenant {user_id}")
        
        return {
            "status": "success",
            "count": len(examples),
            "examples": examples,
            "stats": {
                "total": len(examples),
                "manual_resolutions": manual_count,
                "ai_assisted": ai_count,
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch training examples: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "count": 0,
            "examples": [],
            "message": str(e)
        }


@router.post("/learned-rules/train")
def train_learned_rules(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Trigger training of learned rules using Neural Core.
    
    This analyzes manual resolution patterns and learns new matching rules
    to improve future reconciliation accuracy.
    
    Training flow:
    1. Fetch manual resolutions from learning_events (source=HUMAN_MANUAL)
    2. Analyze patterns using AI
    3. Store learned rules in rule_memory
    """
    try:
        # First, check if there are any training examples
        example_count = db.query(LearningEvent).filter(
            LearningEvent.tenant_id == user_id,
            LearningEvent.source == "HUMAN_MANUAL"
        ).count()
        
        if example_count == 0:
            return {
                "status": "no_data",
                "message": "No manual resolutions found to train from. Resolve some trades manually first.",
                "tenant_id": user_id,
                "examples_available": 0,
            }
        
        from .learner import run_learning_cycle
        result = run_learning_cycle(user_id)
        
        # Get updated rule count
        rule_count = db.query(RuleMemory).filter(
            RuleMemory.tenant_id == user_id
        ).count()
        
        return {
            "status": result.get("status", "success"),
            "message": result.get("message", "Neural Core training completed"),
            "tenant_id": user_id,
            "examples_used": example_count,
            "new_rules": result.get("new_rules", []),
            "total_rules": rule_count,
        }
    except Exception as e:
        logger.error(f"Neural Core training failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Training failed: {str(e)}",
            "tenant_id": user_id,
        }


@router.get("/audit-logs")
def get_audit_logs(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Audit log endpoint used by LogViewerModal.

    Pulls recent entries from recon_logs and maps them into the
    UI shape. This is read-only and does not alter financial data.
    """
    logs = (
        db.query(ReconLog)
        .filter(ReconLog.tenant_id == user_id)
        .order_by(ReconLog.timestamp.desc())
        .limit(200)
        .all()
    )

    payload: List[Dict[str, Any]] = []
    for log in logs:
        # Determine action type from reason field
        action_type = "UNKNOWN"
        if log.reason:
            reason_upper = log.reason.upper()
            if "MANUAL" in reason_upper:
                action_type = "MANUAL_RESOLVE"
            elif "AUTO_RESOLVE" in reason_upper:
                action_type = "AI_AUTO_RESOLVE"
            elif "AI" in reason_upper:
                action_type = "AI_ANALYSIS"
            elif "RECON" in reason_upper:
                action_type = "RECONCILIATION"
            elif "MATCH" in reason_upper:
                action_type = "MATCH"
            elif "BREAK" in reason_upper:
                action_type = "BREAK"
            elif "HOLDINGS" in reason_upper:
                action_type = "HOLDINGS_UPDATE"
        
        payload.append(
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None,
                "status": "success",
                "action": log.reason,
                "action_type": action_type,
                "details": f"Rule {log.rule_id or 'N/A'} moved from {log.status_before} to {log.status_after}",
                "user": log.tenant_id,
                "model": log.agent_model,
                "trade_id": log.trade_id,
                "cash_id": log.cash_id,
                "context_id": (
                    f"trade:{log.trade_id}"
                    if log.trade_id
                    else f"cash:{log.cash_id}"
                    if log.cash_id
                    else None
                ),
            }
        )

    return payload


