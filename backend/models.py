# backend/models.py

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, 
    Boolean, ForeignKey, Text, JSON, Enum, UniqueConstraint, Numeric, Index
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
    # Financial columns: Use Numeric for precision (15 total digits, 4 decimal places)
    quantity = Column(Numeric(15, 4))
    price = Column(Numeric(15, 4))
    amount = Column(Numeric(15, 2))  # Money: 2 decimals sufficient
    currency = Column(String, default="INR")
    
    source_file = Column(String)
    status = Column(String, default=ReconStatus.UNSETTLED)
    recon_id = Column(String, nullable=True)
    bank_ref = Column(String, nullable=True)
    
    __table_args__ = (
        Index('idx_broker_tenant_status_date', 'tenant_id', 'status', 'date'),
        Index('idx_broker_tenant_symbol', 'tenant_id', 'symbol'),
    )

class BankTxn(Base):
    __tablename__ = "bank_txns"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    
    date = Column(Date, index=True)
    value_date = Column(Date, nullable=True)
    description = Column(String)
    # Financial columns: Use Numeric for precision
    amount = Column(Numeric(15, 2))
    balance = Column(Numeric(15, 2), nullable=True)
    
    source_file = Column(String)
    status = Column(String, default="UNUSED")
    trade_ref = Column(Integer, ForeignKey("broker_trades.id"), nullable=True)
    
    __table_args__ = (
        Index('idx_bank_tenant_status', 'tenant_id', 'status'),
        Index('idx_bank_tenant_date', 'tenant_id', 'date'),
    )

class Holding(Base):
    __tablename__ = "holdings"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    
    date = Column(Date, index=True)
    isin = Column(String)
    symbol = Column(String, index=True)
    # Financial columns: Use Numeric for precision
    quantity = Column(Numeric(15, 4))
    total_value = Column(Numeric(15, 2))
    
    avg_cost = Column(Numeric(15, 4), default=0.0)
    market_price = Column(Numeric(15, 4), default=0.0)
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
    # Financial columns: Use Numeric for precision
    nav_value = Column(Numeric(15, 4))
    aum = Column(Numeric(15, 2))
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


# --- 3.0.1 IMMUTABLE AUDIT LOG (v2.1) ---

class AuditEvent(Base):
    """
    Immutable hash-chained audit event.
    
    CRITICAL: This table should have INSERT only privileges in production.
    No UPDATE or DELETE should ever be allowed.
    
    Hash chain: event_hash = sha256(prev_hash + payload + timestamp)
    This enables integrity verification and tamper detection.
    """
    __tablename__ = "audit_events"
    
    id = Column(String, primary_key=True)  # UUID
    tenant_id = Column(String, index=True, nullable=False)
    run_id = Column(String, index=True, nullable=True)  # Optional link to reconciliation run
    
    # Event metadata
    event_type = Column(String, nullable=False)  # PROPOSAL_CREATED, PROPOSAL_APPROVED, etc.
    entity_type = Column(String, nullable=False)  # TRADE, PROPOSAL, BREAK
    entity_id = Column(String, nullable=False)
    actor = Column(String, nullable=False)  # User ID who performed the action
    actor_role = Column(String, nullable=False, default="SYSTEM")  # OPS_ANALYST | SYSTEM | ADMIN
    
    # Event payload (structured data)
    payload = Column(JSON, nullable=True)
    
    # Hash chain for integrity
    prev_hash = Column(String(64), nullable=False)  # Hash of previous event (or "GENESIS")
    event_hash = Column(String(64), nullable=False, index=True)  # This event's hash
    
    # Timestamp (immutable)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# --- 3.1 RECONCILIATION RUN TRACKING (v2.1 - Idempotency) ---

class ReconciliationRun(Base):
    """
    Tracks each reconciliation run for idempotency and completeness.
    
    The run_id is CLIENT-SUPPLIED and immutable - this enables:
    - Idempotent retries (same run_id = same result)
    - Crash recovery (resume from where we left off)
    - Determinism under load
    
    A run cannot be marked COMPLETE until all expected_sources are received.
    """
    __tablename__ = "reconciliation_runs"
    
    id = Column(String, primary_key=True)  # CLIENT-SUPPLIED UUID, immutable
    tenant_id = Column(String, index=True, nullable=False)
    
    # Run metadata
    run_type = Column(String, nullable=False)  # SETTLEMENT, AI_RESOLVE, MANUAL
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="RUNNING")  # RUNNING, COMPLETE, FAILED, INCOMPLETE
    
    # Completeness tracking (prevents partial reconciliation)
    expected_sources = Column(Integer, default=1)  # How many files expected
    received_sources = Column(Integer, default=0)  # How many uploaded
    
    # Results
    trades_processed = Column(Integer, default=0)
    proposals_created = Column(Integer, default=0)
    breaks_created = Column(Integer, default=0)
    
    # Audit
    created_by = Column(String, nullable=True)


class ReconProposal(Base):
    """
    AI-generated reconciliation proposals.
    
    v2.1 MAKER-CHECKER:
    - created_by: User who triggered AI analysis
    - approved_by: MUST be different user (enforced at API level)
    - approved_at: MUST be later than created_at (temporal separation)
    """
    __tablename__ = "recon_proposals"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    run_id = Column(String, ForeignKey("reconciliation_runs.id"), nullable=True, index=True)

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
    
    # v2.1 Maker-Checker fields
    created_by = Column(String, nullable=True)   # User who triggered analysis
    approved_by = Column(String, nullable=True)  # MUST be different user
    approved_at = Column(DateTime, nullable=True)  # MUST be after created_at
    
    # Idempotency: prevent duplicate proposals for same trade in same run
    __table_args__ = (
        UniqueConstraint('run_id', 'trade_id', name='uq_run_trade_proposal'),
    )


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

# --- 6. GLASS-BOX INGESTION PIPELINE (v3.0) ---

class IngestionSession(Base):
    """
    Stage 1: UPLOAD & STAGING
    Tracks the lifecycle of a file upload before any processing occurs.
    """
    __tablename__ = "ingestion_sessions"

    id = Column(String, primary_key=True)  # UUID
    tenant_id = Column(String, index=True, nullable=False)
    
    # File Metadata
    filename = Column(String, nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA256 deduplication key
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=False)  # S3/MinIO path
    
    status = Column(String, default="ANALYZING")  # ANALYZING, DRAFT, SIGNED, EXECUTING, COMPLETED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    contract = relationship("IngestionContract", uselist=False, back_populates="session")


class IngestionContract(Base):
    """
    Stage 2-4: PROPOSAL & APPROVAL (The Legal Document)
    Stores the negotiated schema mapping and intent.
    Immutable once signed.
    """
    __tablename__ = "ingestion_contracts"

    id = Column(String, primary_key=True)  # UUID
    session_id = Column(String, ForeignKey("ingestion_sessions.id"), unique=True, nullable=False)
    tenant_id = Column(String, index=True, nullable=False)
    
    # Lineage (Drift Detection)
    parent_contract_id = Column(String, ForeignKey("ingestion_contracts.id"), nullable=True)  # Link to previous version
    schema_signature = Column(String, index=True)  # Hash of ordered headers + types
    
    # The Deal
    dataset_type = Column(String, nullable=False)  # TRADE, CASH, NAV, HOLDING
    schema_mapping = Column(JSON, nullable=False)  # { "SourceCol": "TargetField" }
    
    # Metadata & Trust
    confidence = Column(JSON, nullable=False)  # Detailed breakdown { "score": 0.98, "provenance": [...] }
    status = Column(String, default="DRAFT")  # DRAFT, SIGNED, REJECTED
    
    # Sign-off (Non-repudiation)
    signed_by = Column(String, nullable=True)
    signed_at = Column(DateTime, nullable=True)
    
    # Relationships
    session = relationship("IngestionSession", back_populates="contract")
    execution = relationship("IngestionExecution", uselist=False, back_populates="contract")
    # parent = relationship("IngestionContract", remote_side=[id]) # Self-referential if needed


class IngestionExecution(Base):
    """
    Stage 5: EXECUTION (The Commitment)
    Tracks the actual database write operation after approval.
    """
    __tablename__ = "ingestion_executions"

    id = Column(String, primary_key=True)  # UUID
    contract_id = Column(String, ForeignKey("ingestion_contracts.id"), unique=True, nullable=False)
    tenant_id = Column(String, index=True, nullable=False)
    
    status = Column(String, default="QUEUED")  # QUEUED, PROCESSING, COMPLETED, FAILED
    
    # Results
    rows_ingested = Column(Integer, default=0)
    error_log = Column(Text, nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    contract = relationship("IngestionContract", back_populates="execution")
