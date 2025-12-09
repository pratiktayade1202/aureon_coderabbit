# backend/rule_engine/core/engine.py

import logging
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

    def _find_best_match(self, target: Dict, candidates: List[Dict], used_indices: set) -> Optional[int]:
        """
        Smart Matcher: Finds the index of the best candidate in the list.
        Matching Logic:
        1. Currency Must Match
        2. Amount must be within 1% tolerance
        """
        target_amt = float(target.get("amount") or target.get("net_amount") or 0)
        target_ccy = str(target.get("currency", "")).upper()
        
        best_idx = None
        min_diff = float('inf')
        
        for i, cand in enumerate(candidates):
            if i in used_indices: continue
            
            # 1. Currency Check (Loose)
            cand_ccy = str(cand.get("currency", "INR")).upper() # Default to INR if missing
            if target_ccy and cand_ccy and target_ccy != cand_ccy:
                continue

            # 2. Amount Check
            cand_amt = float(cand.get("amount") or 0)
            diff = abs(target_amt - cand_amt)
            
            # Tolerance: 1.0 unit or 1%
            tolerance = max(1.0, target_amt * 0.01)
            
            if diff <= tolerance:
                # We found a potential match. Is it the closest one?
                if diff < min_diff:
                    min_diff = diff
                    best_idx = i
                    
                    # Optimization: Exact match found, stop searching
                    if diff == 0:
                        return i
                        
        return best_idx

    def run(self, dataset_a: List[Dict], dataset_b: List[Dict], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_initialized: self.initialize()
        
        context = RuleContext(metadata=metadata)
        results: List[RuleResult] = []
        
        print(f"⚙️  Intelligent Matching: {len(dataset_a)} Trades vs {len(dataset_b)} Cash entries...")

        active_rules = self.registry.get_all()
        used_cash_indices = set()

        # Iterate through TRADES (Dataset A)
        for trade in dataset_a:
            
            # 1. Find the best matching CASH entry (Dataset B)
            match_idx = self._find_best_match(trade, dataset_b, used_cash_indices)
            
            if match_idx is not None:
                cash = dataset_b[match_idx]
                used_cash_indices.add(match_idx)
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
                    
                    # Pass ID back to Orchestrator
                    if 'id' in trade:
                        res.details['id'] = trade['id']
                    
                    # Tag the result with our matching logic status
                    res.details['match_algorithm'] = match_status

                    row_results[rule.rule_id] = res
                    results.append(res)
                except Exception as e:
                    logging.error(f"Rule {rule.rule_id} crashed: {str(e)}")

        return ResultAggregator.aggregate(results)