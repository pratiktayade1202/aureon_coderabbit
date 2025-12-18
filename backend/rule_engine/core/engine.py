# backend/rule_engine/core/engine.py

import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from .registry import RuleRegistry
from .context import RuleContext
from .result import RuleResult
from .aggregator import ResultAggregator

# Import Domain Registrars
from ..domains.positions import register_position_rules
from ..domains.trade_cash import register_trade_cash_rules
from ..domains.nav import register_nav_rules
from ..domains.data_quality import register_data_quality_rules

class ReconciliationEngine:
    def __init__(self):
        self.registry = RuleRegistry
        self.is_initialized = False

    def initialize(self):
        if self.is_initialized: return
        print("🚀 Aureon Engine: Initializing Rule Domains...")
        register_position_rules()
        register_trade_cash_rules()
        register_nav_rules()
        register_data_quality_rules()  # NEW: Stress test detection rules
        self.is_initialized = True
        print(f"✅ Engine Ready. {len(self.registry.get_all())} rules loaded.")

    def _vectorized_match(self, df_trades: pd.DataFrame, df_cash: pd.DataFrame) -> Dict[int, Optional[int]]:
        """
        Fast matcher for trade↔cash pairing.

        Goals:
        - Avoid Python nested loops (O(N×M) in Python).
        - Preserve existing semantics:
          - Currency must match *if trade currency is present*
          - Amount match within tolerance: max(1.0, 1% of trade amount)
          - One cash row can only be used once (greedy, trade-order deterministic)

        Approach:
        1) Exact matches first (hashed lookup) using rounded amounts (2dp).
        2) Remaining matches via per-currency sorted arrays + binary search, only scanning
           candidates within tolerance (numpy vector ops), for ~O(N log M).
        """
        n_trades = len(df_trades)
        n_cash = len(df_cash)

        if n_trades == 0:
            return {}
        if n_cash == 0:
            return {i: None for i in range(n_trades)}

        # --- Normalize / extract columns (vectorized) ---
        df_trades = df_trades.copy()
        df_cash = df_cash.copy()

        if "net_amount" in df_trades.columns:
            df_trades["_trade_amount"] = pd.to_numeric(df_trades["net_amount"], errors="coerce").fillna(0.0).astype(float)
        elif "amount" in df_trades.columns:
            df_trades["_trade_amount"] = pd.to_numeric(df_trades["amount"], errors="coerce").fillna(0.0).astype(float)
        else:
            df_trades["_trade_amount"] = 0.0

        if "amount" in df_cash.columns:
            df_cash["_cash_amount"] = pd.to_numeric(df_cash["amount"], errors="coerce").fillna(0.0).astype(float)
        else:
            df_cash["_cash_amount"] = 0.0

        # IMPORTANT: mimic old behavior:
        # - If trade currency missing/blank => allow any currency
        # - If cash currency missing => default INR
        if "currency" in df_trades.columns:
            df_trades["_trade_currency"] = df_trades["currency"].fillna("").astype(str).str.upper().str.strip()
        else:
            df_trades["_trade_currency"] = ""

        if "currency" in df_cash.columns:
            df_cash["_cash_currency"] = df_cash["currency"].fillna("INR").astype(str).str.upper().str.strip()
        else:
            df_cash["_cash_currency"] = "INR"

        trade_amt = df_trades["_trade_amount"].to_numpy(dtype=float, copy=False)
        trade_ccy = df_trades["_trade_currency"].to_numpy(dtype=object, copy=False)
        cash_amt = df_cash["_cash_amount"].to_numpy(dtype=float, copy=False)
        cash_ccy = df_cash["_cash_currency"].to_numpy(dtype=object, copy=False)

        matches: Dict[int, Optional[int]] = {i: None for i in range(n_trades)}
        used_cash = np.zeros(n_cash, dtype=bool)

        # --- 1) Exact match pass (hash lookup) ---
        # Use 2dp rounding to avoid float representation surprises.
        trade_amt_key = np.round(trade_amt, 2)
        cash_amt_key = np.round(cash_amt, 2)

        from collections import defaultdict, deque

        exact_by_ccy: Dict[tuple[str, float], deque[int]] = defaultdict(deque)
        exact_any_ccy: Dict[float, deque[int]] = defaultdict(deque)

        for j in range(n_cash):
            ccy = cash_ccy[j] or "INR"
            key_amt = float(cash_amt_key[j])
            exact_by_ccy[(ccy, key_amt)].append(j)
            exact_any_ccy[key_amt].append(j)

        for i in range(n_trades):
            ccy = trade_ccy[i]
            key_amt = float(trade_amt_key[i])

            if ccy:
                dq = exact_by_ccy.get((ccy, key_amt))
            else:
                dq = exact_any_ccy.get(key_amt)

            if not dq:
                continue

            while dq and used_cash[dq[0]]:
                dq.popleft()
            if dq:
                j = dq.popleft()
                used_cash[j] = True
                matches[i] = int(j)

        # --- 2) Tolerance pass (binary search within currency buckets) ---
        # Build sorted cash arrays for remaining rows, per currency and "ANY".
        remaining_idx = np.flatnonzero(~used_cash)
        if remaining_idx.size == 0:
            return matches

        cash_by_ccy: Dict[str, tuple[np.ndarray, np.ndarray]] = {}
        # Currency-specific buckets
        for ccy in np.unique(cash_ccy[remaining_idx]):
            idxs = remaining_idx[cash_ccy[remaining_idx] == ccy]
            if idxs.size == 0:
                continue
            amts = cash_amt[idxs]
            order = np.argsort(amts, kind="mergesort")  # stable
            cash_by_ccy[str(ccy)] = (amts[order], idxs[order])

        # "ANY currency" bucket for trades with missing currency
        any_amts = cash_amt[remaining_idx]
        any_order = np.argsort(any_amts, kind="mergesort")
        cash_any = (any_amts[any_order], remaining_idx[any_order])

        for i in range(n_trades):
            if matches[i] is not None:
                continue

            amt = float(trade_amt[i])
            tol = max(1.0, abs(amt) * 0.01)
            ccy = trade_ccy[i]

            if ccy and str(ccy) in cash_by_ccy:
                amts_sorted, idxs_sorted = cash_by_ccy[str(ccy)]
            else:
                amts_sorted, idxs_sorted = cash_any

            if amts_sorted.size == 0:
                continue

            lo = np.searchsorted(amts_sorted, amt - tol, side="left")
            hi = np.searchsorted(amts_sorted, amt + tol, side="right")
            if lo >= hi:
                continue

            cand_amts = amts_sorted[lo:hi]
            cand_idxs = idxs_sorted[lo:hi]

            # Filter out already-used cash rows
            unused_mask = ~used_cash[cand_idxs]
            if not unused_mask.any():
                continue

            diffs = np.abs(cand_amts - amt)
            diffs = np.where(unused_mask, diffs, np.inf)
            k = int(np.argmin(diffs))
            if not np.isfinite(diffs[k]):
                continue

            j = int(cand_idxs[k])
            used_cash[j] = True
            matches[i] = j

        return matches

    def run(self, dataset_a: List[Dict], dataset_b: List[Dict], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_initialized: self.initialize()
        
        context = RuleContext(metadata=metadata)
        results: List[RuleResult] = []
        
        print(f"⚙️  Intelligent Matching: {len(dataset_a)} Trades vs {len(dataset_b)} Cash entries...")

        # ✅ FAST: Convert to DataFrames for vectorized operations
        # Reset index to ensure sequential 0-based indices matching list positions
        df_trades = pd.DataFrame(dataset_a).reset_index(drop=True)
        df_cash = pd.DataFrame(dataset_b).reset_index(drop=True)
        
        # ✅ FAST: Vectorized matching (replaces O(N×M) nested loops)
        matches = self._vectorized_match(df_trades, df_cash)
        
        active_rules = self.registry.get_all()

        # Iterate through TRADES (Dataset A) - still needed for rule execution
        # Use enumerate to get list position, which matches DataFrame index after reset_index
        for trade_idx, trade in enumerate(dataset_a):
            
            # 1. Get the matched CASH entry (from vectorized matching)
            cash_idx = matches.get(trade_idx)
            
            if cash_idx is not None:
                cash = dataset_b[cash_idx]
                match_status = "PROPOSED_MATCH"
            else:
                cash = {} # Empty dict implies "Missing Cash"
                match_status = "UNMATCHED"

            # 2. Run Validation Rules on the Pair
            row_results = {} 
            
            for rule in active_rules:
                if not rule.should_run(row_results): continue

                try:
                    # If unmatched, we still run rules. 
                    # Many rules will fail (e.g. "Exact Amount Match"), identifying the break.
                    res = rule.execute(trade, cash, context)
                    
                    # Pass IDs back to Orchestrator
                    if 'id' in trade:
                        res.details['id'] = trade['id']
                    if 'id' in cash and cash:
                        res.details['cash_id'] = cash['id']
                    
                    # Tag the result with our matching logic status
                    res.details['match_algorithm'] = match_status

                    row_results[rule.rule_id] = res
                    results.append(res)
                except Exception as e:
                    logging.error(f"Rule {rule.rule_id} crashed: {str(e)}")

        return ResultAggregator.aggregate(results)