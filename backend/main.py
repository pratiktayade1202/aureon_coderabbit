# backend/main.py

import os
import shutil
import zipfile
import io
import json
import numpy as np 
from contextlib import contextmanager
from .ingestion_api import router as ingestion_router
from .recon_api import router as recon_router
from .rules_api import router as rules_router
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text, or_, and_
from sqlalchemy.exc import ProgrammingError, OperationalError
import pandas as pd
from pydantic import BaseModel

# --- IMPORTS ---
from .database import engine, Base, SessionLocal
from . import models  
from .models import (
    BrokerTrade, BankTxn, ReconStatus, Holding, 
    RuleMemory, ReconLog, ReconBreak
)
from .ingestion import process_file_content
from .auth import get_current_user
from .learner import run_learning_cycle 
from .ai_layer.agent import AIAgent
from .rule_engine.orchestrator import ReconOrchestrator
from .recon_api import router as recon_router
app.include_router(recon_router)


# Create tables at startup
#print("🛠️ CREATING DATABASE TABLES NOW...")
#Base.metadata.create_all(bind=engine)
#print("✅ TABLES CREATED.")

app = FastAPI(title="Aureon Backend")
app.include_router(ingestion_router)
app.include_router(recon_router)
app.include_router(rules_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPER: DB SESSION SCOPE ---
@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# --- HEALTH CHECK ---
@app.get("/health")
def health():
    return {"status": "ok", "engine": "Tier-1 Deterministic"}

# --- 1. SECURED UPLOAD ENDPOINT ---
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    user_id: str = Depends(get_current_user) 
):
    try:
        temp_name = f"temp_{file.filename}"
        with open(temp_name, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        filename = file.filename.lower()
        summary = []
        detailed_logs = []

        if filename.endswith(".zip"):
            try:
                with zipfile.ZipFile(temp_name, "r") as z:
                    for subfile in z.namelist():
                        if subfile.startswith("__") or subfile.startswith(".") or "/." in subfile:
                            continue
                        if subfile.endswith("/"):
                            continue
                        with z.open(subfile) as f:
                            content = f.read()
                            result_data = process_file_content(content, subfile, user_id) 
                            summary.append(f"{subfile} -> {result_data['status']}")
                            if 'logs' in result_data:
                                detailed_logs.extend(result_data['logs'])
            except zipfile.BadZipFile:
                return {"status": "error", "message": "Invalid ZIP"}
        else:
            with open(temp_name, "rb") as f:
                content = f.read()
                result_data = process_file_content(content, filename, user_id)
                summary.append(f"{filename} -> {result_data['status']}")
                if 'logs' in result_data:
                    detailed_logs.extend(result_data['logs'])

        os.remove(temp_name)
        return {
            "status": "success",
            "message": "Batch Complete",
            "details": detailed_logs,
            "summary": summary,
            "rows": len(summary),
            "type": "Batch",
        }

    except Exception as e:
        if os.path.exists(temp_name):
            os.remove(temp_name)
        return {"status": "error", "message": f"Error: {str(e)}"}

# --- 2. DASHBOARD STATS ---
@app.get("/dashboard-stats")
def dashboard_stats(user_id: str = Depends(get_current_user)):
    stats = {
        "total_assets": 0.0, 
        "pending_settlements": 0, 
        "available_cash": 0.0,
        "usage": {"rows": 0, "limit": 10000, "percent": 0}
    }
    
    try:
        with engine.connect() as conn:
            holdings_val = conn.execute(text("SELECT COALESCE(SUM(total_value),0) FROM holdings WHERE tenant_id = :tid"), {"tid": user_id}).scalar()
            cash_bal = conn.execute(text("SELECT COALESCE(SUM(amount),0) FROM bank_txns WHERE tenant_id = :tid"), {"tid": user_id}).scalar()
            
            pending = conn.execute(
                text("""
                    SELECT COUNT(*) FROM broker_trades 
                    WHERE (status IS NULL OR status = 'UNSETTLED' OR status = 'PARTIAL' OR status = 'BREAK') 
                    AND tenant_id = :tid
                """),
                {"tid": user_id}
            ).scalar()

            trade_count = conn.execute(text("SELECT COUNT(*) FROM broker_trades WHERE tenant_id = :tid"), {"tid": user_id}).scalar()
            hold_count = conn.execute(text("SELECT COUNT(*) FROM holdings WHERE tenant_id = :tid"), {"tid": user_id}).scalar()
            total_rows = (trade_count or 0) + (hold_count or 0)
            
            percent_used = min(round((total_rows / 10000) * 100), 100)

        total_auc = float(holdings_val or 0) + float(cash_bal or 0)

        return {
            "total_assets": total_auc,
            "pending_settlements": pending or 0,
            "available_cash": float(cash_bal or 0),
            "usage": {
                "rows": total_rows,
                "limit": 10000,
                "percent": percent_used
            }
        }

    except Exception as e:
        print("Stats error:", e)
        return stats

# --- 3. RESET DATABASE ---
@app.post("/reset-db")
def reset_db(user_id: str = Depends(get_current_user)):
    print(f"☢️ NUCLEAR RESET TRIGGERED BY: {user_id}")
    try:
        # 1. Brutal Reset (Drop Schema)
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE;"))
            conn.execute(text("CREATE SCHEMA public;"))
            conn.commit()
        
        # 2. Immediate Rebuild (SQLAlchemy)
        # We use SQLAlchemy to rebuild tables instantly for the UI
        # (We skip Alembic here because this is a 'Reset' button, not a migration)
        Base.metadata.create_all(bind=engine)
        
        # 3. Clear Memory
        from .rule_engine.orchestrator import RuleRegistry
        RuleRegistry.clear()
        
        print("✅ Database reset and rebuilt successfully.")
        return {"status": "success", "message": "Workspace reset complete"}
        
    except Exception as e:
        print(f"❌ Reset Failed: {e}")
        # Return 500 so the frontend knows it failed
        raise HTTPException(status_code=500, detail=str(e))

# --- 4. DATA FETCHING ---
@app.get("/get-holdings")
def get_holdings(user_id: str = Depends(get_current_user)):
    try:
        df = pd.read_sql(text("SELECT * FROM holdings WHERE tenant_id = :tid LIMIT 100"), engine.connect(), params={"tid": user_id})
        df = df.replace([np.nan, np.inf, -np.inf], None)
        return df.to_dict(orient="records")
    except Exception:
        return []

@app.get("/get-nav")
def get_nav(user_id: str = Depends(get_current_user)):
    try:
        df = pd.read_sql(text("SELECT * FROM nav_logs WHERE tenant_id = :tid LIMIT 100"), engine.connect(), params={"tid": user_id})
        df = df.replace([np.nan, np.inf, -np.inf], None)
        return df.to_dict(orient="records")
    except Exception:
        return []

# --- 5. TIER-1 ENGINE ---
@app.post("/run-engine")
def run_engine_endpoint(user_id: str = Depends(get_current_user)):
    print(f"🚀 Triggering Tier-1 Rule Engine for User: {user_id}")
    
    try:
        with session_scope() as session:
            trades = session.query(BrokerTrade).filter(
                BrokerTrade.tenant_id == user_id,
                or_(
                    BrokerTrade.status == None,
                    BrokerTrade.status == "",
                    BrokerTrade.status == ReconStatus.UNSETTLED,
                    BrokerTrade.status == ReconStatus.BREAK,
                    BrokerTrade.status == ReconStatus.PARTIAL
                )
            ).all()
            
            trades = [t for t in trades if not (t.status and "✅" in t.status)]
            
            for t in trades:
                if not t.status: t.status = ReconStatus.UNSETTLED
            
            cash = session.query(BankTxn).filter(
                BankTxn.tenant_id == user_id,
                or_(
                    BankTxn.status == "UNUSED",
                    BankTxn.status == None
                )
            ).all()
            
            if not trades:
                return [] 

            orchestrator = ReconOrchestrator(session, tenant_id=user_id)
            results = orchestrator.run_trade_cash_recon(trades, cash)
            
            return results 
            
    except Exception as e:
        print(f"❌ Engine Failed: {e}")
        return []

@app.post("/run-positions-check")
def run_positions_check_endpoint(user_id: str = Depends(get_current_user)):
    print(f"🧩 Triggering Position Reconciliation for User: {user_id}")
    try:
        with session_scope() as session:
            holdings = session.query(Holding).filter(
                Holding.tenant_id == user_id
            ).all()
            
            if not holdings:
                return []

            orchestrator = ReconOrchestrator(session, tenant_id=user_id)
            results = orchestrator.run_positions_recon(holdings)
            
            return results
    except Exception as e:
        print(f"❌ Position Engine Failed: {e}")
        return {"status": "error", "message": str(e)}

# --- 6. AI & AUDIT (UPDATED MAPPING) ---
@app.post("/run-ai-resolve")
def run_ai_resolve_endpoint(user_id: str = Depends(get_current_user)):
    print(f"🧠 Triggering Tier-2 AI Agent for User: {user_id}")
    try:
        with session_scope() as session:
            agent = AIAgent(session, tenant_id=user_id)
            results = agent.resolve_breaks(dry_run=False)
            print(f"✅ AI Agent Finished. Resolved {results['resolved']} breaks.")
            return results
    except Exception as e:
        print(f"❌ AI Agent Failed: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/audit-logs")
def get_audit_logs(user_id: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            logs = pd.read_sql(text("SELECT * FROM recon_logs WHERE tenant_id = :tid ORDER BY timestamp DESC LIMIT 50"), conn, params={"tid": user_id})
            logs = logs.replace([np.nan], None)
            if not logs.empty:
                if 'timestamp' in logs.columns:
                    logs['timestamp'] = logs['timestamp'].astype(str)
                
                # --- FIX: MAP COLUMNS FOR FRONTEND ---
                # Frontend expects: action, details, model, user
                # Backend has: rule_id, reason, agent_model, tenant_id
                logs = logs.rename(columns={
                    "rule_id": "action",
                    "reason": "details",
                    "agent_model": "model",
                    "tenant_id": "context_id"
                })
                # Add a friendly user label
                logs["user"] = "AI Agent"
                
            return logs.to_dict(orient="records")
    except Exception as e:
        print(f"Audit log error: {e}")
        return []

@app.get("/export-data")
def export_data(user_id: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT * FROM broker_trades WHERE tenant_id = :tid"), conn, params={"tid": user_id})
        
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=aureon_gold_copy.csv"
        return response
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- 7. TIER-3 CO-PILOT ---
@app.get("/analyze-break/{trade_id}")
def analyze_break_endpoint(trade_id: int, user_id: str = Depends(get_current_user)):
    try:
        with session_scope() as session:
            agent = AIAgent(session, tenant_id=user_id)
            suggestion = agent.analyze_single_trade(trade_id)
            return suggestion
    except Exception as e:
        print(f"❌ Analysis Failed: {e}")
        return {"status": "error", "message": str(e)}

# --- 8. MANUAL & SUGGESTION HANDLING (UPDATED LOGGING) ---
class ManualFixRequest(BaseModel):
    trade_id: int
    status: str
    reason: str

@app.post("/manual-resolve")
def manual_resolve(payload: ManualFixRequest, user_id: str = Depends(get_current_user)):
    try:
        with engine.begin() as conn:
            trade = conn.execute(text("SELECT id, symbol, quantity, price FROM broker_trades WHERE id=:id AND tenant_id=:tid"), {"id": payload.trade_id, "tid": user_id}).fetchone()
            
            if not trade: return {"status": "error", "message": "Trade not found"}

            # 1. Update Trade
            conn.execute(text("UPDATE broker_trades SET status = :stat, bank_ref = :reason WHERE id = :id"), {
                "stat": payload.status, "reason": payload.reason, "id": payload.trade_id
            })
            
            # 2. Add to Learner (Memory)
            trade_json = json.dumps({"id": trade.id, "symbol": trade.symbol, "amount": trade.quantity * trade.price})
            conn.execute(text("""
                INSERT INTO learning_events (tenant_id, trade_id, status, source, trade_data, correction_notes)
                VALUES (:tid, :tid_int, 'SETTLED', 'HUMAN_MANUAL', :tdata, :reason)
            """), {
                "tid": user_id, "tid_int": payload.trade_id, "tdata": trade_json, "reason": payload.reason
            })

            # 3. --- FIX: Add to Audit Trail (Visible Logs) ---
            conn.execute(text("""
                INSERT INTO recon_logs (tenant_id, trade_id, rule_id, status_before, status_after, reason, agent_model, timestamp)
                VALUES (:tid, :tid_int, 'MANUAL_USER_ACTION', 'BREAK', 'SETTLED', :reason, 'Human-Operator', NOW())
            """), {
                "tid": user_id, "tid_int": payload.trade_id, "reason": payload.reason
            })
            
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class SuggestionRequest(BaseModel):
    break_id: int
    suggestion_id: str

@app.post("/apply-suggestion")
def apply_suggestion_endpoint(payload: SuggestionRequest, user_id: str = Depends(get_current_user)):
    try:
        with session_scope() as session:
            brk = session.query(ReconBreak).filter(ReconBreak.id == payload.break_id).first()
            if not brk:
                raise HTTPException(status_code=404, detail="Break not found")
            
            if brk.trade_id:
                trade = session.query(BrokerTrade).filter(BrokerTrade.id == brk.trade_id).first()
                if trade:
                    trade.status = "✅ SETTLED (AI-CONFIRMED)"
                    trade.bank_ref = f"Resolved via Co-Pilot (Break #{brk.id})"
            
            brk.status = "RESOLVED"
            brk.resolution_note = "User accepted AI suggestion."
            
            return {"status": "success", "message": "Suggestion Applied"}
            
    except Exception as e:
        print(f"❌ Apply Suggestion Failed: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/learn-rules")
def learn_rules_endpoint(user_id: str = Depends(get_current_user)):
    return run_learning_cycle(user_id)

@app.get("/learned-rules")
def get_learned_rules(user_id: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            rules = conn.execute(
                text("SELECT * FROM rule_memory WHERE tenant_id = :tid ORDER BY confidence_score DESC"),
                {"tid": user_id}
            ).fetchall()
            
            results = []
            for r in rules:
                details = r.learned_rule_json if isinstance(r.learned_rule_json, dict) else json.loads(r.learned_rule_json)
                
                pattern_text = "Unknown Pattern"
                rule_type = "GENERAL"
                
                if "alias" in details:
                    pattern_text = details["alias"]
                    rule_type = "ALIAS"
                elif "symbol_match" in details:
                    pattern_text = details["symbol_match"]
                    rule_type = "FUZZY"
                elif "action" in details:
                    pattern_text = f"{details.get('pattern')} -> {details.get('action')}"
                    rule_type = "TOLERANCE"

                results.append({
                    "id": r.id,
                    "pattern": pattern_text,
                    "confidence": r.confidence_score,
                    "applied": r.times_applied,
                    "type": rule_type
                })
                
            return results
    except Exception as e:
        print(f"Error fetching rules: {e}")
        return []