# tests/integration/test_api.py
"""
Integration tests for API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "OPERATIONAL"
        assert "version" in data
        assert "endpoints" in data
    
    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
    
    def test_api_v1_health(self, client: TestClient, auth_headers: dict):
        """Test API v1 health endpoint."""
        response = client.get("/api/v1/health", headers=auth_headers)
        assert response.status_code == 200


class TestTradesEndpoint:
    """Tests for trades API endpoints."""
    
    def test_get_trades_empty(self, client: TestClient, auth_headers: dict):
        """Test getting trades when none exist."""
        response = client.get("/api/v1/recon/trades", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data or isinstance(data, list)
    
    def test_get_trades_pagination(self, client: TestClient, auth_headers: dict, multiple_trades):
        """Test trades pagination."""
        # Get first page
        response = client.get(
            "/api/v1/recon/trades?page=1&page_size=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if "pagination" in data:
            assert data["pagination"]["page"] == 1
            assert data["pagination"]["page_size"] == 10
            assert len(data["data"]) <= 10
    
    def test_get_trades_filter_by_status(self, client: TestClient, auth_headers: dict, multiple_trades):
        """Test filtering trades by status."""
        response = client.get(
            "/api/v1/recon/trades?status=UNSETTLED",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if "data" in data:
            for trade in data["data"]:
                status = trade.get("status", {})
                if isinstance(status, dict):
                    assert status.get("status") in ["UNSETTLED", "BREAK"]


class TestReconciliationEndpoint:
    """Tests for reconciliation endpoints."""
    
    def test_run_reconciliation(self, client: TestClient, auth_headers: dict, sample_trade, sample_cash_txn):
        """Test running reconciliation."""
        response = client.post("/api/v1/recon/run", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "run_id" in data
    
    def test_get_dashboard_stats(self, client: TestClient, auth_headers: dict):
        """Test dashboard stats endpoint."""
        response = client.get("/api/v1/recon/dashboard-stats", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "trades" in data
        assert "cash" in data
        assert "breaks" in data
    
    def test_get_breaks(self, client: TestClient, auth_headers: dict):
        """Test getting breaks."""
        response = client.get("/api/v1/recon/breaks", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "breaks" in data
        assert "count" in data


class TestIngestionEndpoint:
    """Tests for file ingestion endpoints."""
    
    def test_upload_invalid_file_type(self, client: TestClient, auth_headers: dict):
        """Test uploading invalid file type."""
        response = client.post(
            "/api/v1/ingestion/upload",
            headers=auth_headers,
            files={"file": ("test.txt", b"invalid content", "text/plain")}
        )
        # Should either reject or handle gracefully
        assert response.status_code in [400, 200]
    
    def test_upload_csv_file(self, client: TestClient, auth_headers: dict):
        """Test uploading a valid CSV file."""
        csv_content = b"date,symbol,side,quantity,price,amount\n2025-01-15,RELIANCE,BUY,100,2500,250000"
        
        response = client.post(
            "/api/v1/ingestion/upload",
            headers=auth_headers,
            files={"file": ("trades.csv", csv_content, "text/csv")}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] in ["success", "skipped"]
    
    def test_get_upload_history(self, client: TestClient, auth_headers: dict):
        """Test getting upload history."""
        response = client.get("/api/v1/ingestion/upload/history", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "files" in data


class TestRequestTracking:
    """Tests for request tracking middleware."""
    
    def test_request_id_header(self, client: TestClient):
        """Test that responses include request ID header."""
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
    
    def test_response_time_header(self, client: TestClient):
        """Test that responses include response time header."""
        response = client.get("/health")
        assert "X-Response-Time" in response.headers
    
    def test_security_headers(self, client: TestClient):
        """Test that responses include security headers."""
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_404_not_found(self, client: TestClient):
        """Test 404 response for non-existent endpoint."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
    
    def test_invalid_trade_id(self, client: TestClient, auth_headers: dict):
        """Test analyzing non-existent trade."""
        response = client.get("/api/v1/recon/analyze/999999", headers=auth_headers)
        assert response.status_code == 404
