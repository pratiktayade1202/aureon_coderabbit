# backend/audit/append_log.py
"""
Immutable Append-Only Audit Log (v2.1)

This module provides a hash-chained audit log that:
- Never allows UPDATE or DELETE
- Links each entry to the previous via hash chain
- Stores head hash per run for verification
- Enables replay and integrity verification

Design Principle: "Aureon outputs diffs. It never owns state."
The audit log is the ONLY exception - we own the audit trail.
"""
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AppendOnlyLog:
    """
    Simple append-only audit log with hash chain.
    
    Hash = sha256(prev_hash + payload + timestamp)
    Store head hash per run for replayability.
    
    NOTE: This class INSERT only, never UPDATE.
    The underlying table should have no UPDATE/DELETE privileges in production.
    """
    
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self._head_hash: Optional[str] = None
    
    def _get_last_hash(self) -> str:
        """Get the hash of the most recent audit event for this tenant."""
        from ..models import AuditEvent
        
        last_event = (
            self.db.query(AuditEvent)
            .filter(AuditEvent.tenant_id == self.tenant_id)
            .order_by(AuditEvent.created_at.desc())
            .first()
        )
        
        return last_event.event_hash if last_event else "GENESIS"
    
    def _compute_hash(self, event: Dict[str, Any]) -> str:
        """
        Compute SHA256 hash of event.
        Hash includes: prev_hash + payload + timestamp for chain integrity.
        """
        # Create deterministic JSON string (sorted keys)
        canonical = json.dumps(event, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def append(
        self,
        event_type: str,
        entity_type: str,
        entity_id: Any,
        actor: str,
        payload: Dict[str, Any],
        run_id: Optional[str] = None,
        actor_role: str = "SYSTEM",  # OPS_ANALYST | SYSTEM | ADMIN
    ) -> str:
        """
        Append an immutable audit event.
        
        Args:
            event_type: Type of event (e.g., PROPOSAL_CREATED, PROPOSAL_APPROVED)
            entity_type: Type of entity (e.g., TRADE, PROPOSAL, BREAK, RUN)
            entity_id: ID of the entity
            actor: User ID who performed the action
            payload: Event-specific data
            run_id: Optional reconciliation run ID
            actor_role: Role of actor (OPS_ANALYST, SYSTEM, ADMIN)
            
        Returns:
            The hash of the new event
        """
        from ..models import AuditEvent
        
        prev_hash = self._get_last_hash()
        ts = datetime.utcnow()
        
        # Build the event data (without hash - added after computation)
        event_data = {
            "id": str(uuid4()),
            "ts": ts.isoformat(),
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "actor": actor,
            "actor_role": actor_role,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        
        # Compute hash of the event
        event_hash = self._compute_hash(event_data)
        
        # Create database record
        audit_event = AuditEvent(
            id=event_data["id"],
            tenant_id=self.tenant_id,
            run_id=run_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=str(entity_id),
            actor=actor,
            actor_role=actor_role,
            payload=payload,
            prev_hash=prev_hash,
            event_hash=event_hash,
            created_at=ts,
        )
        
        self.db.add(audit_event)
        self._head_hash = event_hash
        
        logger.info(f"[AUDIT] {event_type} {entity_type}:{entity_id} by {actor} ({actor_role}) hash:{event_hash[:8]}...")
        
        return event_hash
    
    def verify_chain(self) -> Dict[str, Any]:
        """
        Verify the integrity of the audit chain for this tenant.
        
        Returns:
            {
                "valid": bool,
                "events_verified": int,
                "errors": list of any integrity issues
            }
        """
        from ..models import AuditEvent
        
        events = (
            self.db.query(AuditEvent)
            .filter(AuditEvent.tenant_id == self.tenant_id)
            .order_by(AuditEvent.created_at.asc())
            .all()
        )
        
        errors = []
        prev_hash = "GENESIS"
        
        for i, event in enumerate(events):
            # Reconstruct event data
            event_data = {
                "id": event.id,
                "ts": event.created_at.isoformat(),
                "event_type": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "actor": event.actor,
                "actor_role": event.actor_role,
                "payload": event.payload,
                "prev_hash": event.prev_hash,
            }
            
            # Verify prev_hash chain
            if event.prev_hash != prev_hash:
                errors.append(f"Event {i}: prev_hash mismatch (expected {prev_hash[:8]}, got {event.prev_hash[:8]})")
            
            # Verify computed hash
            computed_hash = self._compute_hash(event_data)
            if computed_hash != event.event_hash:
                errors.append(f"Event {i}: hash mismatch (computed {computed_hash[:8]}, stored {event.event_hash[:8]})")
            
            prev_hash = event.event_hash
        
        return {
            "valid": len(errors) == 0,
            "events_verified": len(events),
            "head_hash": prev_hash if events else "GENESIS",
            "errors": errors,
        }


# Singleton-style helper for use in API endpoints
def get_audit_log(db: Session, tenant_id: str) -> AppendOnlyLog:
    """Get an audit log instance for the given tenant."""
    return AppendOnlyLog(db, tenant_id)
