# backend/recon_api.py
from typing import List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db
from .auth import get_current_user
from .rule_engine.orchestrator import ReconOrchestrator
from .ai_layer.agent import AIAgent 
from .models import LearningEvent, ReconLog, ReconBreak 

# Ensure default rules are loaded
try:
    from .rule_engine.domains.trade_cash import register_trade_cash_rules
    register_trade_cash_rules()
except Exception:
    pass

router = APIRouter(tags=["reconciliation"])

class ResolvePayload(BaseModel):
    note: str

# ==========================================
# 1. CORE RECON ENDPOINTS
# ==========================================

@router.post("/recon/run")
def run_reconciliation_process(
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executes the Recon Engine and RETURNS THE DATA for the grid.
    """
    orchestrator = ReconOrchestrator(db, user_id)
    
    try:
        # 1. Run the Engine (Matching + Validation)
        report = orchestrator.run_trade_recon()
        
        # 2. Fetch the UPDATED view for the Frontend
        return orchestrator.get_frontend_trade_view()

    except Exception as e:
        print(f"Recon Error: {e}")
        raise HTTPException(status_code=500, detail=f"Engine Crash: {str(e)}")

@router.get("/recon/breaks")
def get_breaks(
    user_id: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    rows = db.execute(
        text("""
            SELECT id, trade_id, rule_id, break_type, severity, amount_diff, 
                   status, resolution_note, created_at
            FROM recon_breaks
            WHERE tenant_id = :tid AND status != 'RESOLVED'
            ORDER BY created_at DESC LIMIT 500
        """),
        {"tid": user_id},
    ).mappings().all()
    return {"breaks": [dict(r) for r in rows]}

# ==========================================
# 2. MANUAL RESOLUTION
# ==========================================

@router.post("/recon/resolve-trade/{trade_id}")
def manual_resolve_trade(
    trade_id: int,
    payload: ResolvePayload,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Update Trade
    db.execute(
        text("UPDATE broker_trades SET status = 'MATCHED', resolution_note = :note WHERE id = :id AND tenant_id = :tid"),
        {"note": payload.note, "id": trade_id, "tid": user_id}
    )
    
    # 2. Close Break
    db.execute(
        text("UPDATE recon_breaks SET status = 'RESOLVED', resolution_note = :note WHERE trade_id = :id AND tenant_id = :tid"),
        {"note": payload.note, "id": trade_id, "tid": user_id}
    )
    
    db.commit()
    return {"status": "Resolved"}

# ==========================================
# 3. AI ANALYSIS
# ==========================================

@router.get("/recon/analyze/{trade_id}")
def analyze_break(
    trade_id: int,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        agent = AIAgent(db, user_id)
        return agent.analyze_single_trade(trade_id)
    except Exception as e:
        print(f"AI Analysis Failed: {e}")
        return {"status": "error", "message": "AI Agent unavailable"}

# ==========================================
# 4. AUDIT & SYSTEM
# ==========================================

@router.get("/audit-logs")
def get_audit_logs(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches the reconciliation audit trail.
    """
    try:
        # Fetch generic logs
        logs = db.execute(text("""
            SELECT * FROM recon_logs 
            WHERE tenant_id = :tid 
            ORDER BY timestamp DESC LIMIT 100
        """), {"tid": user_id}).mappings().all()
        
        # Fallback: If logs empty, show break history as audit trail
        if not logs:
             logs = db.execute(text("""
                SELECT id, trade_id, rule_id as reason, status, resolution_note, created_at as timestamp 
                FROM recon_breaks
                WHERE tenant_id = :tid
                ORDER BY created_at DESC LIMIT 100
            """), {"tid": user_id}).mappings().all()

        result = []
        for r in logs:
            row_dict = dict(r)
            if 'timestamp' in row_dict:
                row_dict['timestamp'] = str(row_dict['timestamp'])
            result.append(row_dict)
            
        return result

    except Exception as e:
        print(f"Audit Log Error: {e}")
        return []

@router.post("/system/reset")
def reset_database_endpoint(db: Session = Depends(get_db)):
    try:
        db.execute(text("TRUNCATE TABLE recon_logs, recon_breaks, broker_trades, bank_txns, nav_logs, holdings RESTART IDENTITY CASCADE"))
        db.commit()
        return {"status": "System Reset Complete"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-stats")
def get_dashboard_stats(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    total_assets = db.execute(text("SELECT COALESCE(SUM(total_value),0) FROM holdings WHERE tenant_id = :tid"), {"tid": user_id}).scalar()
    pending = db.execute(text("SELECT COUNT(*) FROM broker_trades WHERE status = 'UNSETTLED' AND tenant_id = :tid"), {"tid": user_id}).scalar()
    cash = db.execute(text("SELECT COALESCE(SUM(amount),0) FROM bank_txns WHERE status = 'UNUSED' AND tenant_id = :tid"), {"tid": user_id}).scalar()
    
    return {
        "total_assets": float(total_assets or 0),
        "pending_settlements": pending or 0,
        "available_cash": float(cash or 0),
        "usage": {"rows": 1500, "limit": 10000, "percent": 15}
    }

@router.get("/learned-rules")
def get_learned_rules(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    return []