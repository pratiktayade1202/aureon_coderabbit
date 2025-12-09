"""
backend/learning_api.py

Lightweight endpoints to support the Neural Core (Learner) and audit views
without changing core reconciliation semantics.
"""

from typing import Dict, Any, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import get_db
from .auth import get_current_user
from .models import ReconLog

router = APIRouter(tags=["learning"])


@router.get("/learned-rules")
def get_learned_rules(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Learner page endpoint.

    For now, returns an empty list so the UI renders a graceful
    "no patterns learned yet" state. Later this can be backed by
    rule_memory or other ML storage without breaking the contract.
    """
    return []


@router.post("/learned-rules/train")
def train_learned_rules(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Trigger training of learned rules (stub).

    In this hardened version we simply acknowledge the request; the
    reconciliation engine remains the source of truth for breaks.
    """
    return {
        "status": "success",
        "message": "Training triggered (stubbed endpoint). Core rules remain deterministic.",
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
        payload.append(
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None,
                "status": "success",
                "action": log.reason,
                "details": f"Rule {log.rule_id or 'N/A'} moved from {log.status_before} to {log.status_after}",
                "user": log.tenant_id,
                "model": log.agent_model,
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


