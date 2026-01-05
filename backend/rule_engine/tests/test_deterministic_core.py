#!/usr/bin/env python3
"""
Rule Engine Verification Test Suite.

Tests the 5 critical scenarios to verify deterministic core works:
1. Exact match → MATCH
2. Amount slightly off → REVIEW
3. Currency mismatch → BREAK
4. Date outside window → BREAK
5. Multiple candidates → highest score wins

Run with: python -m backend.rule_engine.tests.test_deterministic_core
"""

import logging
import sys
from datetime import date, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger("ENGINE_TEST")

# Import the new rule engine components
from backend.rule_engine.tiers import (
    DataQualityGate, 
    HardInvariantChecker,
    FinancialToleranceScorer,
    TemporalScorer
)
from backend.rule_engine.core.aggregator import ResultAggregator
from backend.rule_engine.core.candidate_generator import CandidateGenerator
from backend.rule_engine.core.config import DEFAULT_THRESHOLDS


def log_rule_results(trade_id: str, results: list, confidence: float, decision: str):
    """Log structured rule execution trace."""
    print(f"\n{'='*60}")
    print(f"[ENGINE] Trade={trade_id}")
    
    tier_results = {}
    for r in results:
        tier = r.tier
        if tier not in tier_results:
            tier_results[tier] = []
        tier_results[tier].append(r)
    
    for tier in sorted(tier_results.keys()):
        tier_name = {0: "Tier0-DQ", 1: "Tier1-INV", 2: "Tier2-FT", 3: "Tier3-TMP"}.get(tier, f"Tier{tier}")
        tier_passed = all(r.passed for r in tier_results[tier])
        print(f"  {tier_name}={'PASS' if tier_passed else 'FAIL'}")
        
        for r in tier_results[tier]:
            if r.weight > 0:  # Only log scoring rules
                print(f"    {r.rule_id} score={r.score:.2f} weight={r.weight:.2f} | {r.message}")
    
    print(f"  → confidence={confidence:.3f}")
    print(f"  → decision={decision}")
    print('='*60)


def test_scenario(name: str, trade: dict, cash_list: list, expected_decision: str):
    """Run a single test scenario."""
    print(f"\n{'#'*60}")
    print(f"# TEST: {name}")
    print(f"# Expected: {expected_decision}")
    print('#'*60)
    
    generator = CandidateGenerator()
    candidates = generator.generate_candidates(trade, cash_list)
    
    if not candidates:
        print(f"\n[ENGINE] Trade={trade.get('id')}")
        print("  → No candidates passed Tier 0-1")
        print("  → decision=BREAK")
        actual = "BREAK"
    else:
        best = candidates[0]
        log_rule_results(
            str(trade.get('id')),
            best.rule_results,
            best.confidence,
            best.decision
        )
        actual = best.decision
    
    if actual == expected_decision:
        print(f"\n✅ PASS: Got {actual} as expected")
        return True
    else:
        print(f"\n❌ FAIL: Expected {expected_decision}, got {actual}")
        return False


def main():
    """Run all 5 critical test scenarios."""
    print("\n" + "="*60)
    print(" RULE ENGINE DETERMINISTIC CORE - VERIFICATION SUITE")
    print(" Testing 5 Critical Scenarios (NO AI)")
    print("="*60)
    
    today = date.today()
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=7)
    
    results = []
    
    # ─────────────────────────────────────────────────────────────
    # SCENARIO 1: Exact match → MATCH
    # ─────────────────────────────────────────────────────────────
    trade1 = {
        "id": 1001,
        "amount": 100000.00,
        "net_amount": 100000.00,
        "date": today,
        "currency": "INR",
        "side": "BUY",
        "symbol": "RELIANCE"
    }
    cash1 = [{
        "id": 5001,
        "amount": -100000.00,  # Debit (outflow) for BUY
        "date": tomorrow,      # T+1 settlement
        "currency": "INR"
    }]
    results.append(test_scenario("Exact Match → MATCH", trade1, cash1, "MATCH"))
    
    # ─────────────────────────────────────────────────────────────
    # SCENARIO 2: Amount slightly off → REVIEW
    # ─────────────────────────────────────────────────────────────
    trade2 = {
        "id": 1002,
        "amount": 100000.00,
        "net_amount": 100000.00,
        "date": today,
        "currency": "INR",
        "side": "BUY",
        "symbol": "TCS"
    }
    cash2 = [{
        "id": 5002,
        "amount": -100750.00,  # 0.75% difference - should trigger REVIEW
        "date": tomorrow,
        "currency": "INR"
    }]
    results.append(test_scenario("Amount 0.75% Off → REVIEW", trade2, cash2, "REVIEW"))
    
    # ─────────────────────────────────────────────────────────────
    # SCENARIO 3: Currency mismatch → BREAK
    # ─────────────────────────────────────────────────────────────
    trade3 = {
        "id": 1003,
        "amount": 50000.00,
        "net_amount": 50000.00,
        "date": today,
        "currency": "INR",
        "side": "BUY",
        "symbol": "INFY"
    }
    cash3 = [{
        "id": 5003,
        "amount": -50000.00,
        "date": tomorrow,
        "currency": "USD"  # MISMATCH!
    }]
    results.append(test_scenario("Currency Mismatch → BREAK", trade3, cash3, "BREAK"))
    
    # ─────────────────────────────────────────────────────────────
    # SCENARIO 4: Date outside window → BREAK
    # ─────────────────────────────────────────────────────────────
    trade4 = {
        "id": 1004,
        "amount": 75000.00,
        "net_amount": 75000.00,
        "date": today,
        "currency": "INR",
        "side": "SELL",
        "symbol": "HDFC"
    }
    cash4 = [{
        "id": 5004,
        "amount": 75000.00,  # Credit for SELL
        "date": next_week,   # 7 days - outside T+3 window
        "currency": "INR"
    }]
    results.append(test_scenario("Date Outside T+3 → BREAK", trade4, cash4, "BREAK"))
    
    # ─────────────────────────────────────────────────────────────
    # SCENARIO 5: Multiple candidates → highest score wins
    # ─────────────────────────────────────────────────────────────
    trade5 = {
        "id": 1005,
        "amount": 200000.00,
        "net_amount": 200000.00,
        "date": today,
        "currency": "INR",
        "side": "BUY",
        "symbol": "WIPRO"
    }
    cash5 = [
        {
            "id": 5005,
            "amount": -195000.00,  # 2.5% off - poor match
            "date": tomorrow,
            "currency": "INR"
        },
        {
            "id": 5006,
            "amount": -200100.00,  # 0.05% off - great match
            "date": tomorrow,
            "currency": "INR"
        },
        {
            "id": 5007,
            "amount": -198000.00,  # 1% off - ok match
            "date": tomorrow,
            "currency": "INR"
        }
    ]
    
    print(f"\n{'#'*60}")
    print(f"# TEST: Multiple Candidates → Best Score Wins")
    print(f"# Expected: Cash 5006 should win (closest match)")
    print('#'*60)
    
    generator = CandidateGenerator()
    candidates = generator.generate_candidates(trade5, cash5)
    
    if candidates:
        print(f"\n[ENGINE] Trade=1005 | Candidates={len(candidates)}")
        for i, c in enumerate(candidates):
            marker = "← WINNER" if i == 0 else ""
            print(f"  Rank {i+1}: Cash={c.cash_id} conf={c.confidence:.3f} decision={c.decision} {marker}")
        
        winner = candidates[0]
        if winner.cash_id == 5006:
            print(f"\n✅ PASS: Cash 5006 won with highest confidence")
            results.append(True)
        else:
            print(f"\n❌ FAIL: Expected Cash 5006 to win, got {winner.cash_id}")
            results.append(False)
    else:
        print("❌ FAIL: No candidates generated")
        results.append(False)
    
    # ─────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print(" TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    
    test_names = [
        "Exact Match → MATCH",
        "Amount Off → REVIEW",
        "Currency Mismatch → BREAK",
        "Date Outside Window → BREAK",
        "Multiple Candidates → Best Wins"
    ]
    
    for i, (name, passed_test) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"  {i+1}. {name}: {status}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Deterministic core is working!")
        print("   Safe to proceed with Tier 4 integration.")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED - Fix before proceeding")
        return 1


if __name__ == "__main__":
    sys.exit(main())
