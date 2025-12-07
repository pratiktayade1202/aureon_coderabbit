# backend/recon_api.py
from datetime import datetime
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/recon", tags=["reconciliation"])


@router.post("/run")
def run_basic_reconciliation(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Very simple Tier-1-ish reconciliation:
    - For this tenant, mark trades as unmatched breaks if we can't find a cash txn
      with same amount and same date.
    This is intentionally conservative; it won't over-match.
    """
    try:
        # Clear old breaks for this tenant
        db.execute(
            text("DELETE FROM recon_breaks WHERE tenant_id = :tid"),
            {"tid": user_id},
        )

        # Insert UNMATCHED_TRADE breaks
        db.execute(
            text(
                """
                INSERT INTO recon_breaks
                (
                    tenant_id,
                    trade_id,
                    cash_id,
                    rule_id,
                    break_type,
                    severity,
                    amount_diff,
                    age_days,
                    status,
                    resolution_note,
                    created_at
                )
                SELECT
                    bt.tenant_id,
                    bt.id AS trade_id,
                    NULL AS cash_id,
                    'T1_UNMATCHED_TRADE' AS rule_id,
                    'UNMATCHED_TRADE' AS break_type,
                    'HIGH' AS severity,
                    bt.amount AS amount_diff,
                    0 AS age_days,
                    'OPEN' AS status,
                    '' AS resolution_note,
                    NOW() AS created_at
                FROM broker_trades bt
                WHERE bt.tenant_id = :tid
                  AND NOT EXISTS (
                      SELECT 1
                      FROM bank_txns b
                      WHERE b.tenant_id = bt.tenant_id
                        AND b.amount = bt.amount
                        AND b.date = bt.date
                  )
                """
            ),
            {"tid": user_id},
        )

        # Insert UNMATCHED_CASH breaks (cash with no matching trade)
        db.execute(
            text(
                """
                INSERT INTO recon_breaks
                (
                    tenant_id,
                    trade_id,
                    cash_id,
                    rule_id,
                    break_type,
                    severity,
                    amount_diff,
                    age_days,
                    status,
                    resolution_note,
                    created_at
                )
                SELECT
                    b.tenant_id,
                    NULL AS trade_id,
                    b.id   AS cash_id,
                    'T1_UNMATCHED_CASH' AS rule_id,
                    'UNMATCHED_CASH' AS break_type,
                    'MEDIUM' AS severity,
                    b.amount AS amount_diff,
                    0 AS age_days,
                    'OPEN' AS status,
                    '' AS resolution_note,
                    NOW() AS created_at
                FROM bank_txns b
                WHERE b.tenant_id = :tid
                  AND NOT EXISTS (
                      SELECT 1
                      FROM broker_trades bt
                      WHERE bt.tenant_id = b.tenant_id
                        AND bt.amount = b.amount
                        AND bt.date = b.date
                  )
                """
            ),
            {"tid": user_id},
        )

        db.commit()
        return {"status": "OK", "message": "Basic reconciliation run for tenant", "tenant_id": user_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Recon failed: {e}")


@router.get("/breaks")
def list_breaks(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns current breaks for this tenant.
    """
    rows = db.execute(
        text(
            """
            SELECT
                id,
                trade_id,
                cash_id,
                rule_id,
                break_type,
                severity,
                amount_diff,
                age_days,
                status,
                resolution_note,
                created_at
            FROM recon_breaks
            WHERE tenant_id = :tid
            ORDER BY created_at DESC
            LIMIT 500
            """
        ),
        {"tid": user_id},
    ).mappings().all()

    return {"breaks": [dict(r) for r in rows]}


@router.post("/clear/{break_id}")
def clear_break(
    break_id: int,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Marks a break as RESOLVED.
    """
    res = db.execute(
        text(
            """
            UPDATE recon_breaks
               SET status = 'RESOLVED',
                   resolution_note = COALESCE(resolution_note, '') || ' [manual resolve]',
                   created_at = created_at
             WHERE id = :bid
               AND tenant_id = :tid
            """
        ),
        {"bid": break_id, "tid": user_id},
    )
    db.commit()

    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Break not found")

    return {"status": "OK", "break_id": break_id}
