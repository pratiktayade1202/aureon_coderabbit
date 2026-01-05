#!/bin/bash
# Activate virtual environment if it exists
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

# Require DATABASE_URL from environment (no hardcoded credentials)
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is required"
    exit 1
fi

echo "========================================================"
echo "          AUREON SYSTEM DIAGNOSTIC REPORT"
echo "========================================================"
date
echo ""

echo "### 1. PROCESS CONTROL"
echo "--------------------------------------------------------"
echo "[CHECK] ps aux | grep uvicorn"
ps aux | grep uvicorn | grep -v grep
echo ""
echo "[CHECK] lsof -i :8000"
lsof -i :8000
echo ""

echo "### 2. DATABASE (POSTGRES)"
echo "--------------------------------------------------------"
echo "[CHECK] psql \dt"
psql $DATABASE_URL -c "\dt" || echo "ERROR: psql connection failed"
echo ""
echo "[CHECK] psql \d audit_events"
psql $DATABASE_URL -c "\d audit_events" || echo "ERROR: table check failed"
echo ""

echo "### 3. ALEMBIC"
echo "--------------------------------------------------------"
echo "[CHECK] alembic current"
alembic current || echo "ERROR: alembic failed"
echo ""

echo "### 4. ORM REFLECTION"
echo "--------------------------------------------------------"
echo "[CHECK] backend/ops_check_schema.py"
python backend/ops_check_schema.py || echo "ERROR: python script failed"
echo ""

echo "### 7. API VERIFICATION"
echo "--------------------------------------------------------"
echo "[CHECK] /api/v1/recon/system/health"
curl -s http://localhost:8000/api/v1/recon/system/health | python -m json.tool || echo "API Unreachable"
echo ""
echo "[CHECK] /api/v1/recon/system/info"
curl -s http://localhost:8000/api/v1/recon/system/info | python -m json.tool || echo "API Unreachable"
echo ""

echo "### 9. TESTS (Deterministic Core)"
echo "--------------------------------------------------------"
# Using coverage or direct python execution as requested
python -m backend.rule_engine.tests.test_deterministic_core 2>&1 || echo "Tests Failed"
echo ""
echo "========================================================"
echo "DIAGNOSTIC COMPLETE"
echo "========================================================"
