# backend/constants.py
"""
Centralized constants and enums for the Aureon backend.
Replaces magic numbers and strings throughout the codebase.
"""
from enum import Enum


class ConfidenceThreshold:
    """AI confidence thresholds for matching decisions."""
    HIGH = 0.95
    MEDIUM = 0.85
    LOW = 0.70
    PROPOSAL_MINIMUM = 0.80


class TradeStatus:
    """Trade reconciliation status values."""
    MATCHED = "MATCHED"
    UNSETTLED = "UNSETTLED"
    BREAK = "BREAK"
    PARTIAL = "PARTIAL"


class ProposalStatus:
    """AI proposal status values."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class BreakSeverityLevel:
    """Break severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ResolutionType:
    """How a trade was resolved."""
    RULE = "RULE"
    MANUAL = "MANUAL"
    AI = "AI"
    UNKNOWN = "UNKNOWN"


class ActorRole:
    """Actor roles for audit events."""
    OPS_ANALYST = "OPS_ANALYST"
    SYSTEM = "SYSTEM"
    ADMIN = "ADMIN"
    AI_AGENT = "AI_AGENT"


# Pagination limits
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50

# File upload limits
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_FILES_PER_BATCH = 10

# Rate limiting (requests per minute)
RATE_LIMIT_UPLOAD = 10
RATE_LIMIT_SETTLEMENT = 5
RATE_LIMIT_AI_RESOLVE = 5

# Lock timeouts (seconds)
DEFAULT_LOCK_TIMEOUT = 300

# Amount tolerance for matching
AMOUNT_TOLERANCE_PERCENT = 1.0

# ZIP safety limits
MAX_ZIP_COMPRESSION_RATIO = 100
MAX_UNCOMPRESSED_SIZE_BYTES = 500 * 1024 * 1024  # 500MB
