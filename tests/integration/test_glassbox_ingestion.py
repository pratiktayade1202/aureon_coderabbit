# tests/integration/test_glassbox_ingestion.py
"""
Integration test for the Glass-Box Ingestion Pipeline.
Verifies the end-to-end flow:
1. Upload -> Session Created -> Analysis (Auto)
2. Preview -> Inspect Contract & Confidence
3. Approve -> Contract Signed -> Execution Queued
"""
import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Assuming standard conftest.py provides client and db_session
# If not, we'll import app from main

def test_glassbox_ingestion_flow(client: TestClient, db_session: Session):
    # 1. SETUP: Create a dummy CSV file
    csv_content = b"date,symbol,quantity,price,side\n2023-01-01,AAPL,100,150.0,BUY"
    filename = "test_trade_JAN23.csv"
    
    # 2. UPLOAD (Start Session)
    response = client.post(
        "/api/v1/ingestion/sessions",  # Adjust prefix if needed
        files={"file": (filename, csv_content, "text/csv")},
        headers={"Authorization": "Bearer dev-token"}
    )
    
    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()
    
    session_id = data["session_id"]
    status = data["status"]
    
    assert session_id is not None
    # In our demo impl, analysis is synchronous, so status should be DRAFT
    assert status == "DRAFT" 
    
    # 3. PREVIEW (Get Session Status)
    response = client.get(
        f"/api/v1/ingestion/sessions/{session_id}",
        headers={"Authorization": "Bearer dev-token"}
    )
    
    assert response.status_code == 200
    session_data = response.json()
    contract = session_data["contract"]
    
    assert contract is not None
    assert contract["status"] == "DRAFT"
    
    # Check Intent Detection
    assert contract["dataset_type"] == "TRADE"
    
    # Check Mapping
    mapping = contract["mapping"]
    assert mapping["date"] == "date" # Assuming standard map works
    assert mapping["symbol"] == "symbol"
    
    # Check Confidence
    confidence = contract["confidence"]
    assert confidence["score"] > 0.0
    
    # 4. APPROVE (Sign Contract)
    contract_id = contract["id"]
    final_mapping = mapping # Accept as is
    
    response = client.post(
        f"/api/v1/ingestion/contracts/{contract_id}/approve",
        json={
            "contract_id": contract_id,
            "final_mapping": final_mapping,
            "destructive_ack": False
        },
        headers={"Authorization": "Bearer dev-token"}
    )
    
    assert response.status_code == 200
    approval_data = response.json()
    
    assert approval_data["status"] == "success"
    assert "execution_id" in approval_data
    
    # 5. VERIFY FINAL STATE
    # Verify contract status is SIGNED
    response = client.get(
        f"/api/v1/ingestion/sessions/{session_id}",
        headers={"Authorization": "Bearer dev-token"}
    )
    final_contract = response.json()["contract"]
    assert final_contract["status"] == "SIGNED"
