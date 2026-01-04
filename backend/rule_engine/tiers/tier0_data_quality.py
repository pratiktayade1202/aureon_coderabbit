# backend/rule_engine/tiers/tier0_data_quality.py
"""
Tier 0: Data Quality Gate Rules.

These rules run BEFORE any matching logic.
Failures here = record rejected, no further processing.

AI is FORBIDDEN at this tier.
"""

from typing import Dict, Any, List
from ..core.result import RuleResult
import logging

logger = logging.getLogger(__name__)


class DataQualityGate:
    """
    Data Quality validation rules.
    
    All rules in this tier:
    - Are deterministic (no AI)
    - Return hard failures (is_hard_fail=True)
    - Prevent record from entering matching pipeline
    """
    
    TIER = 0
    
    # Required fields for trades
    TRADE_REQUIRED_FIELDS = [
        "amount", "date", "currency", "side"
    ]
    
    # Required fields for cash
    CASH_REQUIRED_FIELDS = [
        "amount", "date", "currency"
    ]
    
    # Valid currency codes (ISO 4217 subset for India)
    VALID_CURRENCIES = {"INR", "USD", "EUR", "GBP", "JPY", "SGD", "AED"}
    
    @classmethod
    def run_all(cls, record: Dict[str, Any], record_type: str = "trade") -> List[RuleResult]:
        """
        Run all data quality checks on a record.
        
        Args:
            record: Trade or cash record dict
            record_type: "trade" or "cash"
            
        Returns:
            List of RuleResult for each check
        """
        results = []
        
        results.append(cls.dq_001_mandatory_fields(record, record_type))
        results.append(cls.dq_002_date_format(record))
        results.append(cls.dq_003_amount_valid(record))
        results.append(cls.dq_004_currency_valid(record))
        results.append(cls.dq_005_identifier_present(record, record_type))
        
        return results
    
    @classmethod
    def dq_001_mandatory_fields(cls, record: Dict[str, Any], 
                                 record_type: str = "trade") -> RuleResult:
        """
        DQ_001: All mandatory fields must be present and non-null.
        """
        required = cls.TRADE_REQUIRED_FIELDS if record_type == "trade" else cls.CASH_REQUIRED_FIELDS
        missing = [f for f in required if f not in record or record.get(f) is None]
        
        if missing:
            return RuleResult(
                rule_id="DQ_001",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,  # Gate rules don't contribute to confidence
                passed=False,
                is_hard_fail=True,
                failure_mode="MISSING_MANDATORY_FIELDS",
                break_type="DATA_QUALITY",
                severity="CRITICAL",
                message=f"Missing required fields: {', '.join(missing)}",
                justification=f"Record type '{record_type}' requires fields: {required}. Missing: {missing}",
                raw_values={"missing_fields": missing, "required": required}
            )
        
        return RuleResult(
            rule_id="DQ_001",
            tier=cls.TIER,
            score=1.0,
            weight=0.0,
            passed=True,
            message="All mandatory fields present",
            justification=f"All {len(required)} required fields validated"
        )
    
    @classmethod
    def dq_002_date_format(cls, record: Dict[str, Any]) -> RuleResult:
        """
        DQ_002: Date field must be valid format.
        """
        date_val = record.get("date")
        
        if date_val is None:
            # Already caught by DQ_001
            return RuleResult(
                rule_id="DQ_002",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="MISSING_DATE",
                message="Date field is missing"
            )
        
        # Check if it's a valid date-like object or string
        try:
            from datetime import datetime, date
            
            if isinstance(date_val, (datetime, date)):
                valid = True
            elif isinstance(date_val, str):
                # Try common formats
                for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"]:
                    try:
                        datetime.strptime(date_val, fmt)
                        valid = True
                        break
                    except ValueError:
                        continue
                else:
                    valid = False
            else:
                valid = False
                
        except Exception as e:
            valid = False
        
        if not valid:
            return RuleResult(
                rule_id="DQ_002",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="INVALID_DATE_FORMAT",
                break_type="DATA_QUALITY",
                severity="CRITICAL",
                message=f"Invalid date format: {date_val}",
                raw_values={"date_value": str(date_val)}
            )
        
        return RuleResult(
            rule_id="DQ_002",
            tier=cls.TIER,
            score=1.0,
            weight=0.0,
            passed=True,
            message="Date format valid"
        )
    
    @classmethod
    def dq_003_amount_valid(cls, record: Dict[str, Any]) -> RuleResult:
        """
        DQ_003: Amount must be numeric and reasonable.
        """
        amount = record.get("amount")
        
        try:
            amount_float = float(amount)
            # Allow negative (for credits) but flag extreme values
            if abs(amount_float) > 1e12:  # > 1 trillion is suspicious
                return RuleResult(
                    rule_id="DQ_003",
                    tier=cls.TIER,
                    score=0.0,
                    weight=0.0,
                    passed=False,
                    is_hard_fail=True,
                    failure_mode="AMOUNT_UNREASONABLE",
                    message=f"Amount {amount_float} exceeds reasonable bounds",
                    raw_values={"amount": amount_float}
                )
        except (TypeError, ValueError):
            return RuleResult(
                rule_id="DQ_003",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="AMOUNT_NOT_NUMERIC",
                break_type="DATA_QUALITY",
                severity="CRITICAL",
                message=f"Amount is not numeric: {amount}",
                raw_values={"amount_raw": str(amount)}
            )
        
        return RuleResult(
            rule_id="DQ_003",
            tier=cls.TIER,
            score=1.0,
            weight=0.0,
            passed=True,
            message=f"Amount valid: {amount_float}"
        )
    
    @classmethod
    def dq_004_currency_valid(cls, record: Dict[str, Any]) -> RuleResult:
        """
        DQ_004: Currency code must be valid ISO 4217.
        """
        currency = (record.get("currency") or "").upper().strip()
        
        if not currency:
            return RuleResult(
                rule_id="DQ_004",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="MISSING_CURRENCY",
                message="Currency code missing"
            )
        
        if currency not in cls.VALID_CURRENCIES:
            return RuleResult(
                rule_id="DQ_004",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="INVALID_CURRENCY_CODE",
                break_type="DATA_QUALITY",
                severity="CRITICAL",
                message=f"Invalid currency code: {currency}",
                raw_values={"currency": currency, "valid_codes": list(cls.VALID_CURRENCIES)}
            )
        
        return RuleResult(
            rule_id="DQ_004",
            tier=cls.TIER,
            score=1.0,
            weight=0.0,
            passed=True,
            message=f"Currency valid: {currency}"
        )
    
    @classmethod
    def dq_005_identifier_present(cls, record: Dict[str, Any], 
                                  record_type: str = "trade") -> RuleResult:
        """
        DQ_005: At least one identifier must be present.
        For trades: ISIN, symbol, or trade_ref
        For cash: id or txn_ref
        """
        if record_type == "trade":
            identifiers = ["isin", "symbol", "trade_ref", "id"]
        else:
            identifiers = ["id", "txn_ref", "reference"]
        
        has_identifier = any(record.get(f) for f in identifiers)
        
        if not has_identifier:
            return RuleResult(
                rule_id="DQ_005",
                tier=cls.TIER,
                score=0.0,
                weight=0.0,
                passed=False,
                is_hard_fail=True,
                failure_mode="MISSING_IDENTIFIER",
                break_type="DATA_QUALITY",
                severity="CRITICAL",
                message=f"No identifier present. Checked: {identifiers}",
                raw_values={"checked_fields": identifiers}
            )
        
        found = [f for f in identifiers if record.get(f)]
        return RuleResult(
            rule_id="DQ_005",
            tier=cls.TIER,
            score=1.0,
            weight=0.0,
            passed=True,
            message=f"Identifier found: {found[0]}",
            raw_values={"found_identifiers": found}
        )
