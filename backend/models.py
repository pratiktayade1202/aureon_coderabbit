# backend/models.py

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, 
    Boolean, ForeignKey, Text, JSON, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

# CRITICAL FIX: Import the shared Base from database.py
# Do NOT create a new declarative_base() here.
from .database import Base 

# --- ENUMS FOR STANDARDIZATION ---
class ReconStatus(str, enum.Enum):
    UNSETTLED = "UNSETTLED"
    PARTIAL = "PARTIAL"
    MATCHED = "MATCHED"
    BREAK = "BREAK" 

class BreakSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class RuleTier(str, enum.Enum):
    TIER_1_DETERMINISTIC = "TIER_1"
    TIER_2_TOLERANCE = "TIER_2"
    TIER_3_AI = "TIER_3"

# --- 1. CORE DATA TABLES ---

class BrokerTrade(Base):
    __tablename__ = "broker_trades"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    
    date = Column(Date, index=True)
    settlement_date = Column(Date, nullable=True)
    symbol = Column(String, index=True)
    isin = Column(String, index=True)
    side = Column(String) 
    quantity = Column(Float)
    price = Column(Float)
    amount = Column(Float) 
    currency = Column(String, default="INR")
    
    source_file = Column(String)
    status = Column(String, default=ReconStatus.UNSETTLED)
    recon_id = Column(String, nullable=True)
    bank_ref = Column(String, nullable=True)

class BankTxn(Base):
    __tablename__ = "bank_txns"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    
    date = Column(Date, index=True)
    value_date = Column(Date, nullable=True)
    description = Column(String)
    amount = Column(Float)
    balance = Column(Float, nullable=True)
    
    source_file = Column(String)
    status = Column(String, default="UNUSED")
    trade_ref = Column(Integer, ForeignKey("broker_trades.id"), nullable=True)

class Holding(Base):
    __tablename__ = "holdings"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    
    date = Column(Date, index=True)
    isin = Column(String)
    symbol = Column(String, index=True)
    quantity = Column(Float)
    total_value = Column(Float)
    
    avg_cost = Column(Float, default=0.0)
    market_price = Column(Float, default=0.0)
    source_file = Column(String)

    __table_args__ = (
        UniqueConstraint('symbol', 'tenant_id', name='uq_holding_symbol_tenant'),
    )

class NavLog(Base):
    __tablename__ = "nav_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    
    date = Column(Date)
    fund_name = Column(String)
    isin = Column(String, nullable=True)
    nav_value = Column(Float)
    aum = Column(Float)
    source_file = Column(String)

# --- 2. RULE ENGINE TABLES ---

class RuleDefinition(Base):
    __tablename__ = "rule_definitions"
    
    rule_id = Column(String, primary_key=True)
    name = Column(String)
    description = Column(String)
    domain = Column(String)
    tier = Column(Enum(RuleTier), default=RuleTier.TIER_1_DETERMINISTIC)
    is_active = Column(Boolean, default=True)
    tolerance_threshold = Column(Float, default=0.0)

class ReconBreak(Base):
    __tablename__ = "recon_breaks"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    
    trade_id = Column(Integer, ForeignKey("broker_trades.id"), nullable=True)
    cash_id = Column(Integer, ForeignKey("bank_txns.id"), nullable=True)
    
    rule_id = Column(String, ForeignKey("rule_definitions.rule_id"))
    break_type = Column(String)
    severity = Column(Enum(BreakSeverity), default=BreakSeverity.MEDIUM)
    
    amount_diff = Column(Float, default=0.0)
    age_days = Column(Integer, default=0)
    status = Column(String, default="OPEN")
    
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# --- 3. AUDIT & MEMORY ---

class ReconLog(Base):
    __tablename__ = "recon_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    trade_id = Column(Integer, nullable=True)
    cash_id = Column(Integer, nullable=True)
    rule_id = Column(String, nullable=True)
    status_before = Column(String)
    status_after = Column(String)
    reason = Column(String)
    agent_model = Column(String)


class ReconProposal(Base):
    __tablename__ = "recon_proposals"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)

    # What is the AI proposing?
    trade_id = Column(Integer, ForeignKey("broker_trades.id"))
    cash_id = Column(Integer, ForeignKey("bank_txns.id"), nullable=True)
    break_id = Column(Integer, ForeignKey("recon_breaks.id"), nullable=True)

    # Why?
    confidence = Column(Float)
    explanation = Column(String)
    source_model = Column(String)  # "Gemini-2.0-Flash", "GPT-4o"

    # Status of the proposal itself
    status = Column(String, default="PENDING")  # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)


class RuleMemory(Base):
    __tablename__ = "rule_memory"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, index=True)
    pattern_hash = Column(String, index=True)
    learned_rule_json = Column(JSON)
    confidence_score = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    times_applied = Column(Integer, default=0)

class LearningEvent(Base):
    __tablename__ = "learning_events"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String)
    trade_id = Column(Integer)
    status = Column(String)
    source = Column(String)
    trade_data = Column(JSON)
    correction_notes = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# --- 4. FILE PROCESSING TRACKING ---

class ProcessedFile(Base):
    __tablename__ = "processed_files"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    filename = Column(String, nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA256
    file_size = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    processed_at = Column(DateTime, default=datetime.utcnow)
    rows_processed = Column(Integer, default=0)
    errors = Column(Text, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'file_hash', name='uq_processed_file_tenant_hash'),
    )

# --- 5. TENANT ISOLATION (MUTEX LOCKS) ---

class ReconLock(Base):
    """
    Mutex lock to prevent concurrent heavy operations for a single tenant.
    Only one "Heavy Job" can run per tenant at a time.
    """
    __tablename__ = "recon_locks"
    
    tenant_id = Column(String, primary_key=True, index=True)
    locked_until = Column(DateTime, nullable=False)
    process_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
