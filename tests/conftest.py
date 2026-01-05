# tests/conftest.py
"""
Pytest configuration and shared fixtures.
"""
import os
import pytest
from typing import Generator
from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Set test environment before importing app
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from backend.main import app
from backend.database import Base, get_db
from backend.models import (
    BrokerTrade,
    BankTxn,
    Holding,
    ReconBreak,
    ProcessedFile,
)

# Test database
TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    """Override database dependency for tests."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test database tables."""
    Base.metadata.create_all(bind=test_engine)
    yield
    # Cleanup after all tests
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a clean database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Provide a test client with database override."""
    app.dependency_overrides[get_db] = lambda: db_session
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict:
    """Provide authentication headers for API calls."""
    return {"Authorization": "Bearer dev-token"}


@pytest.fixture
def sample_trade(db_session: Session) -> BrokerTrade:
    """Create a sample trade for testing."""
    trade = BrokerTrade(
        tenant_id="test_tenant",
        date=date.today(),
        symbol="RELIANCE",
        isin="INE002A01018",
        side="BUY",
        quantity=100.0,
        price=2500.0,
        amount=250000.0,
        currency="INR",
        status="UNSETTLED",
        source_file="test_trades.csv"
    )
    db_session.add(trade)
    db_session.commit()
    db_session.refresh(trade)
    return trade


@pytest.fixture
def sample_cash_txn(db_session: Session) -> BankTxn:
    """Create a sample cash transaction for testing."""
    txn = BankTxn(
        tenant_id="test_tenant",
        date=date.today(),
        description="NEFT-RELIANCE",
        amount=-250000.0,
        status="UNUSED",
        source_file="test_ledger.csv"
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)
    return txn


@pytest.fixture
def sample_holding(db_session: Session) -> Holding:
    """Create a sample holding for testing."""
    holding = Holding(
        tenant_id="test_tenant",
        date=date.today(),
        symbol="RELIANCE",
        isin="INE002A01018",
        quantity=100.0,
        avg_cost=2400.0,
        market_price=2500.0,
        total_value=250000.0,
        source_file="test_holdings.csv"
    )
    db_session.add(holding)
    db_session.commit()
    db_session.refresh(holding)
    return holding


@pytest.fixture
def multiple_trades(db_session: Session) -> list:
    """Create multiple trades for pagination testing."""
    trades = []
    for i in range(25):
        trade = BrokerTrade(
            tenant_id="test_tenant",
            date=date.today(),
            symbol=f"STOCK{i:02d}",
            isin=f"INE00{i:02d}A01018",
            side="BUY" if i % 2 == 0 else "SELL",
            quantity=float(100 + i * 10),
            price=float(1000 + i * 100),
            amount=float((100 + i * 10) * (1000 + i * 100)),
            currency="INR",
            status="UNSETTLED" if i % 3 == 0 else "MATCHED",
            source_file="test_batch.csv"
        )
        trades.append(trade)
    
    db_session.add_all(trades)
    db_session.commit()
    
    for trade in trades:
        db_session.refresh(trade)
    
    return trades
