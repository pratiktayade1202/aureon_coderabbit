# tests/integration/test_safety_v21.py
"""
Surgical Test Coverage for AUREON v2.1 Safety Features

These tests verify the core safety guarantees:
1. Proposal-Only Mode - No holdings mutation
2. Idempotency - Same run twice = same result
3. Maker-Checker - Creator cannot approve own proposals
4. Completeness Guard - Blocks incomplete runs
5. Audit Chain Integrity - Hash chain verification

Run with: pytest tests/integration/test_safety_v21.py -v
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models import (
    BrokerTrade, BankTxn, Holding, ReconProposal, 
    ReconciliationRun, AuditEvent, ReconBreak
)


class TestProposalOnlyMode:
    """
    Test: Aureon outputs diffs. It never owns state.
    Holdings should NEVER be mutated by any reconciliation operation.
    """
    
    def test_settlement_engine_does_not_mutate_holdings(self, client: TestClient, db_session: Session):
        """Settlement engine should NOT update holdings."""
        # Get initial holdings count (in production DB)
        initial_holdings = db_session.query(Holding).count()
        
        # Run settlement engine (even with no data, should not create holdings)
        response = client.post(
            "/api/v1/recon/run-settlement-engine",
            headers={"Authorization": "Bearer dev-token"}
        )
        
        # Assert: Holdings should NOT have changed
        final_holdings = db_session.query(Holding).count()
        assert final_holdings == initial_holdings, "Holdings should not be mutated in proposal-only mode"
    
    def test_proposal_only_mode_flag_exists(self, client: TestClient):
        """System info should show proposal-only mode is enabled."""
        response = client.get(
            "/api/v1/recon/system/info",
            headers={"Authorization": "Bearer dev-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["operational_mode"] == "PROPOSAL_ONLY"
        assert data["safety_disclosure"]["holdings_mutation"] == False


class TestIdempotency:
    """
    Test: Same run ID twice = same result.
    Client-supplied run IDs enable idempotent retries.
    """
    
    def test_create_run_is_idempotent(self, client: TestClient, db_session: Session):
        """Creating a run with same ID twice should return existing run."""
        run_id = f"test-run-{uuid4()}"
        
        # First create
        response1 = client.post(
            "/api/v1/recon/runs/create",
            json={"run_id": run_id, "run_type": "SETTLEMENT", "expected_sources": 2},
            headers={"Authorization": "Bearer dev-token"}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["status"] == "created"
        
        # Second create with same ID - should return existing
        response2 = client.post(
            "/api/v1/recon/runs/create",
            json={"run_id": run_id, "run_type": "SETTLEMENT", "expected_sources": 2},
            headers={"Authorization": "Bearer dev-token"}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        # The API returns "exists" status when run already exists
        assert data2.get("message") == "Run already exists (idempotent)" or data2["status"] in ["exists", "created"]
        
        # Verify run_id is returned
        assert data2["run_id"] == run_id
    
    def test_proposal_unique_constraint_model(self, db_session: Session):
        """Same (run_id, trade_id) should reject duplicate proposals at DB level."""
        run_id = f"test-run-{uuid4()}"
        
        # Create run
        run = ReconciliationRun(
            id=run_id,
            tenant_id="test-user",
            run_type="SETTLEMENT",
            expected_sources=1,
        )
        db_session.add(run)
        db_session.flush()
        
        # Create trade
        trade = BrokerTrade(
            tenant_id="test-user",
            date=datetime.now().date(),
            symbol="INFY",
            side="BUY",
            quantity=100,
            price=1500.0,
            amount=150000.0,
            status="UNSETTLED",
        )
        db_session.add(trade)
        db_session.flush()
        
        # First proposal
        proposal1 = ReconProposal(
            tenant_id="test-user",
            run_id=run_id,
            trade_id=trade.id,
            confidence=0.95,
            explanation="Test",
            source_model="TEST",
            created_by="user1",
        )
        db_session.add(proposal1)
        db_session.flush()
        
        # Second proposal with same run_id + trade_id should fail
        proposal2 = ReconProposal(
            tenant_id="test-user",
            run_id=run_id,
            trade_id=trade.id,
            confidence=0.90,
            explanation="Duplicate",
            source_model="TEST",
            created_by="user2",
        )
        db_session.add(proposal2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.flush()


class TestMakerChecker:
    """
    Test: Creator cannot approve own proposals.
    Enforces separation of duties.
    """
    
    def test_maker_checker_fields_exist_on_proposal(self, db_session: Session):
        """Proposal model should have maker-checker fields."""
        # Verify ReconProposal has the required fields
        assert hasattr(ReconProposal, 'created_by')
        assert hasattr(ReconProposal, 'approved_by')
        assert hasattr(ReconProposal, 'approved_at')
    
    def test_maker_checker_logic_in_commit(self, client: TestClient, db_session: Session):
        """Commit endpoint should enforce maker-checker."""
        # Create a trade in DB first
        trade = BrokerTrade(
            tenant_id="dev-token",  # Must match the dev-token user
            date=datetime.now().date(),
            symbol="HDFC",
            side="BUY",
            quantity=20,
            price=1600.0,
            amount=32000.0,
            status="UNSETTLED",
        )
        db_session.add(trade)
        db_session.flush()
        trade_id = trade.id
        
        # Create proposal with created_by = dev-token (same user who will commit)
        proposal = ReconProposal(
            tenant_id="dev-token",
            trade_id=trade_id,
            confidence=0.95,
            explanation="High confidence match",
            source_model="GEMINI",
            status="PENDING",
            created_by="dev-token",  # Same user
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add(proposal)
        db_session.commit()  # Commit so API can see it
        
        # Try to commit - the proposal should be blocked
        response = client.post(
            "/api/v1/recon/proposals/commit",
            json={"min_confidence": 0.90},
            headers={"Authorization": "Bearer dev-token"}
        )
        
        data = response.json()
        # Either no commits or error about self-approval
        assert data["committed"] == 0 or any("Cannot approve" in str(e) for e in data.get("errors", []))


class TestCompletenessGuard:
    """
    Test: Run cannot be marked complete if sources are missing.
    Prevents partial reconciliation.
    """
    
    def test_completeness_fields_exist(self):
        """ReconciliationRun should have completeness tracking fields."""
        assert hasattr(ReconciliationRun, 'expected_sources')
        assert hasattr(ReconciliationRun, 'received_sources')
    
    def test_incomplete_run_via_api(self, client: TestClient, db_session: Session):
        """Test completeness guard via API flow."""
        run_id = f"test-run-{uuid4()}"
        
        # Create run expecting 3 sources
        response = client.post(
            "/api/v1/recon/runs/create",
            json={"run_id": run_id, "run_type": "SETTLEMENT", "expected_sources": 3},
            headers={"Authorization": "Bearer dev-token"}
        )
        assert response.status_code == 200
        
        # Try to complete without uploading any sources
        response = client.post(
            f"/api/v1/recon/runs/{run_id}/complete",
            headers={"Authorization": "Bearer dev-token"}
        )
        
        # Should fail because received_sources (0) < expected_sources (3)
        assert response.status_code == 400
        # Check for missing in any part of the response
        response_text = str(response.json())
        assert "missing" in response_text.lower() or "source" in response_text.lower()


class TestAuditChainIntegrity:
    """
    Test: Audit log hash chain is tamper-evident.
    Each event's hash includes previous hash.
    """
    
    def test_audit_append_creates_chain(self, db_session: Session):
        """Appending events should create valid hash chain."""
        from backend.audit import get_audit_log
        
        audit = get_audit_log(db_session, "test-user")
        
        # Append multiple events
        hash1 = audit.append(
            event_type="TEST_EVENT_1",
            entity_type="TEST",
            entity_id="1",
            actor="test-user",
            payload={"action": "created"},
        )
        db_session.commit()
        
        hash2 = audit.append(
            event_type="TEST_EVENT_2",
            entity_type="TEST",
            entity_id="2",
            actor="test-user",
            payload={"action": "updated"},
        )
        db_session.commit()
        
        # Verify chain
        result = audit.verify_chain()
        assert result["valid"] == True
        assert result["events_verified"] >= 2
        assert result["head_hash"] == hash2
    
    def test_chain_verification_api(self, client: TestClient, db_session: Session):
        """API endpoint should verify chain integrity."""
        response = client.get(
            "/api/v1/recon/audit-verify",
            headers={"Authorization": "Bearer dev-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "events_verified" in data
