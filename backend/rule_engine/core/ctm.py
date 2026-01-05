# backend/rule_engine/core/ctm.py

from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class CanonicalTrade:
    """
    Standardized Trade Object for Rule Engine.
    Decouples logic from specific DB models.
    """
    id: str  # Unique ID (internal or external)
    trade_date: date
    settlement_date: Optional[date]
    symbol: str
    isin: Optional[str]
    side: str  # BUY / SELL
    quantity: float
    price: float
    net_amount: float
    currency: str
    source_ref: Optional[str] = None

@dataclass
class CanonicalCash:
    """
    Standardized Cash Entry for Rule Engine.
    """
    id: str
    date: date
    value_date: Optional[date]
    amount: float
    currency: str
    description: str
    type: str = "CASH" # CASH, FEE, DIVIDEND

def to_canonical_trade(db_trade) -> CanonicalTrade:
    """Helper to convert DB model to Canonical Trade"""
    return CanonicalTrade(
        id=str(db_trade.id),
        trade_date=db_trade.date,
        settlement_date=db_trade.settlement_date,
        symbol=str(db_trade.symbol).upper().strip(),
        isin=str(db_trade.isin).upper().strip() if db_trade.isin else None,
        side=str(db_trade.side).upper().strip(),
        quantity=float(db_trade.quantity),
        price=float(db_trade.price),
        net_amount=float(db_trade.amount),
        currency=str(db_trade.currency).upper() if hasattr(db_trade, 'currency') else "INR",
        source_ref=db_trade.source_file
    )

def to_canonical_cash(db_txn) -> CanonicalCash:
    """Helper to convert DB model to Canonical Cash"""
    return CanonicalCash(
        id=str(db_txn.id),
        date=db_txn.date,
        value_date=db_txn.value_date,
        amount=float(db_txn.amount),
        currency="INR", # Default for now, extend later
        description=str(db_txn.description).upper(),
        type="CASH"
    )

@dataclass
class CanonicalHolding:
    """
    Standardized Holding Object for Position Reconciliation.
    """
    id: str                 # Unique ID or composite key
    date: date              # As-of date
    isin: Optional[str]     # Primary Key for Instl (ISIN > Symbol)
    symbol: str             # Human readable
    
    # Quantity Buckets
    quantity_total: float   # The aggregate number
    quantity_free: float    # Tradeable
    quantity_pledged: float # Locked/Margin
    
    # Valuation
    market_price: float
    total_value: float
    currency: str
    
    source: str             # "INTERNAL_BOOKS" or "CUSTODIAN_FILE"
    account_type: str       # "POOL", "CLIENT", "OWN"