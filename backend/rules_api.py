# backend/rules_api.py
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleCreate(BaseModel):
    rule_id: str
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None
    tier: Optional[str] = None  # 'TIER_1_DETERMINISTIC', 'TIER_2_TOLERANCE', 'TIER_3_AI'
    tolerance_threshold: Optional[float] = None


@router.get("/list")
def list_rules(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    rows = db.execute(
        text(
            """
            SELECT rule_id, name, description, domain, tier, is_active, tolerance_threshold
            FROM rule_definitions
            ORDER BY domain, tier, rule_id
            """
        )
    ).mappings().all()

    return {"rules": [dict(r) for r in rows]}


@router.post("/activate/{rule_id}")
def activate_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    res = db.execute(
        text(
            """
            UPDATE rule_definitions
               SET is_active = TRUE
             WHERE rule_id = :rid
            """
        ),
        {"rid": rule_id},
    )
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"status": "OK", "rule_id": rule_id, "is_active": True}


@router.post("/deactivate/{rule_id}")
def deactivate_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    res = db.execute(
        text(
            """
            UPDATE rule_definitions
               SET is_active = FALSE
             WHERE rule_id = :rid
            """
        ),
        {"rid": rule_id},
    )
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"status": "OK", "rule_id": rule_id, "is_active": False}


@router.post("/create")
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        db.execute(
            text(
                """
                INSERT INTO rule_definitions
                (rule_id, name, description, domain, tier, is_active, tolerance_threshold)
                VALUES (:rule_id, :name, :description, :domain, :tier, TRUE, :tol)
                """
            ),
            {
                "rule_id": payload.rule_id,
                "name": payload.name,
                "description": payload.description,
                "domain": payload.domain,
                "tier": payload.tier,
                "tol": payload.tolerance_threshold,
            },
        )
        db.commit()
        return {"status": "OK", "rule_id": payload.rule_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Rule create failed: {e}")
