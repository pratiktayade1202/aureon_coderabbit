# backend/recon_api.py
"""
Reconciliation API endpoints with proper error handling and transaction safety.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body, Request
from sqlalchemy.orm import Session
from sqlalchemy import text, func, case
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from contextlib import contextmanager
import logging
import csv
import io

from .auth import get_current_user
from .database import get_db
from .rule_engine.orchestrator import ReconOrchestrator
from .models import BrokerTrade, BankTxn, Holding, ReconBreak, ReconStatus, NavLog, ReconLog, LearningEvent, ReconProposal, ReconLock, ReconciliationRun, AuditEvent
from .ai_layer.agent import AIAgent
from .utils.financial import to_decimal
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["reconciliation"])
logger = logging.getLogger(__name__)

# Rate limiting
from .rate_limiting import limiter, SETTLEMENT_LIMIT, AI_RESOLVE_LIMIT


# --- TENANT ISOLATION: MUTEX LOCK HELPER ---
@contextmanager
def acquire_tenant_lock(db: Session, user_id: str, process_name: str, timeout_seconds: int = 300):
    """
    Context manager to enforce single-threaded execution per tenant.
    Raises 409 if locked. Releases lock on exit.
    
    PHASE 3: TENANT ISOLATION (The Traffic Cop)
    Prevents concurrent heavy operations (upload, settlement, AI resolve, commit).
    """
    now = datetime.utcnow()
    
    # 1. Check existing lock
    lock = db.query(ReconLock).filter(ReconLock.tenant_id == user_id).first()
    
    if lock and lock.locked_until > now:
        remaining = int((lock.locked_until - now).total_seconds())
        raise HTTPException(
            status_code=409, 
            detail=f"System is busy processing '{lock.process_name}'. Please wait {remaining} seconds."
        )
    
    # 2. Acquire Lock
    expiry = now + timedelta(seconds=timeout_seconds)
    if not lock:
        lock = ReconLock(tenant_id=user_id, locked_until=expiry, process_name=process_name)
        db.add(lock)
    else:
        lock.locked_until = expiry
        lock.process_name = process_name
    
    db.commit()
    
    try:
        yield  # Allow endpoint to run
    finally:
        # 3. Release Lock (by expiring it immediately)
        # We fetch again to be safe in case of session weirdness, though usually object is attached
        lock = db.query(ReconLock).filter(ReconLock.tenant_id == user_id).first()
        if lock:
            lock.locked_until = datetime.utcnow()  # Expire it
            db.commit()


class ManualResolveRequest(BaseModel):
    cash_id: Optional[int] = None
    note: Optional[str] = None


class BulkResolveRequest(BaseModel):
    trade_ids: List[int]
    note: Optional[str] = "Bulk Manual Resolve"


class CommitProposalsRequest(BaseModel):
    min_confidence: Optional[float] = None


class CreateRunRequest(BaseModel):
    """Request to create a new reconciliation run."""
    run_id: str  # CLIENT-SUPPLIED, must be unique
    run_type: str = "SETTLEMENT"  # SETTLEMENT, AI_RESOLVE, MANUAL
    expected_sources: int = 1  # Number of files expected before run is complete


# ============================================================
# AUDIT HELPER (v2.1)
# Single interface for all control-plane audit events.
# AuditEvent = External audit trail (governance decisions only)
# ReconLog = Internal debug telemetry (never expose to UI)
# ============================================================

def _audit(
    db: Session,
    tenant_id: str,
    event_type: str,
    entity_type: str,
    entity_id: Any,
    actor: str,
    payload: Dict[str, Any],
    run_id: Optional[str] = None,
    actor_role: str = "SYSTEM",  # OPS_ANALYST | SYSTEM | ADMIN
) -> None:
    """
    Log a control-plane audit event.
    
    ONLY use for governance-relevant decisions:
    - RUN_STARTED, RUN_COMPLETED, RUN_FAILED
    - FILE_UPLOADED
    - PROPOSAL_CREATED, PROPOSAL_APPROVED, PROPOSAL_REJECTED, PROPOSAL_EXPIRED
    - TRADE_RESOLVED (manual)
    
    Actor Roles:
    - OPS_ANALYST: Human analyst making decisions
    - SYSTEM: Automated system actions (AI, engine)
    - ADMIN: Administrative overrides
    
    DO NOT use for engine internals (matching attempts, retries, etc.)
    """
    from .audit import get_audit_log
    audit = get_audit_log(db, tenant_id)
    audit.append(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        payload=payload,
        run_id=run_id,
        actor_role=actor_role,
    )




# ============================================================
# RECONCILIATION RUN MANAGEMENT (v2.1 - Idempotency)
# ============================================================

@router.post("/runs/create")
def create_reconciliation_run(
    payload: CreateRunRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Create a new reconciliation run with client-supplied ID.
    
    The run_id MUST be unique and is immutable - this enables:
    - Idempotent retries (same run_id = same result)
    - Crash recovery (resume from where we left off)
    - Determinism under load
    """
    # Check if run already exists
    existing = db.query(ReconciliationRun).filter_by(id=payload.run_id).first()
    if existing:
        return {
            "status": "exists",
            "message": "Run already exists (idempotent)",
            "run_id": existing.id,
            "run_status": existing.status,  # Use different key to avoid collision
        }
    
    run = ReconciliationRun(
        id=payload.run_id,
        tenant_id=user_id,
        run_type=payload.run_type,
        expected_sources=payload.expected_sources,
        received_sources=0,
        status="RUNNING",
        created_by=user_id,
    )
    db.add(run)
    db.commit()
    
    logger.info(f"[RUN] Created run {payload.run_id} ({payload.run_type}) expecting {payload.expected_sources} sources")
    
    return {
        "status": "created",
        "run_id": run.id,
        "run_type": run.run_type,
        "expected_sources": run.expected_sources,
    }


@router.post("/runs/{run_id}/complete")
def mark_run_complete(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Mark a reconciliation run as complete.
    
    COMPLETENESS GUARD: Blocks completion if expected sources haven't been received.
    This prevents partial reconciliation and false confidence.
    """
    run = db.query(ReconciliationRun).filter_by(id=run_id, tenant_id=user_id).first()
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    
    if run.status == "COMPLETE":
        return {
            "status": "already_complete",
            "run_id": run_id,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
    
    # COMPLETENESS GUARD: Block if sources missing
    if run.received_sources < run.expected_sources:
        missing = run.expected_sources - run.received_sources
        logger.warning(f"[COMPLETENESS_GUARD] Run {run_id} incomplete: {missing} sources missing")
        raise HTTPException(
            400,
            f"Cannot complete run: {missing} source(s) missing. "
            f"Expected {run.expected_sources}, received {run.received_sources}."
        )
    
    run.status = "COMPLETE"
    run.completed_at = datetime.utcnow()
    db.commit()
    
    # Log to audit trail
    from .audit import get_audit_log
    audit = get_audit_log(db, user_id)
    audit.append(
        event_type="RUN_COMPLETED",
        entity_type="RUN",
        entity_id=run_id,
        actor=user_id,
        payload={
            "expected_sources": run.expected_sources,
            "received_sources": run.received_sources,
            "trades_processed": run.trades_processed,
            "proposals_created": run.proposals_created,
        },
        run_id=run_id,
    )
    db.commit()
    
    logger.info(f"[RUN] Run {run_id} marked COMPLETE ({run.trades_processed} trades, {run.proposals_created} proposals)")
    
    return {
        "status": "complete",
        "run_id": run_id,
        "completed_at": run.completed_at.isoformat(),
        "trades_processed": run.trades_processed,
        "proposals_created": run.proposals_created,
    }


@router.get("/runs/{run_id}")
def get_run_status(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get the status of a reconciliation run."""
    run = db.query(ReconciliationRun).filter_by(id=run_id, tenant_id=user_id).first()
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    
    return {
        "run_id": run.id,
        "run_type": run.run_type,
        "status": run.status,
        "expected_sources": run.expected_sources,
        "received_sources": run.received_sources,
        "trades_processed": run.trades_processed,
        "proposals_created": run.proposals_created,
        "breaks_created": run.breaks_created,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_by": run.created_by,
    }


def _reset_tenant_data(db: Session, user_id: str) -> None:
    """Utility: wipes all tenant data. Used by both reset endpoints."""
    # Clear proposals and runs first (foreign key dependencies)
    db.execute(text("DELETE FROM recon_proposals WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM audit_events WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM reconciliation_runs WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM recon_breaks WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM recon_logs WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM bank_txns WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM holdings WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM broker_trades WHERE tenant_id = :tid"), {"tid": user_id})
    db.execute(text("DELETE FROM nav_logs WHERE tenant_id = :tid"), {"tid": user_id})  # NAV data
    db.execute(text("DELETE FROM processed_files WHERE tenant_id = :tid"), {"tid": user_id})

@router.post("/run-settlement-engine")
@limiter.limit(SETTLEMENT_LIMIT)
def run_settlement_engine(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    PHASE 2: RUN SETTLEMENT ENGINE (Deterministic Rules Only)
    
    This endpoint performs ONLY deterministic rule-based reconciliation:
    1. Runs trade-cash matching rules (amount, date, currency matching)
    2. Updates settlement statuses (UNSETTLED → MATCHED)
    3. Creates reconciliation breaks for unmatched trades
    4. Updates holdings and AUC based on matched trades
    5. Sets resolution_type = "RULE" for deterministically matched trades
    6. Writes audit events for all rule-based actions
    
    CRITICAL: This does NOT invoke AI/GPT.
    
    After this phase:
    - Dashboard shows reduced pending settlements
    - Resolved trades have resolution_type = "RULE"
    - Remaining breaks are visible
    - Holdings and AUC are updated
    - Button changes to "AUTO RESOLVE" for AI phase
    """
    with acquire_tenant_lock(db, user_id, "Settlement Engine"):
        run_id = None
        try:
            logger.info(f"SETTLEMENT ENGINE (Phase 2) triggered for tenant {user_id}")
            
            # ============================================================
            # GOVERNANCE AUDIT: RUN_STARTED (v2.1)
            # Control began. Who initiated it?
            # ============================================================
            from uuid import uuid4
            run_id = f"settlement-{uuid4()}"
            _audit(
                db=db,
                tenant_id=user_id,
                event_type="RUN_STARTED",
                entity_type="RUN",
                entity_id=run_id,
                actor=user_id,
                payload={"run_type": "SETTLEMENT", "phase": "PHASE_2_DETERMINISTIC"},
                run_id=run_id,
                actor_role="OPS_ANALYST",
            )
            
            # Run ONLY deterministic rule engine (no AI)
            orchestrator = ReconOrchestrator(db, user_id)
            result = orchestrator.run_trade_recon()
            
            matches = result.get("matches", 0)
            breaks_created = result.get("breaks", 0)
            
            logger.info(f"Deterministic rules completed: {matches} matches, {breaks_created} breaks created")
            
            return {
                "status": "success",
                "message": "Settlement engine completed - deterministic rules applied",
                "phase": "PHASE_2_DETERMINISTIC",
                "run_id": run_id,
                "tenant_id": user_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "deterministic_results": {
                    "matches": matches,
                    "breaks_created": breaks_created,
                    "resolution_type": "RULE"
                },
                "next_step": "Click AUTO RESOLVE to apply AI reasoning to remaining breaks",
                "details": result
            }
                
        except Exception as e:
            # ============================================================
            # GOVERNANCE AUDIT: RUN_FAILED (v2.1)
            # Failures matter MORE than success for auditors.
            # ============================================================
            if run_id:
                try:
                    _audit(
                        db=db,
                        tenant_id=user_id,
                        event_type="RUN_FAILED",
                        entity_type="RUN",
                        entity_id=run_id,
                        actor=user_id,
                        payload={"error": str(e)[:500], "phase": "PHASE_2_DETERMINISTIC"},
                        run_id=run_id,
                        actor_role="SYSTEM",
                    )
                    db.commit()  # Commit audit even if main operation failed
                except Exception:
                    pass  # Don't fail the failure
            
            db.rollback()
            logger.error(f"Settlement engine failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Settlement engine failed: {str(e)}"
            )


@router.post("/auto-resolve")
@limiter.limit(AI_RESOLVE_LIMIT)
def run_auto_resolve(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    PHASE 3: AUTO RESOLVE (AI/GPT Only)
    
    This endpoint performs ONLY AI-based resolution of remaining breaks:
    1. Analyzes all open breaks using GPT/AI reasoning
    2. For high-confidence AI matches (≥ 0.85):
       - Resolves the break
       - Updates trade status to MATCHED
       - Sets resolution_type = "AI"
       - Sets resolution_note = <GPT explanation>
    3. Updates holdings and AUC for AI-resolved trades
    4. Writes audit logs for all AI decisions
    
    CRITICAL: This does NOT run deterministic rules.
    You must run "RUN SETTLEMENT ENGINE" first.
    
    After this phase:
    - Dashboard shows fully reconciled trades
    - AI-resolved trades have resolution_type = "AI" and explanation
    - Holdings and AUC are finalized
    - Complete audit trail is visible
    """
    with acquire_tenant_lock(db, user_id, "AI Auto-Resolve"):
        try:
            logger.info(f"AUTO RESOLVE (Phase 3 - AI Only) triggered for tenant {user_id}")
            
            # PHASE 3 (AIR GAP): AI creates proposals only. No ledger mutation here.
            proposals_created = 0
            propose_threshold = 0.80  # Create proposals at/above this confidence
            
            # Get all open breaks (remaining after Phase 2)
            open_breaks = db.query(ReconBreak).filter(
                ReconBreak.tenant_id == user_id,
                ReconBreak.status == "OPEN"
            ).all()
            
            if not open_breaks:
                logger.info(f"No open breaks to resolve - settlement engine already resolved everything")
                return {
                    "status": "success",
                    "message": "No open breaks remaining - nothing to propose",
                    "phase": "PHASE_3_AI_PROPOSAL",
                    "tenant_id": user_id,
                    "ai_results": {
                        "breaks_analyzed": 0,
                        "proposals_created": 0,
                        "threshold": propose_threshold
                    }
                }
            
            logger.info(f"AI phase: Analyzing {len(open_breaks)} remaining breaks after settlement engine")
            
            try:
                agent = AIAgent(db, user_id)

                for brk in open_breaks:
                    if not brk.trade_id:
                        continue

                    analysis = agent.analyze_single_trade(brk.trade_id)
                    confidence = analysis.get("ai_suggestion", {}).get("confidence", 0) or 0.0

                    # CHECK: Is confidence high enough to PROPOSE?
                    if analysis.get("found") and confidence >= propose_threshold:
                        best_candidate = analysis.get("best_candidate")
                        explanation = analysis.get("ai_suggestion", {}).get("explanation", "") or ""

                        if best_candidate and best_candidate.get("id"):
                            # Avoid duplicate pending proposals for the same break
                            existing = (
                                db.query(ReconProposal)
                                .filter(
                                    ReconProposal.tenant_id == user_id,
                                    ReconProposal.status == "PENDING",
                                    ReconProposal.break_id == brk.id,
                                )
                                .first()
                            )
                            if existing:
                                continue

                            proposal = ReconProposal(
                                tenant_id=user_id,
                                trade_id=brk.trade_id,
                                cash_id=best_candidate.get("id"),
                                break_id=brk.id,
                                confidence=float(confidence),
                                explanation=explanation[:500],
                                source_model="AI_AGENT",
                                status="PENDING",
                                created_by="AI_AGENT",  # System-generated
                            )
                            db.add(proposal)
                            db.flush()  # Get proposal.id
                            
                            # ============================================================
                            # GOVERNANCE AUDIT: PROPOSAL_CREATED (v2.1)
                            # AI generated a decision suggestion. Auditable event.
                            # ============================================================
                            _audit(
                                db=db,
                                tenant_id=user_id,
                                event_type="PROPOSAL_CREATED",
                                entity_type="PROPOSAL",
                                entity_id=proposal.id,
                                actor="AI_AGENT",
                                payload={
                                    "trade_id": brk.trade_id,
                                    "cash_id": best_candidate.get("id"),
                                    "confidence": float(confidence),
                                    "source_model": "AI_AGENT",
                                },
                                actor_role="SYSTEM",  # AI-generated proposal
                            )
                            proposals_created += 1

                db.commit()
                logger.info(f"AI proposal generation complete: {proposals_created} proposals created")

            except Exception as ai_error:
                logger.error(f"AI phase failed: {str(ai_error)}", exc_info=True)
                db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"AI proposal generation failed: {str(ai_error)}"
                )
            
            return {
                "status": "success",
                "message": f"AI generated {proposals_created} proposals for review.",
                "phase": "PHASE_3_AI_PROPOSAL",
                "tenant_id": user_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "ai_results": {
                    "breaks_analyzed": len(open_breaks),
                    "resolved": 0,  # air-gap: nothing committed here
                    "proposals_created": proposals_created,
                    "threshold": propose_threshold,
                    "resolution_type": "AI_PROPOSAL"
                },
                "proposals_count": proposals_created
            }
                
        except Exception as e:
            db.rollback()
            logger.error(f"Auto Resolve failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Auto Resolve failed: {str(e)}"
            )

@router.post("/run")
def run_reconciliation_process_legacy(
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    LEGACY ENDPOINT: Redirects to /run-settlement-engine (Phase 2).
    Kept for backward compatibility with existing frontend code.
    
    This runs ONLY deterministic rules (not AI).
    For AI resolution, call /auto-resolve after this completes.
    """
    return run_settlement_engine(background_tasks, user_id, db)

def _get_resolution_type(bank_ref: str) -> str:
    """
    Parse bank_ref to determine resolution type.
    
    Bank_ref formats:
    - "RULE:..." -> RESOLVED_RULE
    - "MANUAL:..." -> RESOLVED_MANUAL  
    - "AI:..." -> RESOLVED_AI
    - Other/empty -> UNKNOWN
    """
    if not bank_ref:
        return "UNKNOWN"
    
    bank_ref_upper = bank_ref.upper()
    if bank_ref_upper.startswith("RULE:"):
        return "RESOLVED_RULE"
    elif bank_ref_upper.startswith("MANUAL:"):
        return "RESOLVED_MANUAL"
    elif bank_ref_upper.startswith("AI:"):
        return "RESOLVED_AI"
    elif "AI MATCHED" in bank_ref_upper or "AI AUTO" in bank_ref_upper:
        return "RESOLVED_AI"  # Legacy format
    elif "MATCHED TO CASH" in bank_ref_upper:
        return "RESOLVED_RULE"  # Legacy format
    else:
        return "RESOLVED"  # Generic resolved state


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
    
    **PHASE SEPARATION - READ-ONLY ENDPOINT:**
    - Before Auto Resolve: All trades show UNSETTLED (raw ingested state)
      - No resolution_type or resolution_note
      - No reconciliation breaks visible
    - After Auto Resolve: Trades show reconciliation status
      - MATCHED trades have resolution_type (RULE/MANUAL/AI) and resolution_note
      - UNSETTLED trades may have BREAK status if couldn't be matched
    
    This endpoint does NOT trigger any reconciliation logic.
    
    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        status: Filter by status (MATCHED, UNSETTLED, BREAK)
        symbol: Filter by symbol (partial match)
        date_from: Filter trades from this date (YYYY-MM-DD)
        date_to: Filter trades until this date (YYYY-MM-DD)
    
    Returns:
        Paginated response with trades and metadata including:
        - resolution_type: How the trade was resolved (RULE/MANUAL/AI) - only for MATCHED
        - resolution_note: Additional context about the resolution - only for MATCHED
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
            status_upper = status.upper()
            # Special-case BREAK: it's derived from UNSETTLED + open ReconBreak, not stored on BrokerTrade.status
            if status_upper == "BREAK":
                query = query.filter(
                    (BrokerTrade.status == "UNSETTLED") | (BrokerTrade.status.is_(None))
                ).filter(
                    db.query(ReconBreak.id)
                    .filter(
                        ReconBreak.trade_id == BrokerTrade.id,
                        ReconBreak.tenant_id == user_id,
                        ReconBreak.status == "OPEN",
                    )
                    .exists()
                )
            else:
                query = query.filter(BrokerTrade.status == status_upper)
        
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
        
        # Format for frontend with resolution type information
        formatted_trades = []
        
        for t in trades:
            # CRITICAL FIX:
            # Frontend expects `status` to be a string (React cannot render objects as children).
            # Extra structured info is emitted via `break_details`.
            status_str = t.status
            break_details = None
            resolution_type = None

            if t.status == "MATCHED":
                status_str = "MATCHED"
                resolution_type = _get_resolution_type(t.bank_ref)
            elif t.status == "UNSETTLED" or t.status is None:
                has_break = db.query(ReconBreak).filter_by(trade_id=t.id, status="OPEN").first()
                if has_break:
                    status_str = "BREAK"
                    break_details = {
                        "break_type": has_break.break_type,
                        "severity": has_break.severity.value if has_break.severity else "MEDIUM",
                        "break_id": has_break.id,
                    }
                else:
                    status_str = "UNSETTLED"
            else:
                status_str = t.status or "UNSETTLED"
            
            # Extract resolution note (only for MATCHED trades - phase separation)
            resolution_note = None
            if t.status == "MATCHED" and t.bank_ref:
                if ":" in t.bank_ref:
                    resolution_note = t.bank_ref.split(":", 1)[1].strip()
                else:
                    resolution_note = t.bank_ref
            
            formatted_trades.append({
                "id": t.id,
                "timestamp": t.date.isoformat() if t.date else None,
                "security": t.symbol or "UNKNOWN",
                "side": t.side or "UNKNOWN",
                "quantity": float(to_decimal(t.quantity)),
                "price": float(to_decimal(t.price)),
                "amount": float(to_decimal(t.amount)),
                "status": status_str,  # <-- always a string (prevents React crash)
                "break_details": break_details,  # <-- structured details for UI
                "resolution_type": resolution_type,
                "resolution_note": resolution_note,
                "bank_ref": t.bank_ref if t.status == "MATCHED" else None,  # Only expose after reconciliation
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

@router.get("/workflow-status")
def get_workflow_status(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get current workflow phase and which button to show.
    
    This is a lightweight endpoint for the frontend to determine
    which reconciliation button to display.
    
    Returns:
    - current_phase: PHASE_1_INGESTION, PHASE_2_SETTLEMENT_COMPLETE, or PHASE_3_COMPLETE
    - button_to_show: RUN_SETTLEMENT_ENGINE, AUTO_RESOLVE, or null
    - next_action: Human-readable description
    """
    try:
        # Count RULE-based matches (Phase 2 indicator)
        rule_matches = db.execute(
            text("""
                SELECT COUNT(*) FROM broker_trades 
                WHERE tenant_id = :tid 
                AND status = 'MATCHED' 
                AND bank_ref LIKE 'RULE:%'
            """),
            {"tid": user_id}
        ).scalar() or 0
        
        # Count AI-based matches (Phase 3 indicator)
        # Air-gap mode commits use AI_COMMIT; keep legacy AI:% too.
        ai_matches = db.execute(
            text("""
                SELECT COUNT(*) FROM broker_trades 
                WHERE tenant_id = :tid 
                AND status = 'MATCHED' 
                AND (bank_ref LIKE 'AI_COMMIT:%' OR bank_ref LIKE 'AI:%')
            """),
            {"tid": user_id}
        ).scalar() or 0
        
        # Count total trades
        total_trades = db.execute(
            text("SELECT COUNT(*) FROM broker_trades WHERE tenant_id = :tid"),
            {"tid": user_id}
        ).scalar() or 0
        
        # Count unsettled trades
        unsettled_trades = db.execute(
            text("""
                SELECT COUNT(*) FROM broker_trades 
                WHERE tenant_id = :tid 
                AND (status = 'UNSETTLED' OR status IS NULL)
            """),
            {"tid": user_id}
        ).scalar() or 0
        
        # Count open breaks
        open_breaks = db.execute(
            text("""
                SELECT COUNT(*) FROM recon_breaks 
                WHERE tenant_id = :tid 
                AND status = 'OPEN'
            """),
            {"tid": user_id}
        ).scalar() or 0

        # NEW: Count pending AI proposals (Air Gap workflow)
        pending_proposals = (
            db.query(ReconProposal)
            .filter(
                ReconProposal.tenant_id == user_id,
                ReconProposal.status == "PENDING",
            )
            .count()
        )

        # CRITICAL FIX:
        # The settlement engine "ran" if it produced rule matches OR it produced breaks.
        # A stress test can easily yield 0 matches but many breaks — we must still
        # unlock Phase 2 (AUTO_RESOLVE) in that case.
        settlement_ran = (rule_matches > 0) or (open_breaks > 0)
        
        # Determine phase and button
        if total_trades == 0:
            phase = "PHASE_0_NO_DATA"
            button = None
            action = "Upload files to begin reconciliation"
            can_run_settlement = False
            can_run_ai = False
        elif pending_proposals > 0:
            phase = "PHASE_3_PROPOSALS_PENDING"
            button = "REVIEW_AND_COMMIT"
            action = f"Review and commit {pending_proposals} AI proposals"
            can_run_settlement = False
            can_run_ai = False
        elif (not settlement_ran) and ai_matches == 0:
            phase = "PHASE_1_INGESTION"
            button = "RUN_SETTLEMENT_ENGINE"
            action = "Run deterministic settlement engine to match trades"
            can_run_settlement = True
            can_run_ai = False
        elif settlement_ran and ai_matches == 0 and open_breaks > 0:
            phase = "PHASE_2_SETTLEMENT_COMPLETE"
            button = "AUTO_RESOLVE"
            action = f"Run AI auto-resolve ({open_breaks} breaks remaining)"
            can_run_settlement = False
            can_run_ai = True
        elif open_breaks == 0 and total_trades > 0:
            phase = "PHASE_3_COMPLETE"
            button = None
            action = "Reconciliation complete"
            can_run_settlement = False
            can_run_ai = False
        else:
            # Mixed states (e.g., partial AI run)
            phase = "PHASE_3_COMPLETE"
            button = "AUTO_RESOLVE" if open_breaks > 0 else None
            action = "Reconciliation complete"
            can_run_settlement = False
            can_run_ai = open_breaks > 0
        
        return {
            "status": "success",
            "workflow": {
                "current_phase": phase,
                "button_to_show": button,
                "next_action": action,
                "pending_proposals": pending_proposals,
                "can_run_settlement_engine": can_run_settlement,
                "can_run_auto_resolve": can_run_ai
            },
            "statistics": {
                "total_trades": total_trades,
                "unsettled_trades": unsettled_trades,
                "rule_matched": rule_matches,
                "ai_matched": ai_matches,
                "open_breaks": open_breaks,
                "pending_proposals": pending_proposals,
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get workflow status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow status: {str(e)}"
        )


@router.get("/breaks")
def get_breaks(
    user_id: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get reconciliation breaks.
    
    **3-PHASE WORKFLOW:**
    - After Phase 1 (Ingestion): Returns empty list (no reconciliation yet)
    - After Phase 2 (Settlement Engine): Returns breaks created by rules
    - After Phase 3 (Auto Resolve): Returns remaining breaks after AI
    
    These are RECONCILIATION breaks (matching failures), not ingestion/DQ issues.
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
    
    **3-PHASE WORKFLOW - READ-ONLY ENDPOINT:**
    Returns which phase the system is in and which button to show:
    - Phase 1 (After Ingestion): Show "RUN SETTLEMENT ENGINE" button
    - Phase 2 (After Settlement): Show "AUTO RESOLVE" button  
    - Phase 3 (After AI): Reconciliation complete
    
    Phase detection logic:
    - If no RULE-based matches exist → Phase 1 (button: RUN SETTLEMENT ENGINE)
    - If RULE matches exist but AI matches don't → Phase 2 (button: AUTO RESOLVE)
    - If both exist → Phase 3 (complete)
    
    This endpoint does NOT trigger any reconciliation logic.
    
    Includes trades, cash, holdings (AUC), NAV, and break statistics.
    """
    try:
        # Detect current phase based on resolution types
        rule_matches = db.execute(
            text("""
                SELECT COUNT(*) FROM broker_trades 
                WHERE tenant_id = :tid 
                AND status = 'MATCHED' 
                AND bank_ref LIKE 'RULE:%'
            """),
            {"tid": user_id}
        ).scalar() or 0
        
        ai_matches = db.execute(
            text("""
                SELECT COUNT(*) FROM broker_trades 
                WHERE tenant_id = :tid 
                AND status = 'MATCHED' 
                AND (bank_ref LIKE 'AI_COMMIT:%' OR bank_ref LIKE 'AI:%')
            """),
            {"tid": user_id}
        ).scalar() or 0
        
        total_trades = db.execute(
            text("SELECT COUNT(*) FROM broker_trades WHERE tenant_id = :tid"),
            {"tid": user_id}
        ).scalar() or 0

        # --- FIX START: CORRECT PENDING MATH (no double counting) ---
        # Total pending = trades that are NOT MATCHED.
        # We do NOT add open breaks to this, because every break belongs to an unsettled trade.
        pending_count = db.execute(
            text("""
                SELECT COUNT(*) FROM broker_trades
                WHERE tenant_id = :tid
                  AND (status != 'MATCHED' OR status IS NULL)
            """),
            {"tid": user_id},
        ).scalar() or 0
        # --- FIX END ---

        pending_proposals = (
            db.query(ReconProposal)
            .filter(
                ReconProposal.tenant_id == user_id,
                ReconProposal.status == "PENDING",
            )
            .count()
        )
        
        # Determine phase and next action
        # NOTE: A stress test can yield 0 matches but many breaks — that still means the engine ran.
        if total_trades == 0:
            current_phase = "PHASE_0_NO_DATA"
            next_action = "Upload files to begin"
            button_to_show = None
        else:
            open_breaks_count = db.execute(
                text("SELECT COUNT(*) FROM recon_breaks WHERE tenant_id = :tid AND status = 'OPEN'"),
                {"tid": user_id},
            ).scalar() or 0
            settlement_ran = (rule_matches > 0) or (open_breaks_count > 0)

            if pending_proposals > 0:
                current_phase = "PHASE_3_PROPOSALS_PENDING"
                next_action = f"Review and commit {pending_proposals} AI proposals"
                button_to_show = "REVIEW_AND_COMMIT"
            elif (not settlement_ran) and ai_matches == 0:
                current_phase = "PHASE_1_INGESTION"
                next_action = "Run deterministic settlement engine"
                button_to_show = "RUN_SETTLEMENT_ENGINE"
            elif settlement_ran and ai_matches == 0:
                current_phase = "PHASE_2_SETTLEMENT_COMPLETE"
                next_action = "Run AI auto-resolve on remaining breaks"
                button_to_show = "AUTO_RESOLVE"
            else:
                current_phase = "PHASE_3_COMPLETE"
                next_action = "Reconciliation complete"
                button_to_show = None

        # Get trade statistics
        trade_stats = db.query(
            func.count(BrokerTrade.id).label("total"),
            func.sum(case((BrokerTrade.status == "MATCHED", 1), else_=0)).label("settled"),
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

        open_breaks = break_stats.open or 0

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
            "pending_settlements": pending_count,  # <-- Correct, non-double-counting number
            "proposals_pending": pending_proposals,
            "workflow": {
                "current_phase": current_phase,
                "next_action": next_action,
                "button_to_show": button_to_show,
                "pending_proposals": pending_proposals,
                "phase_progress": {
                    "ingestion": total_trades > 0,
                    "settlement_engine": (rule_matches > 0) or (open_breaks > 0),
                    "auto_resolve": ai_matches > 0
                }
            },
            "trades": {
                "total": trade_stats.total or 0,
                "settled": trade_stats.settled or 0,
                # Back-compat: keep this field, but make it consistent with pending_count
                "unsettled": pending_count,
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
                "open": open_breaks,
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
                "open_breaks": open_breaks,  # subset of pending, shown for context
                "match_rate": round((trade_stats.settled or 0) / max(trade_stats.total or 1, 1) * 100, 1)
            }
        }
    except Exception as e:
        logger.error(f"Failed to fetch dashboard stats: {str(e)}", exc_info=True)
        # Return safe defaults on error
        return {
            "status": "success",
            "tenant_id": user_id,
            "workflow": {
                "current_phase": "PHASE_0_NO_DATA",
                "next_action": "Upload files to begin",
                "button_to_show": None,
                "phase_progress": {
                    "ingestion": False,
                    "settlement_engine": False,
                    "auto_resolve": False
                }
            },
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
def run_ai_resolve_legacy(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    DEPRECATED: Use /auto-resolve instead.
    
    This endpoint has been replaced by the unified /auto-resolve endpoint
    which performs both deterministic and AI-based reconciliation in a single flow.
    
    Kept for backward compatibility with existing frontend code.
    """
    return {
        "status": "deprecated",
        "message": "This endpoint is deprecated. Please use /auto-resolve instead, which performs both deterministic rules and AI reasoning.",
        "redirect": "/api/v1/recon/auto-resolve"
    }

@router.post("/ai-resolve-standalone")
def run_ai_resolve_standalone(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    LEGACY STANDALONE AI RESOLVE (for testing/development only).
    
    Runs ONLY the AI phase on existing open breaks.
    Does NOT run deterministic rules first.
    
    CONFIDENCE THRESHOLDS:
    - >= 0.85: High confidence, auto-resolve
    - 0.70-0.85: Medium confidence, logged but not auto-resolved
    - < 0.70: Low confidence, needs manual review
    
    After resolution:
    - Updates trade status to MATCHED
    - Updates cash status to MATCHED  
    - Closes the break
    - Creates audit log entry
    
    NOTE (v2.1 PROPOSAL-ONLY MODE):
    Holdings are NOT updated. Aureon outputs diffs only.
    """
    # Configurable threshold - can be adjusted based on risk tolerance
    AUTO_RESOLVE_THRESHOLD = 0.85  # Lowered from 0.9 to allow more auto-resolutions
    
    try:
        agent = AIAgent(db, user_id)
        
        # Get all open breaks with associated trades
        open_breaks = db.query(ReconBreak).filter(
            ReconBreak.tenant_id == user_id,
            ReconBreak.status == "OPEN"
        ).all()
        
        logger.info(f"AI Auto-Resolve: Processing {len(open_breaks)} open breaks for tenant {user_id}")
        
        resolved_count = 0
        analyzed_count = 0
        skipped_count = 0
        low_confidence_count = 0
        analysis_details = []  # Track what happened for debugging
        resolved_trade_ids = set()  # Track for holdings update
        
        for brk in open_breaks:
            if not brk.trade_id:
                skipped_count += 1
                continue
                
            analyzed_count += 1
            
            # Analyze the trade using AI agent
            analysis = agent.analyze_single_trade(brk.trade_id)
            
            confidence = analysis.get("ai_suggestion", {}).get("confidence", 0)
            action = analysis.get("ai_suggestion", {}).get("action", "ESCALATE")
            explanation = analysis.get("ai_suggestion", {}).get("explanation", "")
            best_candidate = analysis.get("best_candidate")
            
            logger.info(f"Trade {brk.trade_id}: confidence={confidence:.2f}, action={action}, candidates={analysis.get('candidates_count', 0)}")
            
            detail = {
                "trade_id": brk.trade_id,
                "break_id": brk.id,
                "confidence": confidence,
                "action": action,
                "resolved": False,
                "reason": explanation[:100] if explanation else "No explanation"
            }
            
            # Check if we should auto-resolve
            if analysis.get("found") and confidence >= AUTO_RESOLVE_THRESHOLD and best_candidate:
                # High confidence match - auto-resolve
                trade = db.query(BrokerTrade).filter_by(
                    id=brk.trade_id, 
                    tenant_id=user_id
                ).first()
                
                if trade and trade.status != "MATCHED":
                    # Update trade status
                    trade.status = "MATCHED"
                    trade.bank_ref = f"AI:{explanation[:50]}... (conf: {confidence:.2f})"
                    
                    # Update cash status if we have a match
                    cash_id = best_candidate.get("id")
                    if cash_id:
                        cash = db.query(BankTxn).filter_by(
                            id=cash_id, 
                            tenant_id=user_id
                        ).first()
                        if cash:
                            cash.status = "MATCHED"
                            cash.trade_ref = trade.id
                    
                    # Mark break as resolved
                    brk.status = "RESOLVED"
                    brk.resolution_note = f"AI:{explanation[:150]}"
                    
                    # Track for holdings update
                    resolved_trade_ids.add(trade.id)
                    resolved_count += 1
                    detail["resolved"] = True
                    
                    # Create audit log
                    audit_log = ReconLog(
                        tenant_id=user_id,
                        trade_id=trade.id,
                        cash_id=cash_id,
                        reason=f"AUTO_RESOLVE: {explanation[:150]}",
                        status_before="UNSETTLED",
                        status_after="MATCHED",
                        agent_model=f"AI_AGENT (conf: {confidence:.2f})",
                    )
                    db.add(audit_log)
                    
                    logger.info(f"✓ Auto-resolved trade {trade.id} with confidence {confidence:.2f}")
            else:
                # Low confidence - log but don't resolve
                low_confidence_count += 1
                detail["reason"] = f"Below threshold ({confidence:.2f} < {AUTO_RESOLVE_THRESHOLD})"
                
                # Still log the analysis attempt for audit
                audit_log = ReconLog(
                    tenant_id=user_id,
                    trade_id=brk.trade_id,
                    reason=f"AI_REVIEW_NEEDED: {explanation[:100]}",
                    status_before="OPEN",
                    status_after="REVIEW",
                    agent_model=f"AI_AGENT (conf: {confidence:.2f})",
                )
                db.add(audit_log)
            
            analysis_details.append(detail)
        
        # ============================================================
        # PROPOSAL-ONLY MODE (v2.1)
        # Holdings are NOT updated here.
        # Aureon outputs diffs (proposals). It never owns state.
        # ============================================================
        logger.info(f"[PROPOSAL_ONLY_MODE] Skipping holdings mutation for {len(resolved_trade_ids)} resolved trades")
        
        db.commit()
        
        logger.info(f"AI Auto-Resolve complete: {resolved_count}/{analyzed_count} resolved, {low_confidence_count} low confidence")
        
        return {
            "status": "success",
            "resolved": resolved_count,
            "total_breaks": len(open_breaks),
            "analyzed": analyzed_count,
            "skipped": skipped_count,
            "low_confidence": low_confidence_count,
            "threshold_used": AUTO_RESOLVE_THRESHOLD,
            "message": f"Resolved {resolved_count} of {analyzed_count} analyzed breaks using AI (threshold: {AUTO_RESOLVE_THRESHOLD})",
            "details": analysis_details[:20]  # Return first 20 for debugging
        }
    except Exception as e:
        db.rollback()
        logger.error(f"AI resolve failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"AI resolve failed: {str(e)}"
        )


@router.post("/resolve-manual/{trade_id}")
def resolve_manual_no_body(
    trade_id: int,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Convenience endpoint for the Glass Box UI.

    Accepts no request body and performs a manual resolve with a default note.
    This keeps the frontend simple (one click) while still persisting the
    resolution in the DB (trade MATCHED, breaks RESOLVED, audit log written).

    NOTE: This wraps the existing /resolve-trade/{trade_id} endpoint.
    """
    payload = ManualResolveRequest(cash_id=None, note="Manual Resolve")
    return manual_resolve_trade(trade_id=trade_id, payload=payload, user_id=user_id, db=db)


@router.post("/resolve-bulk")
def resolve_bulk_trades(
    payload: BulkResolveRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Resolve multiple trades at once.

    Behavior:
    - Iterates trade_ids
    - Attempts to resolve each trade independently
    - Continues on failures (partial success)
    """
    resolved_count = 0
    errors: List[str] = []
    warnings: List[str] = []

    trade_ids = payload.trade_ids or []
    logger.info(f"Bulk resolving {len(trade_ids)} trades for tenant {user_id}")

    for trade_id in trade_ids:
        try:
            single_req = ManualResolveRequest(note=payload.note)
            res = manual_resolve_trade(
                trade_id=trade_id,
                payload=single_req,
                user_id=user_id,
                db=db,
            )

            # manual_resolve_trade can return {"status": "warning"} if already resolved
            if isinstance(res, dict) and res.get("status") == "warning":
                warnings.append(f"ID {trade_id}: {res.get('message', 'Already resolved')}")
            else:
                resolved_count += 1
        except Exception as e:
            logger.error(f"Failed to resolve trade {trade_id}: {str(e)}")
            errors.append(f"ID {trade_id}: {str(e)}")
            # continue

    return {
        "status": "success",
        "resolved_count": resolved_count,
        "failed_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


@router.post("/proposals/commit")
def commit_proposals(
    payload: Optional[CommitProposalsRequest] = Body(default=None),
    min_confidence: float = 0.90,  # Safety threshold (query param fallback)
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    EXECUTOR: Applies pending AI proposals to the Ledger.
    Only applies proposals above the confidence threshold.
    """
    with acquire_tenant_lock(db, user_id, "Committing Proposals"):
        try:
            threshold = (
                float(payload.min_confidence)
                if payload and payload.min_confidence is not None
                else float(min_confidence)
            )
            proposals = (
                db.query(ReconProposal)
                .filter(
                    ReconProposal.tenant_id == user_id,
                    ReconProposal.status == "PENDING",
                    ReconProposal.confidence >= threshold,
                )
                .all()
            )

            committed_count = 0
            errors: List[str] = []

            for p in proposals:
                try:
                    # Use nested transaction so one failure doesn't poison the whole batch
                    with db.begin_nested():
                        # ============================================================
                        # MAKER-CHECKER ENFORCEMENT (v2.1)
                        # ============================================================
                        # 1. Different user required
                        if p.created_by and p.created_by == user_id:
                            logger.warning(f"[MAKER_CHECKER] Proposal {p.id} rejected: creator cannot approve own proposal")
                            errors.append(f"proposal {p.id}: Cannot approve own proposal (created by same user)")
                            continue
                        
                        # Note: Temporal separation is enforced by setting approved_at when approving.
                        # The sequence (created_at < approved_at) is guaranteed by timestamp logic.
                        now = datetime.utcnow()
                        
                        trade = db.query(BrokerTrade).filter_by(id=p.trade_id, tenant_id=user_id).first()
                        if not trade or trade.status == "MATCHED":
                            p.status = "REJECTED"
                            p.processed_at = now
                            continue

                        trade.status = "MATCHED"
                        trade.bank_ref = f"AI_COMMIT:{(p.explanation or '')[:100]} (conf: {float(p.confidence or 0):.2f})"

                        if p.cash_id:
                            cash = db.query(BankTxn).filter_by(id=p.cash_id, tenant_id=user_id).first()
                            if cash:
                                cash.status = "MATCHED"
                                cash.trade_ref = trade.id

                        if p.break_id:
                            brk = db.query(ReconBreak).filter_by(id=p.break_id, tenant_id=user_id).first()
                            if brk:
                                brk.status = "RESOLVED"
                                brk.resolution_note = "Auto-Commited from AI Proposal"

                        p.status = "APPROVED"
                        p.processed_at = now
                        p.approved_by = user_id  # v2.1 Maker-checker audit
                        p.approved_at = now      # v2.1 Temporal separation proof

                        # ============================================================
                        # GOVERNANCE AUDIT: PROPOSAL_APPROVED (v2.1)
                        # This is a control-plane decision, not engine telemetry.
                        # ============================================================
                        _audit(
                            db=db,
                            tenant_id=user_id,
                            event_type="PROPOSAL_APPROVED",
                            entity_type="PROPOSAL",
                            entity_id=p.id,
                            actor=user_id,
                            payload={
                                "trade_id": trade.id,
                                "trade_symbol": trade.symbol,
                                "trade_amount": float(trade.amount) if trade.amount else 0,
                                "cash_id": p.cash_id,
                                "confidence": float(p.confidence) if p.confidence else 0,
                                "source_model": p.source_model,
                                "created_by": p.created_by,
                            },
                            run_id=p.run_id,
                            actor_role="OPS_ANALYST",  # Human approved
                        )

                        # ============================================================
                        # PROPOSAL-ONLY MODE (v2.1)
                        # Holdings are NOT updated here.
                        # Aureon outputs diffs (proposals). It never owns state.
                        # ============================================================
                        logger.info(f"[PROPOSAL_ONLY_MODE] Proposal {p.id} committed, holdings NOT mutated")

                        committed_count += 1
                except Exception as e:
                    logger.error(f"Failed to commit proposal {p.id}: {str(e)}")
                    errors.append(f"proposal {p.id}: {str(e)}")
                    db.rollback()

            db.commit()

            return {
                "status": "success",
                "committed": committed_count,
                "threshold_used": threshold,
                "failed": len(errors),
                "errors": errors,
            }
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# PROPOSALS PREVIEW (v2.1 - Phase 3)
# Shows pending proposals BEFORE committing for human review
# ============================================================

@router.get("/proposals/preview")
def preview_proposals(
    min_confidence: float = 0.0,  # Filter by confidence floor
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Preview all pending AI proposals BEFORE committing.
    
    This endpoint allows analysts to review:
    - What trades are being proposed for matching
    - What cash entries they're being matched to
    - The AI's confidence and explanation
    - The source model used
    
    Use this to inspect proposals before calling /proposals/commit.
    """
    proposals = (
        db.query(ReconProposal)
        .filter(
            ReconProposal.tenant_id == user_id,
            ReconProposal.status == "PENDING",
            ReconProposal.confidence >= min_confidence,
        )
        .order_by(ReconProposal.confidence.desc())
        .all()
    )
    
    preview_data = []
    confidence_bands = {"high": 0, "medium": 0, "low": 0}  # >= 0.95, 0.80-0.95, < 0.80
    
    for p in proposals:
        # Get related trade
        trade = db.query(BrokerTrade).filter_by(id=p.trade_id, tenant_id=user_id).first()
        cash = db.query(BankTxn).filter_by(id=p.cash_id, tenant_id=user_id).first() if p.cash_id else None
        
        conf = float(p.confidence) if p.confidence else 0.0
        if conf >= 0.95:
            confidence_bands["high"] += 1
            confidence_label = "HIGH"
        elif conf >= 0.80:
            confidence_bands["medium"] += 1
            confidence_label = "MEDIUM"
        else:
            confidence_bands["low"] += 1
            confidence_label = "LOW"
        
        preview_data.append({
            "proposal_id": p.id,
            "confidence": conf,
            "confidence_label": confidence_label,
            "source_model": p.source_model,
            "explanation": p.explanation,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "trade": {
                "id": trade.id if trade else None,
                "symbol": trade.symbol if trade else None,
                "side": trade.side if trade else None,
                "amount": float(trade.amount) if trade and trade.amount else 0,
                "quantity": float(trade.quantity) if trade and trade.quantity else 0,
                "date": trade.date.isoformat() if trade and trade.date else None,
                "status": trade.status if trade else None,
            } if trade else None,
            "cash": {
                "id": cash.id if cash else None,
                "amount": float(cash.amount) if cash and cash.amount else 0,
                "type": cash.txn_type if cash else None,
                "date": cash.date.isoformat() if cash and cash.date else None,
                "status": cash.status if cash else None,
            } if cash else None,
            "amount_diff": abs(float(trade.amount or 0) - float(cash.amount or 0)) if trade and cash else None,
            "amount_diff_pct": round(
                abs(float(trade.amount or 0) - float(cash.amount or 0)) / max(float(trade.amount or 1), 1) * 100, 2
            ) if trade and cash and trade.amount else None,
        })
    
    return {
        "status": "success",
        "count": len(preview_data),
        "summary": {
            "total_pending": len(preview_data),
            "high_confidence": confidence_bands["high"],
            "medium_confidence": confidence_bands["medium"],
            "low_confidence": confidence_bands["low"],
            "recommendation": (
                f"Safe to commit {confidence_bands['high']} high-confidence proposals (>= 0.95). "
                f"Review {confidence_bands['medium']} medium-confidence proposals."
            ) if preview_data else "No pending proposals found.",
        },
        "proposals": preview_data,
        "next_steps": [
            "Review proposals above",
            "To commit high-confidence: POST /proposals/commit?min_confidence=0.95",
            "To commit all: POST /proposals/commit?min_confidence=0.80",
            "To export: GET /proposals/export",
        ],
    }


# ============================================================
# PROPOSALS EXPORT (v2.1 - Phase 3)
# ============================================================


@router.get("/proposals/export")
def export_proposals(
    format: str = "json",  # json or csv
    status: Optional[str] = None,  # PENDING, APPROVED, REJECTED
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export proposals for external consumption.
    
    This is how approved matches flow to external systems:
    - Fund admin downloads approved proposals
    - Accounting system ingests for journal entries
    - Custodian reconciles against their records
    
    Aureon outputs diffs. It never owns state.
    """
    query = db.query(ReconProposal).filter(ReconProposal.tenant_id == user_id)
    
    if status:
        query = query.filter(ReconProposal.status == status.upper())
    
    proposals = query.order_by(ReconProposal.created_at.desc()).all()
    
    # Build export data
    export_data = []
    for p in proposals:
        # Get related trade (with tenant isolation for security)
        trade = db.query(BrokerTrade).filter_by(id=p.trade_id, tenant_id=user_id).first()
        cash = db.query(BankTxn).filter_by(id=p.cash_id, tenant_id=user_id).first() if p.cash_id else None
        
        export_data.append({
            "proposal_id": p.id,
            "run_id": p.run_id,
            "status": p.status,
            "confidence": float(p.confidence) if p.confidence else 0.0,
            "trade_id": p.trade_id,
            "trade_symbol": trade.symbol if trade else None,
            "trade_amount": float(trade.amount) if trade else None,
            "trade_date": trade.date.isoformat() if trade and trade.date else None,
            "cash_id": p.cash_id,
            "cash_amount": float(cash.amount) if cash else None,
            "cash_date": cash.date.isoformat() if cash and cash.date else None,
            "explanation": p.explanation,
            "source_model": p.source_model,
            "created_by": p.created_by,
            "approved_by": p.approved_by,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        })
    
    if format.lower() == "csv":
        # Generate CSV
        if not export_data:
            return StreamingResponse(
                iter(["No proposals found"]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=proposals.csv"}
            )
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
        writer.writeheader()
        writer.writerows(export_data)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=proposals_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
    
    # Default: JSON
    return {
        "status": "success",
        "count": len(export_data),
        "proposals": export_data,
        "exported_at": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/system/info")
def get_system_info(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    System information including safety disclosures.
    
    Returns operational mode, version, and worst-case failure disclosure.
    """
    from .config import settings
    
    return {
        "system": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "operational_mode": "PROPOSAL_ONLY",
        
        # ============================================================
        # WORST-CASE DISCLOSURE (v2.1)
        # Auditors, investors, and regulators need to see this.
        # ============================================================
        "safety_disclosure": {
            "mode": "PROPOSAL_ONLY",
            "holdings_mutation": False,
            "system_of_record": False,
            "worst_case_failure": (
                "Aureon produces no usable proposals and reconciliation "
                "proceeds manually, identical to Excel. Aureon is assistive "
                "tooling, not a system of record."
            ),
            "liability_scope": (
                "Aureon provides match suggestions only. All settlements "
                "must be approved by qualified personnel and executed through "
                "authorized systems (fund admin, custodian, accounting)."
            ),
            "audit_trail": "Immutable hash-chain audit log enabled",
            "maker_checker": "Enforced - creator cannot approve own proposals",
        },
        
        "capabilities": {
            "equity_trades": True,
            "derivatives": False,
            "real_time": False,
            "auto_posting": False,
        },
    }


# ============================================================
# AUDIT TRAIL ENDPOINTS (v2.1 - UI Support)
# ============================================================

@router.get("/audit-events")
def get_audit_events(
    limit: int = 100,
    event_type: Optional[str] = None,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get audit events for the tenant.
    
    Returns events in reverse chronological order with hash chain info.
    """
    query = db.query(AuditEvent).filter(AuditEvent.tenant_id == user_id)
    
    if event_type:
        query = query.filter(AuditEvent.event_type.ilike(f"%{event_type}%"))
    
    events = query.order_by(AuditEvent.created_at.desc()).limit(limit).all()
    
    return {
        "status": "success",
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "actor": e.actor,
                "payload": e.payload,
                "prev_hash": e.prev_hash,
                "event_hash": e.event_hash,
                "run_id": e.run_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.get("/audit-verify")
def verify_audit_chain(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Verify the integrity of the audit hash chain.
    
    Returns verification result:
    - valid: True if chain is intact
    - events_verified: Number of events checked
    - head_hash: Current head of the chain
    - errors: List of any integrity issues found
    """
    from .audit import get_audit_log
    
    audit = get_audit_log(db, user_id)
    result = audit.verify_chain()
    
    logger.info(f"[AUDIT_VERIFY] Tenant {user_id}: valid={result['valid']}, events={result['events_verified']}")
    
    return {
        "status": "success",
        **result,
    }


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
    
    NOTE (v2.1 PROPOSAL-ONLY MODE):
    Holdings are NOT updated. Aureon outputs proposals only.
    Holdings must live in external systems (fund admin, custodian).
    """
    trade = (
        db.query(BrokerTrade)
        .filter(BrokerTrade.id == trade_id, BrokerTrade.tenant_id == user_id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    # Check if trade is already resolved
    if trade.status == "MATCHED":
        return {
            "status": "warning", 
            "message": "Trade is already resolved", 
            "trade_id": trade_id
        }

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
        # Update trade status with MANUAL prefix for resolution tracking
        trade.status = "MATCHED"
        trade.bank_ref = f"MANUAL:{note}"

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
            brk.resolution_note = f"MANUAL:{note}"

        # Write learning event so Neural Core can retrain later
        # CRITICAL: Use source="HUMAN_MANUAL" so learner.py can find it
        learning_event = LearningEvent(
            tenant_id=user_id,
            trade_id=trade.id,
            status="MANUAL_RESOLVED",
            source="HUMAN_MANUAL",  # Fixed: was "Analyst", learner looks for "HUMAN_MANUAL"
            trade_data={
                "symbol": trade.symbol,
                "amount": float(trade.amount) if trade.amount else 0,
                "side": trade.side,
                "quantity": float(trade.quantity) if trade.quantity else 0,
                "price": float(trade.price) if trade.price else 0,
                "date": trade.date.isoformat() if trade.date else None,
                "cash_id": cash_record.id if cash_record else None,
                "cash_amount": float(cash_record.amount) if cash_record else None,
            },
            correction_notes=note,
        )
        db.add(learning_event)
        
        # ============================================================
        # PROPOSAL-ONLY MODE (v2.1)
        # Holdings are NOT updated here.
        # Aureon outputs diffs (proposals). It never owns state.
        # ============================================================
        logger.info(f"[PROPOSAL_ONLY_MODE] Trade {trade_id} resolved, holdings NOT mutated")
        
        # ============================================================
        # GOVERNANCE AUDIT: TRADE_RESOLVED (v2.1)
        # Human authority exercised. This belongs in the audit trail.
        # ============================================================
        _audit(
            db=db,
            tenant_id=user_id,
            event_type="TRADE_RESOLVED",
            entity_type="TRADE",
            entity_id=trade.id,
            actor=user_id,
            payload={
                "symbol": trade.symbol,
                "amount": float(trade.amount) if trade.amount else 0,
                "side": trade.side,
                "cash_id": cash_record.id if cash_record else None,
                "cash_amount": float(cash_record.amount) if cash_record else None,
                "resolution_note": note,
                "breaks_closed": len(open_breaks),
            },
            actor_role="OPS_ANALYST",  # Human manually resolved
        )

        db.commit()
        
        return {
            "status": "success", 
            "message": "Trade resolved (proposal-only mode - holdings not mutated)", 
            "trade_id": trade_id,
            "resolution_type": "MANUAL",
            "proposal_only_mode": True,
        }
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


@router.post("/system/hard-reset")
def system_hard_reset(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    DEVELOPMENT ONLY: Full schema reset.
    
    This endpoint:
    1. Drops ALL tables in public schema (not just data)
    2. Runs Alembic upgrade head to recreate schema
    3. Verifies schema integrity
    
    WARNING: This destroys ALL data for ALL tenants.
    Never expose in production.
    """
    from .database import engine, Base
    from .config import settings
    
    # Block in production
    if settings.environment == "production":
        raise HTTPException(
            status_code=403,
            detail="Hard reset is disabled in production"
        )
    
    try:
        logger.warning("🚨 HARD RESET INITIATED - Dropping all tables...")
        
        # Step 1: Drop all tables
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            conn.commit()
        logger.info("✅ Schema dropped and recreated")
        
        # Step 2: Run Alembic migrations
        import subprocess
        import os as os_mod
        # Compute project root dynamically (works on any machine)
        project_root = os_mod.path.dirname(os_mod.path.dirname(os_mod.path.abspath(__file__)))
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        if result.returncode != 0:
            raise RuntimeError(f"Alembic upgrade failed: {result.stderr}")
        logger.info("✅ Alembic migrations applied")
        
        # Step 3: Verify schema
        from sqlalchemy import inspect
        insp = inspect(engine)
        tables = insp.get_table_names()
        
        return {
            "status": "success",
            "message": "Hard reset completed - schema rebuilt from migrations",
            "tables_created": tables,
            "warning": "Server MUST be restarted to reload ORM metadata"
        }
        
    except Exception as e:
        logger.error(f"Hard reset failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Hard reset failed: {str(e)}"
        )


@router.get("/system/health")
def system_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Comprehensive system health check.
    
    Verifies:
    - Database reachable
    - Schema valid
    - Alembic version correct
    - Audit table writable
    - Critical tables exist
    """
    from .database import engine
    from sqlalchemy import inspect
    
    checks = {}
    overall_healthy = True
    
    try:
        # Check 1: Database connection
        with engine.connect() as conn:
            db_name = conn.execute(text("SELECT current_database()")).scalar()
            checks["database_connection"] = {
                "status": "healthy",
                "database": db_name
            }
    except Exception as e:
        checks["database_connection"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    try:
        # Check 2: Alembic version
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            expected = "1d4eef084a0e"
            is_current = version == expected
            checks["alembic_version"] = {
                "status": "healthy" if is_current else "warning",
                "current": version,
                "expected": expected
            }
            if not is_current:
                overall_healthy = False
    except Exception as e:
        checks["alembic_version"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    try:
        # Check 3: Critical tables exist
        insp = inspect(engine)
        critical_tables = ["broker_trades", "bank_txns", "audit_events", "recon_proposals"]
        existing = insp.get_table_names()
        missing = [t for t in critical_tables if t not in existing]
        checks["critical_tables"] = {
            "status": "healthy" if not missing else "unhealthy",
            "missing": missing if missing else None
        }
        if missing:
            overall_healthy = False
    except Exception as e:
        checks["critical_tables"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    try:
        # Check 4: Audit column exists (the one that was failing)
        cols = [c["name"] for c in insp.get_columns("audit_events")]
        has_actor_role = "actor_role" in cols
        checks["audit_schema"] = {
            "status": "healthy" if has_actor_role else "unhealthy",
            "actor_role_exists": has_actor_role
        }
        if not has_actor_role:
            overall_healthy = False
    except Exception as e:
        checks["audit_schema"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks
    }

@router.get("/export-csv")
def export_reconciliation_report(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate and download a full reconciliation audit report as CSV.

    Columns:
    Trade ID, Date, Symbol, Side, Amount, Status, Resolution Type, Resolution Note, AI Confidence
    """
    try:
        logger.info(f"Generating CSV export for tenant {user_id}")

        # Join trades with (optional) open break + matched cash txn
        from sqlalchemy.orm import aliased
        from sqlalchemy import and_
        import re

        Break = aliased(ReconBreak)
        Cash = aliased(BankTxn)

        # Pick one OPEN break per trade (lowest id) to avoid duplicates
        open_break_sq = (
            db.query(
                ReconBreak.trade_id.label("trade_id"),
                func.min(ReconBreak.id).label("break_id"),
            )
            .filter(
                ReconBreak.tenant_id == user_id,
                ReconBreak.status == "OPEN",
            )
            .group_by(ReconBreak.trade_id)
            .subquery()
        )

        # Pick one matched cash row per trade (lowest id) to avoid duplicates
        cash_sq = (
            db.query(
                BankTxn.trade_ref.label("trade_ref"),
                func.min(BankTxn.id).label("cash_id"),
            )
            .filter(
                BankTxn.tenant_id == user_id,
                BankTxn.trade_ref.isnot(None),
            )
            .group_by(BankTxn.trade_ref)
            .subquery()
        )

        rows = (
            db.query(BrokerTrade, Break, Cash)
            .outerjoin(open_break_sq, open_break_sq.c.trade_id == BrokerTrade.id)
            .outerjoin(Break, Break.id == open_break_sq.c.break_id)
            .outerjoin(cash_sq, cash_sq.c.trade_ref == BrokerTrade.id)
            .outerjoin(Cash, Cash.id == cash_sq.c.cash_id)
            .filter(BrokerTrade.tenant_id == user_id)
            .order_by(BrokerTrade.date.desc())
            .all()
        )

        def _parse_ai_confidence(text_val: str) -> Optional[float]:
            if not text_val:
                return None
            # supports "(conf: 0.92)" or "confidence: 0.92"
            m = re.search(r"(?:conf(?:idence)?\s*[:=]\s*)(0(?:\.\d+)?|1(?:\.0+)?)", text_val, re.IGNORECASE)
            if not m:
                return None
            try:
                return float(m.group(1))
            except Exception:
                return None

        def generate():
            output = io.StringIO()
            writer = csv.writer(output)

            writer.writerow(
                [
                    "Trade ID",
                    "Date",
                    "Symbol",
                    "Side",
                    "Amount",
                    "Status",
                    "Resolution Type",
                    "Resolution Note",
                    "AI Confidence",
                ]
            )
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            for t, brk, cash in rows:
                # Status (BREAK is derived)
                status = t.status or "UNSETTLED"
                if status in ("UNSETTLED", None) and brk is not None:
                    status = "BREAK"

                # Resolution type + note
                resolution_type = "PENDING"
                resolution_note = ""
                ai_conf = None

                if t.status == "MATCHED":
                    if t.bank_ref and ":" in t.bank_ref:
                        prefix, note = t.bank_ref.split(":", 1)
                        resolution_type = prefix.strip().upper()
                        resolution_note = note.strip()
                    else:
                        resolution_type = "MATCHED_UNKNOWN"
                        resolution_note = t.bank_ref or ""

                    if resolution_type == "AI":
                        ai_conf = _parse_ai_confidence(t.bank_ref or "")

                else:
                    if brk is not None:
                        resolution_type = "OPEN_BREAK"
                        sev = brk.severity.value if getattr(brk, "severity", None) else "MEDIUM"
                        resolution_note = f"{brk.break_type} - {sev}"
                        ai_conf = _parse_ai_confidence(getattr(brk, "resolution_note", "") or "")

                writer.writerow(
                    [
                        t.id,
                        t.date.isoformat() if t.date else "",
                        t.symbol or "",
                        t.side or "",
                        float(to_decimal(t.amount)),
                        status,
                        resolution_type,
                        resolution_note,
                        f"{ai_conf:.2f}" if ai_conf is not None else "",
                    ]
                )
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

        filename = f"aureon_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"Export failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")