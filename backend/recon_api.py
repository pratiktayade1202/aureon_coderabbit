# backend/recon_api.py
"""
Reconciliation API endpoints with proper error handling and transaction safety.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text, func, case
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import logging

from .auth import get_current_user
from .database import get_db
from .rule_engine.orchestrator import ReconOrchestrator
from .models import BrokerTrade, BankTxn, Holding, ReconBreak, ReconStatus, NavLog, ReconLog, LearningEvent
from .ai_layer.agent import AIAgent
from .utils.financial import to_decimal
from pydantic import BaseModel

router = APIRouter(tags=["reconciliation"])
logger = logging.getLogger(__name__)


class ManualResolveRequest(BaseModel):
    cash_id: Optional[int] = None
    note: Optional[str] = None


def _reset_tenant_data(db: Session, user_id: str) -> None:
    """Utility: wipes all tenant data. Used by both reset endpoints."""
    db.execute(text("DELETE FROM recon_breaks WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM recon_logs WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM bank_txns WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM holdings WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM broker_trades WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM processed_files WHERE tenant_id = :tid"), {"tid": user_id})

@router.post("/run") 
def run_reconciliation_process(
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Run trade reconciliation process.
    """
    try:
        orchestrator = ReconOrchestrator(db, user_id)
        result = orchestrator.run_trade_recon()
        
        return {
            "status": "success",
            "message": "Reconciliation completed successfully",
            "run_id": orchestrator.run_id,
            "tenant_id": user_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "matches": result.get("matches", 0),
            "breaks": result.get("breaks", 0),
            "details": result
        }
        
    except Exception as e:
        logger.error(f"Reconciliation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Reconciliation failed: {str(e)}"
        )

@router.get("/trades")
def get_trades(
    page: int = 1,
    page_size: int = 50,
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user_id: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get trades for the tenant with pagination and filtering.
    
    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        status: Filter by status (MATCHED, UNSETTLED, BREAK)
        symbol: Filter by symbol (partial match)
        date_from: Filter trades from this date (YYYY-MM-DD)
        date_to: Filter trades until this date (YYYY-MM-DD)
    
    Returns:
        Paginated response with trades and metadata
    """
    try:
        # Validate pagination params
        page = max(1, page)
        page_size = min(max(1, page_size), 100)  # Cap at 100
        offset = (page - 1) * page_size
        
        # Build query
        query = db.query(BrokerTrade).filter(BrokerTrade.tenant_id == user_id)
        
        # Apply filters
        if status:
            query = query.filter(BrokerTrade.status == status.upper())
        
        if symbol:
            query = query.filter(BrokerTrade.symbol.ilike(f"%{symbol}%"))
        
        if date_from:
            from datetime import datetime as dt
            try:
                from_date = dt.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(BrokerTrade.date >= from_date)
            except ValueError:
                pass
        
        if date_to:
            from datetime import datetime as dt
            try:
                to_date = dt.strptime(date_to, "%Y-%m-%d").date()
                query = query.filter(BrokerTrade.date <= to_date)
            except ValueError:
                pass
        
        # Get total count
        total_count = query.count()
        
        # Get paginated results
        trades = query.order_by(BrokerTrade.date.desc()).offset(offset).limit(page_size).all()
        
        # Format for frontend
        orchestrator = ReconOrchestrator(db, user_id)
        formatted_trades = []
        
        for t in trades:
            display_status = t.status or "UNSETTLED"
            
            if t.status == "UNSETTLED":
                has_break = db.query(ReconBreak).filter_by(
                    trade_id=t.id, 
                    status="OPEN"
                ).first()
                if has_break:
                    display_status = {
                        "status": "BREAK",
                        "break_type": has_break.break_type,
                        "severity": has_break.severity.value if has_break.severity else "MEDIUM",
                    }
                else:
                    display_status = {"status": "UNSETTLED"}
            else:
                display_status = {"status": t.status}
            
            formatted_trades.append({
                "id": t.id,
                "timestamp": t.date.isoformat() if t.date else None,
                "security": t.symbol or "UNKNOWN",
                "side": t.side or "UNKNOWN",
                "quantity": float(to_decimal(t.quantity)),
                "price": float(to_decimal(t.price)),
                "amount": float(to_decimal(t.amount)),
                "status": display_status,
                "bank_ref": t.bank_ref,
                "currency": t.currency or "INR",
                "source_file": t.source_file,
            })
        
        # Calculate pagination metadata
        total_pages = (total_count + page_size - 1) // page_size
        
        return {
            "status": "success",
            "data": formatted_trades,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    except Exception as e:
        logger.error(f"Failed to fetch trades: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch trades: {str(e)}"
        )


@router.get("/trades/all")
def get_all_trades(
    user_id: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get all trades for the tenant (legacy endpoint for backwards compatibility).
    Use /trades with pagination for production use.
    """
    try:
        orchestrator = ReconOrchestrator(db, user_id)
        trades = orchestrator.get_frontend_trade_view()
        return trades
    except Exception as e:
        logger.error(f"Failed to fetch trades: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch trades: {str(e)}"
        )


@router.get("/analyze/{trade_id}")
def analyze_trade_break(
    trade_id: int,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return AI analysis for a specific trade/break combination.
    Uses deterministic AIAgent math + returns structured payload for the drawer.
    """
    trade = (
        db.query(BrokerTrade)
        .filter(BrokerTrade.id == trade_id, BrokerTrade.tenant_id == user_id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    agent = AIAgent(db, user_id)
    analysis = agent.analyze_single_trade(trade_id)
    # Ensure the response always carries the trade_id for the frontend.
    analysis["trade_id"] = trade_id
    return analysis

@router.get("/breaks")
def get_breaks(
    user_id: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get reconciliation breaks.
    """
    try:
        breaks = db.query(ReconBreak).filter(
            ReconBreak.tenant_id == user_id,
            ReconBreak.status == "OPEN"
        ).all()
        
        break_list = []
        for brk in breaks:
            break_list.append({
                "id": brk.id,
                "trade_id": brk.trade_id,
                "cash_id": brk.cash_id,
                "rule_id": brk.rule_id,
                "break_type": brk.break_type,
                "severity": brk.severity.value if brk.severity else "MEDIUM",
                "amount_diff": float(brk.amount_diff) if brk.amount_diff else 0.0,
                "status": brk.status,
                "created_at": brk.created_at.isoformat() if brk.created_at else None,
            })
        
        return {
            "status": "success",
            "count": len(break_list),
            "breaks": break_list,
            "tenant_id": user_id
        }
    except Exception as e:
        logger.error(f"Failed to fetch breaks: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch breaks: {str(e)}"
        )

@router.get("/dashboard-stats")
def get_dashboard_stats(
    user_id: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get dashboard statistics with real data from database.
    Includes trades, cash, holdings (AUC), NAV, and break statistics.
    """
    try:
        # Get trade statistics
        trade_stats = db.query(
            func.count(BrokerTrade.id).label("total"),
            func.sum(case((BrokerTrade.status == "MATCHED", 1), else_=0)).label("settled"),
            func.sum(case((BrokerTrade.status.in_(["UNSETTLED", "BREAK"]), 1), else_=0)).label("unsettled"),
            func.sum(BrokerTrade.amount).label("total_amount"),
        ).filter(BrokerTrade.tenant_id == user_id).first()
        
        # Get cash statistics
        cash_stats = db.query(
            func.count(BankTxn.id).label("total"),
            func.sum(case((BankTxn.status == "MATCHED", 1), else_=0)).label("used"),
            func.sum(case((BankTxn.status == "UNUSED", 1), else_=0)).label("unused"),
            func.sum(BankTxn.amount).label("total_amount"),
        ).filter(BankTxn.tenant_id == user_id).first()
        
        # Get holdings statistics (Assets Under Custody)
        holdings_stats = db.query(
            func.count(Holding.id).label("total_positions"),
            func.sum(Holding.total_value).label("total_auc"),
            func.sum(Holding.quantity).label("total_units"),
        ).filter(Holding.tenant_id == user_id).first()
        
        # Get NAV statistics
        nav_stats = db.query(
            func.count(NavLog.id).label("total_records"),
            func.sum(NavLog.aum).label("total_aum"),
            func.max(NavLog.date).label("latest_date"),
        ).filter(NavLog.tenant_id == user_id).first()
        
        # Get break statistics
        break_stats = db.query(
            func.count(ReconBreak.id).label("total"),
            func.sum(case((ReconBreak.status == "OPEN", 1), else_=0)).label("open"),
            func.sum(case((ReconBreak.status == "RESOLVED", 1), else_=0)).label("resolved"),
        ).filter(ReconBreak.tenant_id == user_id).first()
        
        # Get last reconciliation run info (simpler query to avoid schema issues)
        try:
            last_recon = db.query(
                func.max(ReconLog.timestamp).label("last_run"),
                func.count(ReconLog.id).label("total_runs")
            ).filter(ReconLog.tenant_id == user_id).first()
        except Exception:
            last_recon = None
        
        # Calculate AUC (Assets Under Custody) - sum of holdings value
        auc = float(holdings_stats.total_auc) if holdings_stats and holdings_stats.total_auc else 0.0
        
        return {
            "status": "success",
            "tenant_id": user_id,
            "trades": {
                "total": trade_stats.total or 0,
                "settled": trade_stats.settled or 0,
                "unsettled": trade_stats.unsettled or 0,
                "total_amount": float(trade_stats.total_amount) if trade_stats.total_amount else 0.0
            },
            "cash": {
                "total": cash_stats.total or 0,
                "used": cash_stats.used or 0,
                "unused": cash_stats.unused or 0,
                "total_amount": float(cash_stats.total_amount) if cash_stats.total_amount else 0.0
            },
            "holdings": {
                "total_positions": holdings_stats.total_positions or 0 if holdings_stats else 0,
                "total_auc": auc,
                "total_units": float(holdings_stats.total_units) if holdings_stats and holdings_stats.total_units else 0.0
            },
            "nav": {
                "total_records": nav_stats.total_records or 0 if nav_stats else 0,
                "total_aum": float(nav_stats.total_aum) if nav_stats and nav_stats.total_aum else 0.0,
                "latest_date": nav_stats.latest_date.isoformat() if nav_stats and nav_stats.latest_date else None
            },
            "breaks": {
                "total": break_stats.total or 0,
                "open": break_stats.open or 0,
                "resolved": break_stats.resolved or 0
            },
            "reconciliation": {
                "last_run": last_recon.last_run.isoformat() + "Z" if last_recon and last_recon.last_run else None,
                "status": "completed" if last_recon and last_recon.last_run else "never_run",
                "total_runs": last_recon.total_runs if last_recon else 0
            },
            # Summary metrics for quick dashboard display
            "summary": {
                "auc": auc,
                "open_breaks": break_stats.open or 0,
                "match_rate": round((trade_stats.settled or 0) / max(trade_stats.total or 1, 1) * 100, 1)
            }
        }
    except Exception as e:
        logger.error(f"Failed to fetch dashboard stats: {str(e)}", exc_info=True)
        # Return safe defaults on error
        return {
            "status": "success",
            "tenant_id": user_id,
            "trades": {"total": 0, "settled": 0, "unsettled": 0, "total_amount": 0.0},
            "cash": {"total": 0, "used": 0, "unused": 0, "total_amount": 0.0},
            "holdings": {"total_positions": 0, "total_auc": 0.0, "total_units": 0.0},
            "nav": {"total_records": 0, "total_aum": 0.0, "latest_date": None},
            "breaks": {"total": 0, "open": 0, "resolved": 0},
            "reconciliation": {"last_run": None, "status": "error", "total_runs": 0},
            "summary": {"auc": 0.0, "open_breaks": 0, "match_rate": 0.0}
        }

@router.post("/position-recon")
def run_position_recon(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Run position reconciliation for holdings.
    Returns holdings data in frontend-compatible format.
    """
    try:
        holdings = db.query(Holding).filter(
            Holding.tenant_id == user_id
        ).order_by(Holding.date.desc()).all()
        
        results = []
        for h in holdings:
            results.append({
                "id": h.id,
                "date": h.date.isoformat() if h.date else None,
                "symbol": h.symbol or "UNKNOWN",
                "isin": h.isin,
                "quantity": float(h.quantity) if h.quantity else 0.0,
                "total_value": float(h.total_value) if h.total_value else 0.0,
                "avg_cost": float(h.avg_cost) if h.avg_cost else 0.0,
                "market_price": float(h.market_price) if h.market_price else 0.0,
                "source_file": h.source_file,
            })
        
        return results
    except Exception as e:
        logger.error(f"Failed to fetch positions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch positions: {str(e)}"
        )

@router.get("/nav")
def get_nav_data(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get NAV data for the tenant.
    """
    try:
        nav_records = db.query(NavLog).filter(
            NavLog.tenant_id == user_id
        ).order_by(NavLog.date.desc()).all()
        
        results = []
        for n in nav_records:
            results.append({
                "id": n.id,
                "date": n.date.isoformat() if n.date else None,
                "fund_name": n.fund_name or "Unknown Fund",
                "isin": n.isin,
                "nav_value": float(n.nav_value) if n.nav_value else 0.0,
                "aum": float(n.aum) if n.aum else 0.0,
                "source_file": n.source_file,
            })
        
        return results
    except Exception as e:
        logger.error(f"Failed to fetch NAV data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch NAV data: {str(e)}"
        )


@router.post("/ai-resolve")
def run_ai_resolve(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Run AI agent to automatically resolve breaks and match unsettled trades.
    
    This endpoint:
    1. Analyzes all OPEN breaks for potential matches
    2. Also analyzes UNSETTLED trades without breaks
    3. Uses GPT-4o-mini for reasoning on ambiguous cases
    4. Creates audit logs for all resolutions
    """
    try:
        agent = AIAgent(db, user_id, use_llm=True)  # Enable LLM reasoning
        
        resolved_count = 0
        analyzed_count = 0
        
        # PHASE 1: Handle existing breaks
        open_breaks = db.query(ReconBreak).filter(
            ReconBreak.tenant_id == user_id,
            ReconBreak.status == "OPEN"
        ).all()
        
        for brk in open_breaks:
            if brk.trade_id:
                analyzed_count += 1
                analysis = agent.analyze_single_trade(brk.trade_id)
                
                if analysis.get("found") and analysis.get("ai_suggestion", {}).get("confidence", 0) > 0.9:
                    best_candidate = analysis.get("best_candidate")
                    if best_candidate:
                        # Update trade and cash status
                        db.execute(
                            text("""
                                UPDATE broker_trades 
                                SET status = 'MATCHED', 
                                    bank_ref = :ref
                                WHERE id = :id AND tenant_id = :tid
                            """),
                            {
                                "ref": f"AI-{best_candidate.get('id', 'N/A')}",
                                "id": brk.trade_id,
                                "tid": user_id
                            }
                        )
                        
                        if best_candidate.get("id"):
                            db.execute(
                                text("""
                                    UPDATE bank_txns 
                                    SET status = 'MATCHED', trade_ref = :trade_id
                                    WHERE id = :id AND tenant_id = :tid
                                """),
                                {
                                    "id": best_candidate["id"],
                                    "trade_id": brk.trade_id,
                                    "tid": user_id
                                }
                            )
                        
                        # Mark break as resolved
                        brk.status = "RESOLVED"
                        brk.resolution_note = f"AI Auto-Resolved: {analysis.get('ai_suggestion', {}).get('explanation', '')}"
                        
                        # Create audit log
                        audit_log = ReconLog(
                            tenant_id=user_id,
                            trade_id=brk.trade_id,
                            cash_id=best_candidate.get("id"),
                            rule_id="AI_RESOLVE",
                            status_before="OPEN",
                            status_after="RESOLVED",
                            reason=f"AI matched with confidence {analysis.get('ai_suggestion', {}).get('confidence', 0):.2f}",
                            agent_model="GPT-4o-mini"
                        )
                        db.add(audit_log)
                        resolved_count += 1
        
        # PHASE 2: Also try to match UNSETTLED trades without breaks
        unsettled_trades = db.query(BrokerTrade).filter(
            BrokerTrade.tenant_id == user_id,
            BrokerTrade.status.in_(["UNSETTLED", None])
        ).limit(100).all()
        
        for trade in unsettled_trades:
            # Skip if already has an open break (handled above)
            has_break = db.query(ReconBreak).filter_by(
                trade_id=trade.id, 
                status="OPEN"
            ).first()
            if has_break:
                continue
            
            analyzed_count += 1
            analysis = agent.analyze_single_trade(trade.id)
            
            if analysis.get("found") and analysis.get("ai_suggestion", {}).get("confidence", 0) > 0.9:
                best_candidate = analysis.get("best_candidate")
                if best_candidate:
                    # Update trade and cash status
                    trade.status = "MATCHED"
                    trade.bank_ref = f"AI-{best_candidate.get('id', 'N/A')}"
                    
                    if best_candidate.get("id"):
                        db.execute(
                            text("""
                                UPDATE bank_txns 
                                SET status = 'MATCHED', trade_ref = :trade_id
                                WHERE id = :id AND tenant_id = :tid
                            """),
                            {
                                "id": best_candidate["id"],
                                "trade_id": trade.id,
                                "tid": user_id
                            }
                        )
                    
                    # Create audit log
                    audit_log = ReconLog(
                        tenant_id=user_id,
                        trade_id=trade.id,
                        cash_id=best_candidate.get("id"),
                        rule_id="AI_RESOLVE",
                        status_before="UNSETTLED",
                        status_after="MATCHED",
                        reason=f"AI matched: {analysis.get('ai_suggestion', {}).get('explanation', '')}",
                        agent_model="GPT-4o-mini"
                    )
                    db.add(audit_log)
                    resolved_count += 1
        
        db.commit()
        logger.info(f"AI Resolve: Analyzed {analyzed_count} trades, resolved {resolved_count}")
        
        return {
            "status": "success",
            "resolved": resolved_count,
            "analyzed": analyzed_count,
            "total_breaks": len(open_breaks),
            "message": f"AI analyzed {analyzed_count} trades, resolved {resolved_count}"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"AI resolve failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"AI resolve failed: {str(e)}"
        )


@router.post("/resolve-trade/{trade_id}")
def manual_resolve_trade(
    trade_id: int,
    payload: ManualResolveRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Manual resolution endpoint used by BreakDrawer.
    Allows analysts to match a trade to a cash entry or mark it settled with a note.
    """
    trade = (
        db.query(BrokerTrade)
        .filter(BrokerTrade.id == trade_id, BrokerTrade.tenant_id == user_id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    cash_record = None
    if payload.cash_id is not None:
        cash_record = (
            db.query(BankTxn)
            .filter(BankTxn.id == payload.cash_id, BankTxn.tenant_id == user_id)
            .first()
        )
        if not cash_record:
            raise HTTPException(status_code=404, detail="Cash transaction not found")

    note = payload.note or "MANUAL RESOLVE"
    try:
        trade.status = "MATCHED"
        trade.bank_ref = note

        if cash_record:
            cash_record.status = "MATCHED"
            cash_record.trade_ref = trade.id

        # Close any open breaks linked to the trade
        open_breaks = db.query(ReconBreak).filter(
            ReconBreak.trade_id == trade.id,
            ReconBreak.tenant_id == user_id,
            ReconBreak.status == "OPEN",
        ).all()
        for brk in open_breaks:
            brk.status = "RESOLVED"
            brk.resolution_note = note

        # Write learning event so Neural Core can retrain later
        learning_event = LearningEvent(
            tenant_id=user_id,
            trade_id=trade.id,
            status="MANUAL_RESOLVED",
            source="Analyst",
            trade_data={
                "symbol": trade.symbol,
                "amount": trade.amount,
                "side": trade.side,
                "quantity": trade.quantity,
            },
            correction_notes=note,
        )
        db.add(learning_event)

        db.commit()
        return {"status": "success", "message": "Trade resolved", "trade_id": trade_id}
    except Exception as e:
        db.rollback()
        logger.error(f"Manual resolve failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Manual resolve failed: {str(e)}")

@router.post("/reset-db")
def reset_database(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Reset database for the tenant (development/testing only).
    WARNING: This deletes all data for the tenant.
    """
    try:
        _reset_tenant_data(db, user_id)
        db.commit()
        return {
            "status": "success",
            "message": "Database reset successfully",
            "tenant_id": user_id
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Database reset failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database reset failed: {str(e)}"
        )


@router.post("/system/reset")
def system_reset(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Alias used by frontend system controls.
    """
    try:
        _reset_tenant_data(db, user_id)
        db.commit()
        return {
            "status": "success",
            "message": "System reset completed",
            "tenant_id": user_id
        }
    except Exception as e:
        db.rollback()
        logger.error(f"System reset failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"System reset failed: {str(e)}")

@router.get("/export-data")
def export_data(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export reconciliation data (placeholder - returns metadata).
    TODO: Implement actual CSV export
    """
    try:
        trade_count = db.query(func.count(BrokerTrade.id)).filter(
            BrokerTrade.tenant_id == user_id
        ).scalar()
        
        return {
            "status": "success",
            "tenant_id": user_id,
            "export_url": f"/api/v1/recon/exports/report_{user_id}.csv",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "format": "csv",
            "record_count": trade_count or 0,
            "message": "Export endpoint - actual file generation not yet implemented"
        }
    except Exception as e:
        logger.error(f"Export failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}"
        )
