# backend/rule_engine/core/smart_matcher.py
"""
Smart Matcher (v2.1)

Replaces the binary pass/fail vectorized matcher with a confidence-based
scoring system that supports:
- Multi-tier matching (Exact → Standard → Fuzzy)
- M:N matching for partial fills
- Deterministic explainability (no prose)
- Configurable tolerances

Philosophy: "If it's not obviously correct, it lands in REVIEW."
"""
import logging
import re
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from .match_config import MatchConfig, MatchScore

logger = logging.getLogger(__name__)


class SmartMatcher:
    """
    Confidence-based trade-cash matcher.
    
    Unlike the old binary matcher, this returns confidence scores
    that allow for nuanced decision-making:
    - PROPOSE (≥0.85): High confidence, can auto-resolve
    - REVIEW (0.60-0.85): Needs human review
    - BREAK (<0.60): Create break record
    """
    
    def __init__(self, config: Optional[MatchConfig] = None):
        self.config = config or MatchConfig()
    
    def score_match(self, trade: Dict, cash: Dict) -> MatchScore:
        """
        Score a potential trade-cash match.
        
        Returns a MatchScore with:
        - Overall confidence (0.0-1.0)
        - Action (PROPOSE/REVIEW/BREAK)
        - Match tier (EXACT/STANDARD/FUZZY/NONE)
        - Component breakdown (amount, date, reference, description)
        """
        # Extract amounts
        trade_amt = abs(self._to_float(trade.get("net_amount") or trade.get("amount")))
        cash_amt = abs(self._to_float(cash.get("amount")))
        
        # Calculate amount difference
        if trade_amt > 0:
            diff = abs(trade_amt - cash_amt)
            diff_pct = diff / trade_amt
        else:
            diff = abs(cash_amt)
            diff_pct = 1.0 if cash_amt != 0 else 0.0
        
        # === Amount Scoring (weight: 0.40) ===
        amount_score, match_tier = self._score_amount(diff_pct)
        
        # === Date Scoring (weight: 0.20) ===
        date_score, date_diff = self._score_date(trade, cash)
        
        # === Reference Scoring (weight: 0.20) ===
        reference_score, matched_refs = self._score_references(trade, cash)
        
        # === Description Scoring (weight: 0.20) ===
        description_score = self._score_description(trade, cash) if self.config.enable_fuzzy_description else 0.0
        
        # === Weighted Total ===
        total_score = (
            amount_score * self.config.weight_amount +
            date_score * self.config.weight_date +
            reference_score * self.config.weight_reference +
            description_score * self.config.weight_description
        )
        
        # Determine action based on score
        if total_score >= self.config.auto_match_threshold:
            action = "PROPOSE"
        elif total_score >= self.config.review_threshold:
            action = "REVIEW"
        else:
            action = "BREAK"
        
        return MatchScore(
            score=total_score,
            action=action,
            match_tier=match_tier,
            amount_score=amount_score,
            date_score=date_score,
            reference_score=reference_score,
            description_score=description_score,
            amount_diff=diff,
            amount_diff_pct=diff_pct,
            date_diff_days=date_diff,
            matched_references=matched_refs,
        )
    
    def _score_amount(self, diff_pct: float) -> Tuple[float, str]:
        """Score based on amount difference percentage."""
        if diff_pct <= self.config.exact_tolerance:
            return 1.0, "EXACT"
        elif diff_pct <= self.config.standard_tolerance:
            # Linear interpolation between exact and standard
            ratio = diff_pct / self.config.standard_tolerance
            return 0.85 + (1.0 - 0.85) * (1 - ratio), "STANDARD"
        elif diff_pct <= self.config.fuzzy_tolerance:
            # Linear interpolation between standard and fuzzy
            ratio = (diff_pct - self.config.standard_tolerance) / (self.config.fuzzy_tolerance - self.config.standard_tolerance)
            return 0.60 + (0.85 - 0.60) * (1 - ratio), "FUZZY"
        else:
            # Beyond fuzzy tolerance
            return 0.0, "NONE"
    
    def _score_date(self, trade: Dict, cash: Dict) -> Tuple[float, int]:
        """Score based on date proximity."""
        trade_date = self._to_date(trade.get("settlement_date") or trade.get("date"))
        cash_date = self._to_date(cash.get("value_date") or cash.get("date"))
        
        if not trade_date or not cash_date:
            return 0.5, 0  # Neutral score if dates missing
        
        try:
            diff_days = abs((cash_date - trade_date).days)
        except (TypeError, AttributeError):
            return 0.5, 0
        
        if diff_days == 0:
            return 1.0, 0
        elif diff_days <= self.config.date_tolerance_days:
            # Linear decay within tolerance
            return 1.0 - (diff_days / self.config.date_tolerance_days) * 0.5, diff_days
        else:
            # Beyond tolerance, steep decay
            return max(0.0, 0.5 - (diff_days - self.config.date_tolerance_days) * 0.1), diff_days
    
    def _score_references(self, trade: Dict, cash: Dict) -> Tuple[float, List[str]]:
        """Score based on reference ID matches."""
        narrative = self._normalize(
            cash.get("description") or cash.get("narrative") or ""
        )
        
        if not narrative:
            return 0.3, []  # Low score if no narrative
        
        keys_to_check = ["id", "trade_ref", "isin", "order_id", "broker_ref", "symbol"]
        matched = []
        
        for key in keys_to_check:
            val = self._normalize(str(trade.get(key) or ""))
            # Only match if reasonably unique (len > 4)
            if len(val) > 4 and val in narrative:
                matched.append(f"{key}={trade.get(key)}")
        
        if len(matched) >= 2:
            return 1.0, matched
        elif len(matched) == 1:
            return 0.7, matched
        else:
            return 0.0, []
    
    def _score_description(self, trade: Dict, cash: Dict) -> float:
        """Score based on description/symbol similarity."""
        trade_symbol = self._normalize(trade.get("symbol") or "")
        cash_desc = self._normalize(cash.get("description") or "")
        
        if not trade_symbol or not cash_desc:
            return 0.3
        
        if trade_symbol in cash_desc:
            return 1.0
        
        # Check for partial matches (first 5 chars)
        if len(trade_symbol) >= 5 and trade_symbol[:5] in cash_desc:
            return 0.6
        
        return 0.0
    
    def find_best_matches(
        self, 
        trades: List[Dict], 
        cash_entries: List[Dict],
        top_n: int = 3
    ) -> Dict[int, List[Tuple[int, MatchScore]]]:
        """
        Find best matches for each trade.
        
        Returns:
            Dict mapping trade index to list of (cash_index, MatchScore) sorted by score
        """
        results = {}
        
        for t_idx, trade in enumerate(trades):
            candidates = []
            
            for c_idx, cash in enumerate(cash_entries):
                score = self.score_match(trade, cash)
                if score.score > 0.3:  # Only keep viable candidates
                    candidates.append((c_idx, score))
            
            # Sort by score descending
            candidates.sort(key=lambda x: x[1].score, reverse=True)
            results[t_idx] = candidates[:top_n]
        
        return results
    
    def find_partial_fill_matches(
        self,
        trade: Dict,
        cash_entries: List[Dict]
    ) -> Optional[Tuple[List[int], MatchScore]]:
        """
        Find M:N matches for partial fills.
        
        A trade may be settled by multiple cash entries (partial fills).
        This finds combinations that sum to the trade amount.
        """
        if not self.config.enable_partial_matching:
            return None
        
        trade_amt = abs(self._to_float(trade.get("net_amount") or trade.get("amount")))
        if trade_amt <= 0:
            return None
        
        # Simple greedy approach: find cash entries that sum close to trade
        remaining = trade_amt
        matched_indices = []
        total_cash = 0.0
        
        # Sort cash by amount descending
        indexed_cash = [(i, abs(self._to_float(c.get("amount")))) for i, c in enumerate(cash_entries)]
        indexed_cash.sort(key=lambda x: x[1], reverse=True)
        
        for idx, amt in indexed_cash:
            if amt <= remaining * 1.1:  # Allow 10% overshoot
                matched_indices.append(idx)
                total_cash += amt
                remaining = trade_amt - total_cash
                
                if remaining <= trade_amt * self.config.standard_tolerance:
                    break
        
        if not matched_indices:
            return None
        
        # Calculate match score for the combination
        diff_pct = abs(trade_amt - total_cash) / trade_amt
        
        if diff_pct <= self.config.standard_tolerance:
            return matched_indices, MatchScore(
                score=0.80,  # Partials get slightly lower confidence
                action="PROPOSE",
                match_tier="PARTIAL_FILL",
                amount_diff=abs(trade_amt - total_cash),
                amount_diff_pct=diff_pct,
            )
        elif diff_pct <= self.config.fuzzy_tolerance:
            return matched_indices, MatchScore(
                score=0.65,
                action="REVIEW",
                match_tier="PARTIAL_FILL",
                amount_diff=abs(trade_amt - total_cash),
                amount_diff_pct=diff_pct,
            )
        
        return None
    
    # === Utility Methods ===
    
    def _to_float(self, value: Any) -> float:
        """Safe conversion to float."""
        try:
            if value is None:
                return 0.0
            s_val = str(value).replace(",", "").replace("$", "").replace("₹", "").replace("€", "")
            return float(s_val)
        except (ValueError, TypeError):
            return 0.0
    
    def _to_date(self, value: Any) -> Optional[date]:
        """Safe conversion to date."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        # Add more parsing if needed
        return None
    
    def _normalize(self, s: str) -> str:
        """Normalize string for matching."""
        if not s:
            return ""
        return re.sub(r"[^A-Z0-9]", "", s.upper())


# === Break Classifier ===

class BreakClassifier:
    """
    Categorizes breaks for intelligent prioritization.
    
    Categories optimized for operations workflow:
    - CRITICAL: Needs immediate attention
    - HIGH: Same-day resolution
    - MEDIUM: Can wait for review cycle
    - LOW: Likely noise, batch resolve
    """
    
    CATEGORIES = {
        "MISSING_CASH": {
            "description": "No cash entry found for trade",
            "priority": "CRITICAL",
            "auto_resolvable": False,
        },
        "AMOUNT_MAJOR": {
            "description": "Amount differs by more than 5%",
            "priority": "HIGH",
            "auto_resolvable": False,
        },
        "AMOUNT_MINOR": {
            "description": "Amount within 5%, likely rounding or fees",
            "priority": "LOW",
            "auto_resolvable": True,
        },
        "TIMING": {
            "description": "Date mismatch beyond T+2",
            "priority": "MEDIUM",
            "auto_resolvable": True,
        },
        "PARTIAL_FILL": {
            "description": "Cash is fraction of trade (possible partial)",
            "priority": "MEDIUM",
            "auto_resolvable": False,
        },
        "NETTING": {
            "description": "Multiple trades netted to single cash",
            "priority": "MEDIUM",
            "auto_resolvable": False,
        },
        "CURRENCY_MISMATCH": {
            "description": "Currency codes don't match",
            "priority": "HIGH",
            "auto_resolvable": False,
        },
    }
    
    @classmethod
    def classify(cls, trade: Dict, cash: Optional[Dict], match_score: Optional[MatchScore]) -> str:
        """
        Classify a break based on trade, cash, and match score.
        """
        if cash is None or not cash:
            return "MISSING_CASH"
        
        if match_score is None:
            return "MISSING_CASH"
        
        # Check amount difference
        if match_score.amount_diff_pct > 0.05:
            return "AMOUNT_MAJOR"
        elif match_score.amount_diff_pct > 0.01:
            return "AMOUNT_MINOR"
        
        # Check timing
        if match_score.date_diff_days > 2:
            return "TIMING"
        
        # Check for partial fill pattern
        if match_score.match_tier == "PARTIAL_FILL":
            return "PARTIAL_FILL"
        
        # Check currency
        trade_ccy = (trade.get("currency") or "").upper()
        cash_ccy = (cash.get("currency") or "INR").upper()
        if trade_ccy and cash_ccy and trade_ccy != cash_ccy:
            return "CURRENCY_MISMATCH"
        
        # Default to amount minor if nothing else matches
        return "AMOUNT_MINOR"
    
    @classmethod
    def get_priority(cls, category: str) -> str:
        """Get priority for a break category."""
        return cls.CATEGORIES.get(category, {}).get("priority", "MEDIUM")
    
    @classmethod
    def is_auto_resolvable(cls, category: str) -> bool:
        """Check if break category can be auto-resolved."""
        return cls.CATEGORIES.get(category, {}).get("auto_resolvable", False)
