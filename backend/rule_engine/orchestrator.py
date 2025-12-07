# backend/rule_engine/orchestrator.py

from typing import List
from sqlalchemy.orm import Session
from .core.registry import RuleRegistry
from .core.result import RuleResult
from .core.ctm import to_canonical_trade, to_canonical_cash
from .core.context import RuleContext

# --- DOMAIN REGISTERS ---
# We import ALL domains to ensure every rule is loaded into the registry
from .domains.trade_cash import register_trade_cash_rules
from .domains.positions import register_position_rules
# If these files don't exist yet, comment them out to prevent errors
try:
    from .domains.nav import register_nav_rules
    from .domains.corporate_actions import register_corporate_action_rules
    from .domains.fees import register_fee_rules
    from .domains.fx import register_fx_rules
except ImportError:
    pass

from ..models import (
    BrokerTrade, BankTxn, ReconBreak, ReconStatus, 
    BreakSeverity, RuleDefinition, RuleTier, Holding
)

class ReconOrchestrator:
    """
    The Execution Engine.
    Bridges the abstract Rule Engine with the concrete Database Models.
    """
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        
        # 1. BOOTSTRAP REGISTRY
        RuleRegistry.clear()
        
        # Register Rules
        register_trade_cash_rules()
        register_position_rules()
        
        # Try registering others if available
        try:
            if 'register_nav_rules' in globals(): register_nav_rules()
            if 'register_corporate_action_rules' in globals(): register_corporate_action_rules()
            if 'register_fee_rules' in globals(): register_fee_rules()
            if 'register_fx_rules' in globals(): register_fx_rules()
        except:
            pass
        
        self.rules = RuleRegistry.get_all_rules()
        
        # 2. INITIALIZE CONTEXT (FIXED)
        # We must pass params inside a 'metadata' dictionary
        self.context = RuleContext(
            metadata={
                "tenant_id": tenant_id,
                "TC_002_date_tolerance": 2,          # Explicit naming for rules to find
                "TC_011_abs_tolerance": 1.50,
                "fx_rates": {"USD/INR": 84.50},      # Default fallback
                "base_currency": "INR"
            }
        )

        # 3. DB SYNC (Critical for Foreign Keys)
        self._sync_rules_to_db()
        
        print(f"🔧 Orchestrator initialized for tenant {tenant_id} with {len(self.rules)} rules.")

    def _sync_rules_to_db(self):
        """
        Ensures that all Python rules and the special 'NO_MATCH' rule
        exist in the 'rule_definitions' table to satisfy Foreign Keys.
        """
        try:
            # Ensure System Rules exist
            if not self.db.query(RuleDefinition).filter_by(rule_id="NO_MATCH").first():
                sys_rule = RuleDefinition(
                    rule_id="NO_MATCH",
                    name="No Match Found",
                    description="System rule for orphaned records.",
                    domain="SYSTEM",
                    tier=RuleTier.TIER_1_DETERMINISTIC,
                    is_active=True
                )
                self.db.add(sys_rule)

            # Sync Python Rules
            for r in self.rules:
                if not self.db.query(RuleDefinition).filter_by(rule_id=r.rule_id).first():
                    new_rule = RuleDefinition(
                        rule_id=r.rule_id,
                        name=r.description[:50],
                        description=r.description,
                        domain="General",
                        tier=RuleTier.TIER_1_DETERMINISTIC,
                        is_active=True
                    )
                    self.db.add(new_rule)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"⚠️ Warning: Rule Sync Failed: {e}")

    # --- EXECUTION METHOD 1: TRADE-CASH ---
    def run_trade_cash_recon(self, db_trades: List[BrokerTrade], db_cash: List[BankTxn]):
        results = []
        
        # 1. Convert to Canonical Models (CTM)
        canonical_trades = {t.id: to_canonical_trade(t) for t in db_trades}
        canonical_cash = {c.id: to_canonical_cash(c) for c in db_cash}
        
        # 2. Match Loop
        for trade_id, trade in canonical_trades.items():
            best_match_id = None
            highest_score = 0.0
            best_rule_results = []
            
            for cash_id, cash in canonical_cash.items():
                score, rule_results = self._evaluate_pair(trade, cash)
                
                if score > highest_score:
                    highest_score = score
                    best_match_id = cash_id
                    best_rule_results = rule_results
            
            # 3. Apply Decision to DB
            db_trade = next(t for t in db_trades if t.id == int(trade_id))
            
            if highest_score >= 0.95 and best_match_id:
                db_cash_txn = next(c for c in db_cash if c.id == int(best_match_id))
                self._commit_match(db_trade, db_cash_txn)
                results.append(self._format_ui_response(db_trade, "MATCHED", highest_score))
            
            elif highest_score >= 0.75 and best_match_id:
                db_cash_txn = next(c for c in db_cash if c.id == int(best_match_id))
                self._commit_match(db_trade, db_cash_txn, status=ReconStatus.PARTIAL)
                results.append(self._format_ui_response(db_trade, "PARTIAL", highest_score))
                
            else:
                self._log_break(db_trade, best_rule_results if best_match_id else [])
                results.append(self._format_ui_response(db_trade, "BREAK", highest_score))
                
        return results

    # --- EXECUTION METHOD 2: POSITIONS ---
    def run_positions_recon(self, holdings: List[Holding]):
        results = []
        print(f"   -> Running Position Checks on {len(holdings)} records...")

        for h in holdings:
            overall_status = ReconStatus.MATCHED
            failures = []

            # Run all POS_ rules
            for rule in self.rules:
                if rule.rule_id.startswith("POS_"):
                    # Context is passed for tolerances
                    res = rule.execute(h, None, self.context)
                    if not res.passed:
                        overall_status = ReconStatus.BREAK
                        failures.append(res)
            
            # Update DB Status
            h.status = overall_status
            
            if overall_status == ReconStatus.BREAK:
                self._log_holding_break(h, failures)
            
            results.append({
                "id": h.id,
                "symbol": h.symbol,
                "quantity": h.quantity,
                "value": h.total_value,
                "status": overall_status,
                "score": 1.0 if overall_status == "MATCHED" else 0.0
            })
            
        self.db.commit()
        return results

    # --- HELPERS ---
    def _evaluate_pair(self, trade, cash):
        total_score = 0.0
        max_possible_score = 0.0
        results = []
        
        weights = {"CRITICAL": 10.0, "HIGH": 5.0, "MEDIUM": 2.0, "LOW": 1.0}
        
        for rule in self.rules:
            if rule.rule_id.startswith("TC_"): # Only run Trade-Cash rules here
                res = rule.execute(trade, cash, self.context)
                results.append(res)
                
                w = weights.get(rule.severity, 1.0)
                max_possible_score += w
                
                if res.passed:
                    total_score += (res.score * w)
                else:
                    if rule.severity == "CRITICAL":
                        return 0.0, results # Veto

        final_score = total_score / max_possible_score if max_possible_score > 0 else 0.0
        return final_score, results

    def _commit_match(self, trade, txn, status=ReconStatus.MATCHED):
        trade.status = status
        trade.bank_ref = f"Matched (Txn #{txn.id})"
        trade.recon_id = f"R-{trade.id}-{txn.id}"
        txn.status = "USED"
        txn.trade_ref = trade.id
        self.db.commit()

    def _log_break(self, trade, rule_results: List[RuleResult]):
        if trade.status != ReconStatus.BREAK:
            trade.status = ReconStatus.BREAK
            
            failures = [r for r in rule_results if not r.passed]
            primary_fail = failures[0] if failures else None
            
            break_type = primary_fail.break_type if primary_fail else "ORPHAN"
            note = primary_fail.message if primary_fail else "No match candidates found."
            rule_id = primary_fail.rule_id if primary_fail else "NO_MATCH"
            
            recon_break = ReconBreak(
                tenant_id=self.tenant_id,
                trade_id=trade.id,
                rule_id=rule_id,
                break_type=break_type,
                severity=BreakSeverity.HIGH, 
                status="OPEN",
                resolution_note=note,
                amount_diff=primary_fail.amount_diff if primary_fail else 0.0
            )
            self.db.add(recon_break)
            self.db.commit()

    def _log_holding_break(self, holding, rule_results):
        if not rule_results: return
        
        failure = rule_results[0]
        recon_break = ReconBreak(
            tenant_id=self.tenant_id,
            rule_id=failure.rule_id,
            break_type=failure.break_type,
            severity=BreakSeverity.HIGH,
            status="OPEN",
            resolution_note=failure.message,
            amount_diff=failure.amount_diff
        )
        self.db.add(recon_break)

    def _format_ui_response(self, trade, status, score):
        return {
            "id": trade.id,
            "date": str(trade.date),
            "timestamp": str(trade.date),
            "symbol": trade.symbol,
            "security": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "price": trade.price,
            "amount": trade.amount,
            "bank_ref": trade.bank_ref or "Unmatched",
            "status": status,
            "score": round(score, 2)
        }